# Railway Deployment Guide - Agentic ESG

## 📋 Prerequisites

- Railway account (https://railway.app)
- GitHub repository connected to Railway
- Anthropic API key

## 🚀 Deployment Steps

### 1. Add MongoDB Service to Railway

1. Go to Railway dashboard: https://railway.app/dashboard
2. Open your `agentic-esg` project
3. Click **"+ New"** → **"Database"** → **"Add MongoDB"**
4. Railway will automatically:
   - Provision a MongoDB instance
   - Inject `MONGO_URL` environment variable to all services
   - Connect it to your backend service

### 2. Configure Environment Variables

In your Railway backend service settings, add:

**Required:**
- `ANTHROPIC_API_KEY` - Your Claude API key (you already have this)

**Auto-injected by Railway:**
- `MONGO_URL` - MongoDB connection string (automatically added when you add MongoDB service)
- `PORT` - Railway assigns this automatically

**Optional:**
- `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins (if needed)

### 3. Verify Configuration Files

All configuration files are now ready:

✅ **Dockerfile** - Fixed to use correct module path `cs.backend:app`
✅ **railway.toml** - Configured with:
   - Start command: `uvicorn cs.backend:app --host 0.0.0.0 --port $PORT`
   - Health check: `/health` endpoint
   - Restart policy: on_failure with 3 max retries
✅ **index.html** - API_BASE automatically uses Railway URL in production

### 4. Deploy Backend Service

After adding MongoDB:

1. Railway will automatically trigger a redeploy
2. Or manually trigger: **Settings** → **Redeploy**

### 5. Monitor Deployment

Check the deployment logs for:

```
CS backend started | db=mongodb
INFO: Application startup complete
```

If you see `db=not connected (MONGO_URL missing)`, MongoDB wasn't properly connected.

### 6. Get Your Production URL

1. In Railway dashboard, go to your backend service
2. Click **Settings** → **Networking**
3. Click **Generate Domain** if not already generated
4. Your app will be available at: `https://your-app.up.railway.app`

## 🔍 Verification Checklist

After deployment, verify:

- [ ] Backend is running: `https://your-app.up.railway.app/health`
- [ ] MongoDB connected: Check logs for "db=mongodb"
- [ ] Frontend loads: `https://your-app.up.railway.app/`
- [ ] API works: Try analyzing a region
- [ ] History persists: Refresh page and check history sidebar

## 🐛 Troubleshooting

### MongoDB Connection Issues

**Cross-Project MongoDB Connection:**

If your MongoDB service is in a **different Railway project** than your backend:

1. Go to your MongoDB service project
2. Copy the `MONGO_PUBLIC_URL` value (format: `mongodb://mongo:password@yamanote.proxy.rlwy.net:32910`)
3. In your backend service project → Variables:
   - Set `MONGO_URL` = (paste the MONGO_PUBLIC_URL value)
4. Railway will automatically redeploy

**Note:** `mongodb.railway.internal` only works within the same project. For cross-project connections, always use the public proxy URL.

**Same-Project MongoDB Connection:**

If logs show `MONGO_URL not configured`:
1. Verify MongoDB service is added to the project
2. Check that MongoDB and backend are in the same project
3. Restart the backend service

### Health Check Failing

If deployment fails health checks:
1. Check logs for startup errors
2. Verify `ANTHROPIC_API_KEY` is set
3. Ensure `/health` endpoint is accessible

### CORS Errors

If frontend can't connect to backend:
1. Verify the backend URL in browser console
2. Check CORS middleware is allowing your domain
3. Add your Railway domain to `ALLOWED_ORIGINS` if needed

## 📊 Environment Variables Summary

| Variable | Source | Required | Description |
|----------|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Manual | ✅ Yes | Claude API key for AI analysis |
| `MONGO_URL` | Railway | ✅ Yes | MongoDB connection string (auto-injected) |
| `PORT` | Railway | ✅ Yes | Server port (auto-assigned) |
| `ALLOWED_ORIGINS` | Manual | ❌ No | Custom CORS origins (optional) |

## 🎯 Post-Deployment

Once deployed:

1. **Test the application** with a few analyses
2. **Monitor logs** for any errors
3. **Check MongoDB** - analyses should be saved and retrievable
4. **Share the URL** - Your app is live!

## 📝 Notes

- Railway provides **500 hours free** per month
- MongoDB free tier: **512 MB storage**
- Backend serves both API and frontend (single service)
- Health checks run every 60 seconds with 300s timeout
- Auto-restart on failure (max 3 retries)

## 🔗 Useful Links

- Railway Dashboard: https://railway.app/dashboard
- Railway Docs: https://docs.railway.app
- MongoDB Docs: https://www.mongodb.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com