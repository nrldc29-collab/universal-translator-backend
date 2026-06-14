# Anai Consumer Product

Anai ships in two modes:

## 1. Cloud (open and go) — target: App Store / general public

Download the app → tap **Start talking** → speak. No PC, no Wi‑Fi LAN setup.

**Requires:** a hosted Anai bridge (Railway or your VPS) with a public HTTPS URL.

### Operator setup (one time)

1. Deploy to Railway — see [RAILWAY-DEPLOY.md](RAILWAY-DEPLOY.md).
2. Set `ANAI_CONSUMER_CLOUD_URL=https://YOUR-SERVICE.up.railway.app` in Railway variables (optional — auto-detected from `RAILWAY_PUBLIC_DOMAIN`).
3. Verify cloud + smoke:

```powershell
.\Deploy-ConsumerCloud.ps1 -CloudUrl "https://YOUR-SERVICE.up.railway.app"
```

4. Build the mobile app with that URL baked in:

```powershell
$env:EXPO_PUBLIC_CLOUD_API_URL = "https://YOUR-SERVICE.up.railway.app"
cd translator-mobile
eas build --profile production --platform all
```

4. Set demo credentials in Railway `USERS` (e.g. `demo:your-password`) or use the auto-bootstrap defaults from deploy logs.

### User experience

| Step | Action |
|------|--------|
| 1 | Install Anai from App Store / Play Store (or TestFlight/internal) |
| 2 | Tap **Start talking** on first launch |
| 3 | Allow microphone |
| 4 | Talk — continuous translation until Pause |

Web users on the same Railway URL get the same bridge automatically (same-origin).

## 2. Bridge (self-hosted) — clinics, families, field work

Run `.\Open-Anai.ps1` on a PC; phones on the same Wi‑Fi connect to the LAN IP.

Best when you need **privacy**, **no cloud**, or **offline-capable** local models.

## vs Google Translate

| | Anai Cloud | Google Translate |
|---|------------|------------------|
| Setup | App + cloud URL (we host) | Download only |
| EN↔HT depth | Primary product path | Generic |
| Confidence / native cert | Built in | Minimal |
| Self-host option | Yes (bridge mode) | No |
| Languages | 14 | 249 |

Anai is a **conversation bridge** with trust UX — not a replacement for Google's language breadth.

## Verify consumer readiness

```powershell
.\Deploy-ConsumerCloud.ps1 -CloudUrl "https://YOUR-SERVICE.up.railway.app"
.\Score-Product.ps1 -Full -BackendUrl "https://YOUR-SERVICE.up.railway.app"
python scripts/product_readiness.py --live https://YOUR-SERVICE.up.railway.app
```

### EAS production build

1. Set the demo password as an EAS secret (matches Railway `USERS`):

```powershell
cd translator-mobile
eas secret:create --scope project --name EXPO_PUBLIC_CLOUD_DEMO_PASS --value "your-railway-password" --type string
```

2. Build and submit:

```powershell
.\Build-ConsumerApp.ps1 -CloudUrl "https://YOUR-SERVICE.up.railway.app" -DemoPass "your-railway-password"
eas submit --platform ios    # uses App Store Connect login interactively
eas submit --platform android
```
