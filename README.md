# ID Card OCR service (Tesseract, self-hosted)

Replaces the Gemini call in the Make.com scenario with a self-hosted
Tesseract OCR service, deployed on Render.com's free Docker web service tier.

## What's here

- `app.py` - Flask app. `POST /extract` accepts the image as a
  `multipart/form-data` file field (this is what Make.com's HTTP module
  sends when Body content type is set to "multipart/form-data" and a file
  output is mapped directly to a File field - no base64 encoding needed).
  It also accepts raw image bytes as the whole request body, or a JSON body
  `{"image_base64": "..."}`, as fallbacks. Returns the same 14-field JSON
  shape the Gemini step used to produce
  (`topLeft, text1..text10, middle1..middle3, imageUrl`).
- `Dockerfile` - installs Tesseract + Arabic and English language data, then
  runs the Flask app with gunicorn, binding to Render's `$PORT`.
- `requirements.txt` - deployment dependencies.

## Current status / limitations (read this)

- The OCR engine call (`pytesseract`, `lang="ara+eng"`) is confirmed working
  on Render's build infrastructure (the Arabic language pack installs and
  the service responds to `/health`).
- The **field-mapping logic** (which OCR line becomes `text6` vs `text8`
  etc.) is a **generic heuristic**, written without a real sample of the
  target card. It correctly identifies: the first Arabic-script line (name),
  the longest digit run (ID number/topLeft), formatted phone numbers, and
  dates in order (1st = DOB, 2nd = expiry). Everything else (nationality,
  job title, two company names, region) is currently filled by dumping
  leftover lines in sequence - which will very likely put values in the
  wrong keys for a real card, since it does not know the card's actual
  layout.
- **This needs a real photo of the card to tune properly.** Once you can
  send one, either run it through `/extract` on the deployed service, or
  send it back so the parsing rules can be adjusted (ideally using each
  line's position on the card, not just its order in the OCR text) and
  redeployed.
- The free Render plan spins the service down after 15 minutes of
  inactivity. The next request after idle can take ~50 seconds while it
  spins back up - this is expected, not an error.

## Deploying to Render

1. Push this folder to a GitHub repo (already done: this repo).
2. In the Render dashboard: New -> Web Service -> connect this repo (Public
   Git Repository works fine; Render auto-detects the `Dockerfile`).
3. Under Compute, select the Free plan (Render defaults to the paid
   Starter plan - switch it manually).
4. No environment variables are required; Render sets `PORT` automatically
   and the Dockerfile's `CMD` binds to it.
5. Once deployed, Render gives you a public URL, e.g.
   `https://idcard-ocr-q2a8.onrender.com`.
6. Note: with a "Public Git Repository" connection, new commits do not
   auto-deploy. After pushing a change, go to the service in the Render
   dashboard and click Manual Deploy -> Deploy latest commit.
7. Test it:
   ```
   curl -X POST https://YOUR-RENDER-URL/extract \
     -F "file=@sample.jpg"
   ```

## Wiring into Make.com

Replace the Gemini HTTP module with:
- URL: `https://YOUR-RENDER-URL/extract`
- Method: POST
- Headers: none needed
- Body content type: `multipart/form-data (supports file uploads)`
- Body content: one field, Name `file`, Type `File`, with its file source
  bound (via the radio button) directly to the Telegram "Download a File"
  module's output bundle - do not manually type a base64/IML expression,
  the File field type handles this natively.

The response is already the flat 14-field JSON, so "Parse response" should
stay enabled and no further mapping changes are needed beyond what the
Gemini step already produced.
