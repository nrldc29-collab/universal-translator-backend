#!/usr/bin/env bash
# deploy-railway.sh — Deploy the Universal Translator to Railway
#
# Prerequisites:
#   1. Install Railway CLI: npm i -g @railway/cli
#   2. Login: railway login
#   3. Create project: railway init (or link existing: railway link)
#
# Usage: ./deploy-railway.sh
#
# Required env vars (set via Railway dashboard or `railway variables set`):
#   USERS=username:password          — at least one user for auth
#   JWT_SECRET=<random-64-chars>     — signing key for auth tokens
#   ALLOWED_ORIGINS=https://<service>.up.railway.app
#
# Optional env vars:
#   OLLAMA_ENABLED=0                 — Ollama not available on Railway (no GPU)
#   HYBRID_ENABLE_MARIAN_FALLBACK=0  — skip Marian model load on CPU (faster startup)
#   OPENAI_API_KEY=sk-...            — for AILang quality enhancement agents
#   GOOGLE_TTS_API_KEY=...           — for neural cloud TTS voices
#   DATA_DIR=/app/data                 — enable SQLite persistence (mount volume)
#   STT_PROVIDER=streaming           — if using external STT provider
#   STT_PROVIDER_URL=http://...      — external STT service URL
#   STT_PROVIDER_API_KEY=...         — external STT service key

set -euo pipefail

echo "=== Universal Translator — Railway Deployment ==="

# Check Railway CLI
if ! command -v railway &>/dev/null; then
    echo "ERROR: Railway CLI not found. Install with: npm i -g @railway/cli"
    exit 1
fi

# Check logged in
if ! railway whoami &>/dev/null; then
    echo "ERROR: Not logged in. Run: railway login"
    exit 1
fi

echo ""
echo "Setting production environment variables..."
railway variables set ENVIRONMENT=production
railway variables set BACKEND_HOST=0.0.0.0
railway variables set SERVE_FRONTEND_DIST=1
railway variables set PRELOAD_MODELS=1
railway variables set TRANSLATION_BACKEND=hybrid
railway variables set HYBRID_ENABLE_MARIAN_FALLBACK=0
railway variables set OLLAMA_ENABLED=0
railway variables set AILANG_ENABLED=1
railway variables set USE_GPU=0
railway variables set WHISPER_MODEL_SIZE=tiny
railway variables set NEAR_ZERO_LATENCY_MODE=1
railway variables set VAD_SILENT_CHECKS=1
railway variables set PREDICTIVE_CACHE_SIZE=1000
railway variables set PREDICTIVE_CACHE_TTL=3600
railway variables set DATA_DIR=/app/data

echo ""
echo "Checking required secrets..."
for var in USERS JWT_SECRET ALLOWED_ORIGINS; do
    if ! railway variables get "$var" &>/dev/null 2>&1; then
        echo "WARNING: $var not set. Set it with: railway variables set $var=<value>"
    fi
done

echo ""
echo "Deploying..."
railway up --detach

echo ""
echo "=== Deployment initiated ==="
echo ""
echo "Monitor with: railway logs"
echo "Get URL with: railway domain"
echo ""
echo "After deployment, verify with:"
echo "  curl https://<your-service>.up.railway.app/health"
echo "  curl https://<your-service>.up.railway.app/diagnostics"
echo "  curl https://<your-service>.up.railway.app/languages"
echo ""
echo "Mount a Railway volume at /app/data for persistent quotas/users."
echo "To connect the mobile app, set EXPO_PUBLIC_API_URL to your Railway domain."
