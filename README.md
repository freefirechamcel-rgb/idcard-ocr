# ID Card OCR service (Tesseract, self-hosted)

Replaces the Gemini call in the Make.com scenario with a self-hosted
Tesseract OCR service, deployed on Render (free web service tier).

## What's here

- `app.py` - Flask app. `POST /extract` takes `{"image_base64": "..."}` and
  returns the same 14-field JSON shape the Gemini step used to produce
  (`topLeft, text1..text10, middle1..middle3, imageUrl`).
- `Dockerfile` - installs Tesseract + Arabic and English language data, then
  runs the Flask app with gunicorn, binding to Render's $PORT.
- `requirements.txt` - Python dependencies.

## Current status / limitations (read this)

- The OCR engine call (`pytesseract`, `lang="ara+eng"`) is correct and works
  once deployed - the build server has normal internet access to install the
  Arabic language pack.
- The field-mapping logic (which OCR line becomes `text6` vs `text8` etc.) is
  a generic heuristic, written without a real sample of the target card. It
  needs a real photo of the card to tune properly.

## Deploying to Render

1. In the Render dashboard: New -> Web Service -> Public Git Repository ->
   paste this repo's URL.
2. Render auto-detects the Dockerfile and builds it. No environment
   variables are required; Render sets PORT automatically.
3. Once deployed, Render gives you a public URL, e.g.
   `https://idcard-ocr.onrender.com`.
4. Free tier note: the service sleeps after 15 minutes of inactivity and
   takes about a minute to wake up on the next request.

## Wiring into Make.com

Replace the Gemini HTTP module with:
- URL: `https://YOUR-RENDER-URL.onrender.com/extract`
- Method: POST
- Body content type: JSON
- Body: `{"image_base64": "{{base64(5.data)}}"}`

The response is already the flat 14-field JSON, so no further "Parse
response" mapping changes should be needed beyond what the Gemini step
already produced.

