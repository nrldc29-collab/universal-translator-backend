# Anai QuickStart

## Consumer cloud (no PC) — App Store path

1. Install Anai (TestFlight / Play internal / store build with cloud URL baked in).
2. Tap **Start talking** on first launch.
3. Allow microphone → speak. Continuous translation until Pause.

Operators: deploy to Railway ([RAILWAY-DEPLOY.md](RAILWAY-DEPLOY.md)), then:

```powershell
.\Build-ConsumerApp.ps1 -CloudUrl "https://YOUR-SERVICE.up.railway.app"
```

See [CONSUMER.md](CONSUMER.md) for full consumer product details.

---

## Bridge mode (self-hosted PC) — three steps

## 1. Start the stack (PC)

**Easiest — one command (starts + opens browser):**

```powershell
.\Open-Anai.ps1
```

Or manually:

```powershell
.\Start-Translator.ps1 -QuickStart -Restart
```

Wait until the terminal shows `Ready: True`.

## 2. Open the interpreter

| Surface | URL |
|---------|-----|
| **PC browser** | http://127.0.0.1:8000/ |
| **iPhone Safari (mic)** | `https://<your-LAN-IP>:8443/mobile/app` (same Wi‑Fi) |
| **Phone setup page** | http://`<your-LAN-IP>`:8000/mobile |

Run `.\Ensure-MobileHttps.ps1` once if Safari mic HTTPS is not ready.

## 3. Talk

1. Pick languages (default **English → Haitian Creole**).
2. Tap **Start** / the mic — keep talking; translation and voice continue until you tap **Pause**.
3. Advanced options (replay, two-way mode, diagnostics) live under **Settings** or the status strip **TECH** toggle.

## Full phone app (Expo Go)

```powershell
.\Start-Translator.ps1 -Restart
.\Fix-ExpoPhone.ps1
```

Scan the Expo URL from the terminal (same Wi‑Fi as the PC).

## Verify everything

```powershell
.\scripts\verify_all_product.ps1
```

Or with a running backend:

```powershell
python scripts/product_readiness.py --live http://127.0.0.1:8000
```

Target: **10/10 on all product dimensions** (including consumer open-and-go).
