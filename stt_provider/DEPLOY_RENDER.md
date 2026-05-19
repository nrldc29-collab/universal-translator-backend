# Deploy on Render

## 1. Push this repo to GitHub

```bash
git add render.yaml DEPLOY_RENDER.md
git commit -m "Add Render deployment option"
git push origin main
```

## 2. Create the Render service

In Render:

- New → Blueprint
- Connect the GitHub repo
- Select this repo
- Deploy using `render.yaml`

## 3. Set allowed origins

In Render environment variables, update:

```
ALLOWED_ORIGINS=https://your-client-domain.com
```

For testing with the hosted API and local browser client, temporarily use:

```
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## 4. Get keys

Render generates:

- `STT_API_KEY`
- `ADMIN_API_KEY`

Copy them from the Render dashboard.

## 5. Verify health

```bash
curl https://your-render-service.onrender.com/health
```

## 6. Verify usage endpoint

```bash
curl https://your-render-service.onrender.com/v1/usage \
  -H "Authorization: Bearer YOUR_STT_API_KEY"
```

## 7. Use streaming WebSocket

```
wss://your-render-service.onrender.com/stt/stream
```

## Notes

- Use `wss://`, not `ws://`, for Render.
- CPU transcription may be slow on small instances.
- The first request can be slow while the model downloads and warms up.
- For heavier production use, prefer a GPU-capable host or VPS.
