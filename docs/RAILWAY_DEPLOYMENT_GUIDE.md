# Railway Deployment Guide

This guide covers deploying the Universal Translator backend to Railway for cloud access.

## Prerequisites

- Railway account (https://railway.app)
- GitHub repository with the universal-translator code
- Railway CLI (optional, for advanced deployments)

## Step 1: Prepare Repository

1. Ensure your code is pushed to GitHub
2. Verify `railway.json` exists in the repository root
3. Verify `Dockerfile` exists and is production-ready

## Step 2: Create Railway Project

1. Log in to Railway (https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `universal-translator` repository
4. Railway will detect the `railway.json` and `Dockerfile` automatically

## Step 3: Configure Environment Variables

Copy the environment variables from `railway-production-env.txt` to your Railway project:

### Critical Production Variables (REQUIRED)

These MUST be set before the app will start in production:

```bash
# Generate with: python scripts/generate_secrets.py
JWT_SECRET=<32-character-random-secret>
USERS=<username>:<strong-password>
ADMIN_IDENTITIES=<username>

# Replace with your Railway deployment URL (from Railway Networking tab)
ALLOWED_ORIGINS=https://<your-service>.up.railway.app
ALLOWED_ORIGIN_REGEX=https?://<your-service>\.up\.railway\.app
```

### Optional but Recommended Variables

```bash
# Enable persistent storage
DATA_DIR=/app/data

# OpenAI API for AILang features (optional)
OPENAI_API_KEY=<your-openai-key>

# Google TTS for higher quality voices (optional)
GOOGLE_TTS_API_KEY=<your-google-tts-key>
```

## Step 4: Configure Persistent Storage

1. In Railway project settings, go to "Variables"
2. Add `DATA_DIR=/app/data`
3. Go to "Storage" tab
4. Add a new volume named `data` mounted to `/app/data`
5. This ensures quotas and user data persist across restarts

## Step 5: Deploy

1. Click "Deploy" in Railway
2. Wait for the build to complete (2-5 minutes)
3. Railway will download models and build the Docker image
4. Once deployed, you'll get a URL like `https://your-service.up.railway.app`

## Step 6: Verify Deployment

Check the following endpoints:

```bash
# Health check
curl https://your-service.up.railway.app/health

# Diagnostics
curl https://your-service.up.railway.app/diagnostics

# Languages
curl https://your-service.up.railway.app/languages
```

Expected responses:
- `/health` should return `{"ready": true, ...}`
- `/diagnostics` should show all services as healthy
- `/languages` should return the supported languages list

## Step 7: Configure Mobile App

Update the mobile app to use the Railway backend:

1. Open `translator-mobile/.env`
2. Set the backend URL:
```bash
EXPO_PUBLIC_API_URL=https://your-app.railway.app
```

3. Rebuild the mobile app:
```bash
cd translator-mobile
npm run build
```

## Step 8: Test End-to-End

1. Start the mobile app
2. Login with the credentials you set in `USERS`
3. Test audio streaming translation
4. Verify latency metrics are displayed
5. Test duplex mode with two speakers

## Monitoring

### Railway Dashboard

- View logs in Railway dashboard
- Monitor CPU/memory usage
- Check deployment health

### Diagnostics Endpoint

```bash
curl https://your-app.railway.app/diagnostics
```

This returns:
- Translation health (runtime, fallback chain)
- STT provider status
- CIP brain status
- Persistence status
- Service health summaries

### Metrics Endpoint (requires auth)

```bash
curl -H "Authorization: Bearer <token>" https://your-app.railway.app/metrics
```

## Scaling

### Vertical Scaling

Railway automatically scales based on load. Configure in Railway settings:
- CPU: 0.5 vCPU - 4 vCPU
- RAM: 512 MB - 8 GB

### Horizontal Scaling

For high traffic, consider:
- Railway's built-in load balancing
- Multiple Railway projects behind a load balancer
- CDN for static assets

## Troubleshooting

### App Won't Start

Check logs for:
- Missing required environment variables (JWT_SECRET, USERS, ALLOWED_ORIGINS)
- Invalid ALLOWED_ORIGINS format
- Database initialization errors

### High Latency

- Check `WHISPER_MODEL_SIZE` (tiny is fastest)
- Verify `USE_GPU=0` for Railway (GPU not available)
- Monitor CPU usage in Railway dashboard

### Memory Issues

- Reduce `MAX_AUDIO_MB` and `STREAM_BUFFER_MAX_MB`
- Decrease `STT_MAX_CONCURRENCY`
- Enable `DATA_DIR` for persistent storage to reduce memory usage

### WebSocket Connection Issues

- Verify `ALLOWED_ORIGINS` includes your mobile app's domain
- Check Railway logs for WebSocket errors
- Test with `wscat` or similar WebSocket client

## Security Checklist

- [ ] JWT_SECRET is 32+ characters and not a placeholder
- [ ] USERS uses strong passwords (not demo:demo)
- [ ] ALLOWED_ORIGINS is set to your actual Railway URL (not example.com)
- [ ] ENVIRONMENT=production is set
- [ ] ADMIN_IDENTITIES is set for admin access
- [ ] DATA_DIR is configured for persistent storage
- [ ] API keys (if used) are stored in Railway Variables, not in code

## Cost Optimization

Railway pricing is based on usage. To optimize costs:

1. **Use smaller models**: Set `WHISPER_MODEL_SIZE=tiny`
2. **Limit concurrency**: Reduce `STT_MAX_CONCURRENCY` to 1-2
3. **Disable GPU**: Ensure `USE_GPU=0` (GPU costs extra)
4. **Monitor usage**: Check Railway dashboard regularly
5. **Set quotas**: Configure `FREE_DAILY_AUDIO_MINUTES` to limit usage

## Backup and Recovery

### Database Backup

The SQLite database at `/app/data/anai.sqlite3` is persisted in the Railway volume.

To backup:
1. SSH into the Railway container
2. Copy `/app/data/anai.sqlite3` to external storage

### Recovery

If the volume is lost:
1. Restore from backup
2. Restart the Railway service
3. Data will be reloaded from the restored database

## Continuous Deployment

Railway automatically deploys on push to the configured branch. To control this:

1. In Railway project settings, configure the deployment branch
2. Set up branch protection rules in GitHub
3. Use `railway.json` to control deployment behavior

## Advanced: Custom Domain

To use a custom domain:

1. In Railway project settings, go to "Networking"
2. Add your custom domain
3. Configure DNS records (CNAME to Railway)
4. Update `ALLOWED_ORIGINS` to include your custom domain
5. Update mobile app `EXPO_PUBLIC_API_URL`

## Support

For issues:
- Check Railway logs first
- Review `/diagnostics` endpoint
- Check GitHub issues
- Consult Railway documentation: https://docs.railway.app
