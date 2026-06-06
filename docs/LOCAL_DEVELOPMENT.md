# Local Development

## Quick start (recommended)

```bash
cp .env.example .env
pip install -r requirements.txt
make setup-models          # espeak-ng required on Linux for Haitian Creole TTS
make start-local           # add --restart if port 8000 is stale
```

Wait for **LIVE** in the app header, then:

```bash
make verify-local-live
```

Windows:

```powershell
.\Start-Translator.ps1
.\Test-Translator.ps1
```

Install **espeak-ng** for HT voice on all platforms (`apt install espeak-ng`, `brew install espeak`, or `choco install espeak`).

## Manual backend + frontend

### Backend

```bash
cp .env.example .env
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
PARTIAL_TTS_MODE=1 uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/docs`.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://127.0.0.1:5173`.

## Mobile

```bash
cd translator-mobile
cp .env.example .env
npm install
npm start
```

For a real phone, set `EXPO_PUBLIC_API_URL` to your computer LAN backend URL, not `127.0.0.1`.
