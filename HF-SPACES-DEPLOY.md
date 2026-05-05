# Deploy To Hugging Face Spaces

This project now includes a ready-to-upload Hugging Face Space in:

```text
hf-space/
```

Use this folder for the free Hugging Face demo. It is a lightweight Gradio app
for English-Spanish speech/text translation. The full FastAPI backend remains
the right deployment target for WebSockets, auth, metrics, and TTS.

## Important Account Note

Do not use your Hugging Face account password for Git or API deploys. Hugging
Face uses User Access Tokens for this workflow. Create a token with write access:

```text
https://huggingface.co/settings/tokens
```

If you pasted a real password into chat, rotate it before publishing anything.

## Option A: Deploy In The Browser

1. Open https://huggingface.co/spaces
2. Create a new Space.
3. Choose:
   - Space name: `universal-translator`
   - SDK: `Gradio`
   - Hardware: free CPU to start
   - Visibility: public or private
4. In the Space Files tab, upload the contents of `hf-space/`:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`
   - `README.md`
5. Commit the files.
6. Wait for the build to finish.

Your Space URL will look like:

```text
https://huggingface.co/spaces/YOUR_USERNAME/universal-translator
```

## Option B: Deploy From This Machine

Create a Hugging Face write token, then run PowerShell from this project root:

```powershell
$env:HF_TOKEN = "hf_your_write_token_here"
.\deploy-hf-space.ps1 -SpaceId "YOUR_USERNAME/universal-translator"
```

To make the Space private:

```powershell
$env:HF_TOKEN = "hf_your_write_token_here"
.\deploy-hf-space.ps1 -SpaceId "YOUR_USERNAME/universal-translator" -Private
```

The helper script creates the Space if it does not exist and uploads `hf-space/`.

## Option C: Git Deploy

If Git is available:

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/universal-translator
cd universal-translator
cp -r ../universal-translator/hf-space/* .
git add .
git commit -m "Deploy Universal Translator Space"
git push
```

When Git asks for a password, use a Hugging Face write token, not your account
password.

## What The Space Supports

- Record or upload audio
- Transcribe with `faster-whisper` tiny on CPU
- Translate English to Spanish
- Translate Spanish to English
- Run on the free Hugging Face CPU tier

## Limits

- No WebSocket streaming in this Gradio demo
- No Piper TTS in this Gradio demo
- Free CPU hardware can be slow on the first run
- The first build downloads models and may take several minutes

For the complete app experience, deploy the FastAPI backend on a GPU-capable
server and point the web/mobile clients at that backend.
