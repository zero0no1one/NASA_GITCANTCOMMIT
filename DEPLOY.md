# Deploying the live demo

The `Dockerfile` builds the whole site as one service: the Python API also serves the built 3D app. It works on any host that runs containers. These steps use Render's free plan.

## Before you start

The code must be on `main`, with the **tests**, **web** and **container** checks green on the pull request. The **container** check builds this image and runs it under a 512 MB memory limit, the same as Render's free plan.

## Create the service

1. Sign up at https://render.com.
2. Choose **New** → **Web Service**.
3. Choose the repository:
   - **If you own the repo:** connect GitHub and select it. Every push to `main` then redeploys automatically.
   - **If you don't:** use the **Public Git Repository** option and paste `https://github.com/zero0no1one/NASA_GITCANTCOMMIT`. If that option isn't offered, ask the repo owner to create the service instead.
4. Use these settings:

   | Setting | Value |
   |---|---|
   | Name | `echo-path` (becomes part of the URL; pick another if taken) |
   | Language | Docker |
   | Branch | `main` |
   | Region | Singapore (closest to the Philippines) |
   | Instance type | Free |
   | Health check path (under Advanced) | `/api/health` |

5. Click **Deploy Web Service** and wait for the build to finish.
6. Open the `https://....onrender.com` address it gives you. You should see the lander descending over the terrain.

## Updating it

- **Connected repo:** automatic on every push to `main`.
- **Public Git Repository:** click **Manual Deploy** → **Deploy latest commit**. Render's deploy hook URL (under Settings) does the same with one request.

## Free plan limits

- **It sleeps.** After 15 minutes without visitors the service stops, and the next visitor waits about a minute. **Open the link a couple of minutes before you present.**
- **It's slow per request.** The free plan has 0.1 CPU. Measured on the live service, a re-route takes about 1 s and a Sun or max-slope change about 2.5 s. The simulation clock waits while the rover re-plans, so nothing jumps.
- **Keep a backup.** Record a demo video in case the service or the venue's internet misbehaves.

## Run the production build on your own computer

```powershell
cd web
npm run build
cd "..\NASA Project"
python -m uvicorn api.main:app --port 8000
```

Then open http://localhost:8000. For development, use the two-server setup in `web/README.md` instead.
