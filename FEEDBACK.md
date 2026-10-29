# Echo-Path: Documentation Review

*Review of the 5 markdown files in this project, each checked against the code (`app.py`, `echo_path/*.py`, `tests/*.py`). Reviewer: Claude (Claude Code). Nothing in the project was changed during the review.*

---

## TL;DR

The project has two sets of docs, and they disagree.

- **The Codex docs** (`README.md`, `MODEL_GUIDE.md`, `PROJECT_DOCUMENTATION.md`) are good. They match the code closely and are honest about its limits; they even say "this is not A*". The limitations sections are the strongest writing in the project.
- **The Plan and the Paper** describe a system that was never built. If a judge or reviewer reads the paper and then opens the code, the contradictions will hurt credibility.

**Recommendation:** rewrite the paper to describe what the code actually does, and move the unbuilt features to *Future Work*. Don't try to build all of them before submission.

---

## 1. Paper vs. code

I searched the code for each of these features; none of them is present.

| The Paper / Plan says | What the code actually does |
|---|---|
| A* or RRT graph search for fallback routes | Picks up to 16 spatially separated safe cells, tries 3 flight durations each (0.8×, 1.0×, 1.25× the remaining time), and ranks the feasible ones (`echo_path/routing.py`) |
| `scipy.integrate.solve_ivp` 3-DOF integration, gravity-turn guidance | Cubic polynomial position profile with velocity/acceleration derived by formula, no ODE solver (`echo_path/trajectory.py`) |
| Slope from 3×3 Sobel operators | `np.gradient` (central differences) |
| Hazard H = w_s·S + w_r·R + w_i·I | `0.65·slope/limit + 0.35·roughness/limit`, clipped to [0, 1]. Illumination is a **pass/fail filter** applied afterwards, not a weighted term (`echo_path/terrain.py:95`, `app.py:23-27`) |
| Converts lat/lon to a local East-North-Up frame | Rejects lat/lon rasters outright; you must reproject before importing |
| Uses SELENE/Kaguya Terrain Camera DEMs | Not supported |
| Reachability envelope from remaining Δv | Not implemented; candidate sites are pre-scored as `hazard + 0.25·distance/tile_size` |
| Cost J = w₁H + w₂Δv + w₃·drift | Score = `hazard + 0.4 · fuel_used / available_propellant`, with no drift term |
| Dropout when a ray passes below the lunar limb | Flat local model; any elevation ≤ 0° counts as blocked, and there's no curvature |
| Abstract interfaces (`ITerrainProvider`, `ICommsModel`, …) and "zero modifications" needed to swap modules | Plain functions with no interfaces or base classes. The code *is* modular, but the "zero modifications" claim is overstated |
| Python 3.10+ | README says 3.11+ |

One thing that's correct: the paper's mass-flow equation (`dm/dt = -T / (Isp·g0)`) is mathematically equivalent to what the code computes. Keep it.

The Plan's "Why It Wins" section leans on *determinism via A\**. That argument is still valid for what was built: the polynomial evaluator plus the candidate search is fully deterministic. Rephrase it around that.

---

## 2. Other problems in the Paper

- **Results table is still placeholders** (`[insert score]`). The app can produce real numbers: run the synthetic demo, then take the nominal hazard, fuel margin and slope from the "Flight telemetry" tab, and the fallback values from the ranked fallback table. Otherwise drop the table.
- **Claims that aren't backed up yet:** "optimized fallback trajectories", "successfully precomputes", "significantly increasing mission survivability". There's no evaluation behind these yet, so soften them to "feasible under the prototype's checks".
- **The evaluation section promises "≥3 fallbacks with H < 0.25" at every dropout.** The code doesn't enforce or measure this. Either measure it or remove it.
- **The references aren't citations.** They describe topics rather than naming papers. Suggested real ones:
  - Smith, D. E. et al. (2010). *The Lunar Orbiter Laser Altimeter Investigation on the Lunar Reconnaissance Orbiter Mission.* Space Science Reviews.
  - Açıkmeşe, B. & Ploen, S. (2007). *Convex Programming Approach to Powered Descent Guidance for Mars Landing.* JGCD.
  - Blackmore, L., Açıkmeşe, B. & Scharf, D. (2010). *Minimum-Landing-Error Powered-Descent Guidance for Mars Landing Using Convex Optimization.* JGCD.
  - Epp, C. D. & Smith, T. B. (2007). *Autonomous Precision Landing and Hazard Detection and Avoidance Technology (ALHAT).* IEEE Aerospace Conference.
  - Hart, P. E., Nilsson, N. J. & Raphael, B. (1968). *A Formal Basis for the Heuristic Determination of Minimum Cost Paths.* (A*, if it stays in Future Work.)
- **The core premise will draw questions.** Real landers already fly terminal descent on their own: Earth is ~1.3 light-seconds away and the final phase is too fast for ground control to steer. A knowledgeable judge will ask *why does losing comms change where you land?* The pitch needs a concrete answer, for example:
  - the landing target needed a ground go/no-go call;
  - Echo-Path builds an onboard table of precomputed fallbacks so the lander has a vetted answer without the ground;
  - or loss of comms is used as a proxy for a degraded mission state.

  Note that `MODEL_GUIDE.md` itself says comms loss "is not assumed to imply navigation failure". Make the paper consistent with that.
- **None of the docs name the Space Apps 2026 challenge** this answers. Judging is against a specific challenge statement, so name it near the top.
- **Author line lists only Christian.** Add the rest of the team.

---

## 3. Problems in the Codex docs

These are mostly fine; the fixes are small.

- **Three docs overlap heavily.** The manual acceptance checklist appears in both `README.md` (12 steps) and `PROJECT_DOCUMENTATION.md` (14 steps), and the two copies already differ. For example, only the README has the "Earth elevation 90° / -5°" test. Pick one home for each fact. Suggested split:
  - `README.md`: quick start + acceptance checklist.
  - `MODEL_GUIDE.md`: assumptions and equations. Keep it, because the app renders it in the "Data & model guide" tab.
  - `PROJECT_DOCUMENTATION.md`: rename it to something like `docs/ARCHITECTURE.md` and remove the parts it duplicates from the other two.
- **Hardcoded paths:** `PROJECT_DOCUMENTATION.md` uses `C:\Users\Christian\Documents\...`, which won't work on anyone else's machine. Use relative paths.
- **It lives outside `NASA Project/`,** and its own repository-layout tree leaves it out.
- **Undocumented details** that matter for the paper:
  - the hazard weights (0.65 slope / 0.35 roughness);
  - the candidate pre-score (`hazard + 0.25·distance/size`);
  - the trajectory sampling bounds (at least 121 samples, at most 15,000).
- **The scoring formula** says `fuel_used / available_mass`. The code divides by available *propellant* (`mass − dry_mass`). Small, but it changes the meaning.
- **Broken Obsidian frontmatter:**
  - The Plan is missing its opening `---`, so Obsidian won't read the properties.
  - In the Paper, a `[[wikilink]]` comes before the frontmatter, so its properties are ignored too. Move the link below the closing `---`.

---

## 4. Beyond the docs

- **No git repo yet.** Space Apps submissions usually need a project link, so run `git init`, push to GitHub, and add a `.gitignore` covering `__pycache__/`, `.obsidian/` and `.freebuff/`.
- **The demo has only run on synthetic terrain.** The README says real LOLA validation is "pending your DEM download." Loading one real landing region is probably the single highest-value step for the "uses NASA data" part of judging.
  - LOLA's south-pole polar-stereographic DEMs are already projected in metres, so they should load without reprojection.
  - Watch the crop limits: at most 240 px and 10 km. At 5 m/px a crop is ~1.2 km wide; at 20 m/px it's ~4.8 km.
  - In polar-stereographic grids, grid north is not geographic north. `MODEL_GUIDE.md` already warns about this.
- **Unused code:**
  - `matplotlib` is in `requirements.txt` but nothing imports it.
  - `app.py` imports `io` and `zipfile` without using them.
  - `config_dict()` in `trajectory.py` is never called.
- **`.freebuff/`** is project metadata from another AI coding tool. It's harmless, but keep it out of the repo.
- **AI-use disclosure:** check the current Space Apps rules on disclosing AI-generated code.
- **Tests:** the test suite (`python -m unittest discover -s tests -v`) was not run as part of this review.

---

## 5. Suggested next steps (in order)

1. `git init` and push, so nothing gets lost.
2. Rewrite Paper §5–7 to match the code. Move A*, ODE integration, ENU conversion, Kaguya, and the interfaces to §9 Future Work.
3. Get one real LOLA crop running and use it to fill the results table.
4. Name the Space Apps challenge and sharpen the "why comms loss matters" argument.
5. Consolidate the three Codex docs and fix the paths and frontmatter.
6. Optional, if time allows: implement A* behind `routing.py` so the code catches up to the original plan.
