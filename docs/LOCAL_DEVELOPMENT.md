# Local Development

## Backend

```bash
copy .env.example .env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Frontend

```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Mobile

```bash
cd translator-mobile
copy .env.example .env
npm install
npm start
```

For a real phone, set `EXPO_PUBLIC_API_URL` to your computer LAN backend URL, not `127.0.0.1`.
