# Shorts AI Scheduler — Cloud Web App

## Deploy on Render
1. Create a **private** GitHub repository and upload this project.
2. In Render choose **New → Blueprint**, connect the repo, and deploy the `render.yaml`.
3. Set `APP_PASSWORD` to a strong private password.
4. Set `GOOGLE_REDIRECT_URI` to `https://YOUR-APP.onrender.com/` (include trailing slash).
5. In Google Cloud create OAuth client type **Web application**. Add that exact URI to Authorized redirect URIs.
6. Configure OAuth consent screen/test user. Download the Web application JSON.
7. Open the hosted app, sign in, upload the JSON in Settings, and authorize YouTube.

## Important limitations
- This is a single-owner prototype. Keep the URL and password private.
- The blueprint uses a paid web service and persistent disk; check Render pricing before deploying.
- Hugging Face models run on server CPU/RAM. A low-resource plan may be too slow or fail to load them.
- YouTube Data API does not generally download uploaded video files. Caption list/download access is restricted and may not work for every video.
- Videos without accessible captions need a local media file uploaded to this app for local ASR.
- Visual frame understanding/OCR is not implemented yet.
- YouTube scheduling requires eligible private videos that have never been published. Test one first.
- Do not commit OAuth JSON, token files, or secrets to GitHub.
- Verify generated Hadith, Quran quotations, attributions and religious claims manually.
