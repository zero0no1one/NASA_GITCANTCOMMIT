# What we learned from Echo-Path

Notes for future projects: what worked, what broke and what we'd do differently. Echo-Path itself is a separate practice project.

## Before building

- **Read the event rules and the challenge list first.** Space Apps says teams shouldn't start on their project until the hackathon begins, and its challenge statements come out about two weeks before that. We found both after building.
- **Check what the rules require in a submission.** For Space Apps 2026 that includes describing how AI tools were used, licensing your own work as open source, and citing every source.
- **Decide what the project is for early.** Echo-Path started around communication outages and later moved to landing navigation. The code and UI moved with it, but the paper didn't.

## Stack

- **Python backend, React frontend.** The engine stayed in Python (NumPy, SciPy, Rasterio), with a small FastAPI layer in front of it. The 3D app used Vite, React, TypeScript and Three.js through React Three Fiber. A clear JSON contract let the two sides change separately.
- **One service in production.** The API also serves the built site, so there is one thing to deploy and no cross-origin setup.
- **Keep large data apart from results.** The terrain grid is big and rarely changes, and mission results are small and change often. Fetching them separately means changing a setting doesn't re-download the map.

## Lunar data

- **Sources.** NASA GSFC's PGDA site publishes LOLA elevation maps: 5 m/px for south pole landing sites and a coarser polar mosaic. Sources and citations are in `NASA Project/data/README.md`.
- **Projection.** These maps are south polar stereographic, in metres, so distances work directly on the grid. Convert to latitude and longitude for anything people read.
- **A small map isn't enough for horizons.** Terrain far outside a 1 km crop can block the Sun or Earth, so we added coarser layers out to 186 km and lunar curvature (height drop of d²/2R).
- **Not every site can see Earth.** Near the pole, Earth can sit below the horizon at mean libration. Check that a site suits the scenario before building on it.
- **Limit inputs to what's physically possible.** Free Sun and Earth sliders allowed impossible skies. Solar latitude stays within about ±1.54°, and libration shifts Earth by up to about 6.7° in latitude and 7.9° in longitude.

## Deployment

- **Render's free plan:** 512 MB of memory and 0.1 CPU, and it sleeps after 15 idle minutes, taking about a minute to wake. Rover routes that took 0.2–0.3 s locally took 1.7–2.9 s live, so measure on the real host.
- **Test the container in CI.** Our image built fine, but the site returned 500, because `rasterio` needs `libexpat1`, which the slim Python image lacks. Rasterio is imported lazily, so nothing failed until a request came in. Importing the data loader during the build and running the image under a 512 MB limit in CI now catches this kind of failure.
- **Wait for green.** One pull request was merged with a failing check, and the live site then failed.
- **Check files for local details.** A generated data file carried a local path in its metadata. Search binaries as well as text before publishing.

## Pitfalls in the 3D app

- **Don't put per-frame values in React state that the whole app reads.** Read the clock inside the render loop, and let only the components that show it subscribe.
- **drei's `Html` caused React 19 unmount errors for us.** Drawing labels to canvas sprites removed them.
- **Version cached data.** When the terrain format changed, a stale browser copy crashed the page. A version number in the URL fixed that.
- **Late responses can undo user actions.** Clicking Begin descent just after choosing a site started the run, then the older request's reply cancelled it. Disable the action from the moment a change starts, not from when the request is sent.
- **Don't mix state from two maps.** During a map switch, the new sites were drawn using the old grid and showed wrong coordinates, and an empty list looked like "no sites". Wait until the data on hand all belongs to the current map.
- **Background tabs throttle animation.** Frame rate readings from a hidden or unfocused browser mean nothing. Check smoothness on the machine you'll present from, in the foreground.

## Models and honesty

- **Write invariants as tests.** A battery above 100%, a dead rover still driving and route smoothing that undid the search were all found by checking what must always be true.
- **Measure before claiming.** We assumed A\* avoided shadow at the default site, but the numbers showed no reduction (24% vs 22% of the time). It only saved about 2 minutes.
- **Write the paper from results.** The first paper described methods that were never built and had placeholder results. Numbers should come from a script anyone can re-run.

## Team workflow

- **Branch per task, CI on every pull request,** with test, web and container checks.
- **Keep work in separate folders** so people can build in parallel without merge conflicts.
- **Test the live site after every deploy.** Two real bugs were found this way, because the slower server makes timing problems easier to hit.
- **Record a demo video early,** in case the host or the venue's internet fails.
