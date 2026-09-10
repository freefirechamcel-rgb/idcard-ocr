"""
ID Card OCR extraction service.
Replaces the Gemini-based extraction step in the Make.com Telegram bot scenario.

POST /extract
  body: {"image_base64": "<base64-encoded JPEG/PNG>"}
  returns: {"topLeft": "", "text1": "", ... "text10": "", "middle1": "",
            "middle2": "", "middle3": "", "imageUrl": ""}

Uses Tesseract OCR (ara+eng) for text recognition. Field-mapping logic is
heuristic (regex + line classification) since there is no AI reasoning step.
NOTE: this heuristic parser was written without a real sample of the target
card, and will need tuning once tested against actual card photos - see
README.md.
"""
import base64
import io
import logging
import re

import pytesseract
from flask import Flask, jsonify, request
from PIL import Image, ImageOps, ImageFilter

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("idcard-ocr")

FIELD_KEYS = [
    "topLeft", "text1", "text2", "text3", "text4", "text5", "text6",
    "text7", "text8", "text9", "text10", "middle1", "middle2", "middle3",
    "imageUrl",
]

ARABIC_RE = re.compile(r"[؀-ۿ]")
ARABIC_DIGIT_RE = re.compile(r"[٠-٩]")
LATIN_RE = re.compile(r"[A-Za-z]")
DATE_RE = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b")
PHONE_RE = re.compile(r"\b(\+?\d[\d\s\-]{6,14}\d)\b")
LONG_DIGITS_RE = re.compile(r"\b(\d{6,})\b")


def preprocess(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    w, h = image.size
    if max(w, h) < 1600:
        scale = 1600 / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def ocr_lines(image: Image.Image) -> list[str]:
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(image, lang="ara+eng", config=config)
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def classify(line: str) -> str:
    has_ar = bool(ARABIC_RE.search(line))
    has_la = bool(LATIN_RE.search(line))
    if has_ar and not has_la:
        return "arabic"
    if has_la and not has_ar:
        return "latin"
    if has_ar and has_la:
        return "mixed"
    return "other"


def extract_fields(lines: list[str]) -> dict:
    result = {k: "" for k in FIELD_KEYS}

    arabic_lines = [ln for ln in lines if classify(ln) == "arabic"]
    latin_lines = [ln for ln in lines if classify(ln) in ("latin", "mixed")]

    dates = []
    phone = ""
    long_digits = []
    for ln in lines:
        for m in DATE_RE.findall(ln):
            dates.append(m)
        looks_formatted = "+" in ln or bool(re.search(r"\d[\s\-]\d", ln))
        pm = PHONE_RE.search(ln)
        if pm and not phone and looks_formatted:
            candidate = pm.group(1).replace(" ", "").replace("-", "")
            if len(candidate) >= 7:
                phone = candidate
        else:
            for m in LONG_DIGITS_RE.findall(ln):
                long_digits.append(m)

    if long_digits:
        result["topLeft"] = long_digits[0]

    if arabic_lines:
        result["text1"] = arabic_lines[0]
    if len(arabic_lines) > 1:
        result["middle2"] = arabic_lines[1]
    if len(arabic_lines) > 2:
        result["middle3"] = arabic_lines[2]

    name_candidates = [ln for ln in latin_lines if re.fullmatch(r"[A-Za-z .]+", ln)]
    if name_candidates:
        result["text2"] = name_candidates[0]

    if long_digits:
        result["text3"] = max(long_digits, key=len)

    if dates:
        result["text4"] = dates[0]
    if len(dates) > 1:
        result["middle1"] = dates[1]

    result["text7"] = phone

    used = {result["text2"]}
    leftover = [ln for ln in latin_lines if ln not in used and ln not in dates]
    remaining_keys = ["text5", "text6", "text8", "text9", "text10"]
    for key, val in zip(remaining_keys, leftover):
        result[key] = val

    result["imageUrl"] = ""
    return result


@app.route("/extract", methods=["POST"])
def extract():
    payload = request.get_json(silent=True) or {}
    b64 = payload.get("image_base64") or payload.get("data")
    if not b64:
        return jsonify({"error": "image_base64 field is required"}), 400

    try:
        image_bytes = base64.b64decode(b64)
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        log.exception("failed to decode image")
        return jsonify({"error": f"invalid image data: {exc}"}), 400

    try:
        processed = preprocess(image)
        lines = ocr_lines(processed)
        fields = extract_fields(lines)
    except Exception as exc:
        log.exception("OCR failed")
        return jsonify({"error": f"ocr failed: {exc}"}), 500

    log.info("OCR raw lines: %s", lines)
    return jsonify(fields)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

