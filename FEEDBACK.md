# Echo-Path: Documentation Review and Status

The first review of the project's docs found that the Plan and Paper describe a system that was never built. This file tracks what has been fixed and what's still open.

Echo-Path is now the base of the team's Space Apps 2026 entry for Lunar Landing Site Navigator, which an event organiser allowed. The paper below predates that and isn't part of the submission unless the team decides to include it.

## Still open

### Paper (needs the team)

`NASA Project/NASA Space Apps 2026 - Paper.md` still contradicts the code. Proposed replacement text, with real results and verified citations, is in **`NASA Project/NASA Space Apps 2026 - Paper corrections (draft).md`**. It hasn't been applied, so that Christian and the team can review it first.

| The Paper says | What the code actually does |
|---|---|
| A\* or RRT search for lander fallback routes | Tries up to 16 spaced-out safe cells at 3 flight durations and ranks the feasible ones. A\* is used for the rover only |
| `solve_ivp` 3-DOF integration, gravity-turn guidance | Cubic polynomial path with velocity and acceleration derived by formula |
| Slope from 3×3 Sobel operators | Central differences (`np.gradient`) |
| Hazard H = w_s·S + w_r·R + w_i·I | `0.65·slope/limit + 0.35·roughness/limit`; sunlight is a pass/fail filter |
| Converts lat/lon to a local East-North-Up frame | Rejects lat/lon rasters; uses projected polar stereographic metres |
| Uses SELENE/Kaguya DEMs | LOLA only |
| Reachability envelope from remaining Δv | Not implemented; candidates are pre-scored by `hazard + 0.25·distance/size` |
| Cost J = w₁H + w₂Δv + w₃·drift | `hazard + 0.4·fuel_used/available_propellant`, no drift term |
| Abstract interfaces (`ITerrainProvider`…), "zero modifications" to swap parts | Plain functions in separate modules |
| "≥3 ranked fallbacks with H < 0.25" at any dropout | Measured: holds for 1 of 5 dropouts at the default site |
| Results table | Still `[insert score]` placeholders; real numbers are in the draft |
| Nothing on the rover | The rover is now a major part of the project |

The paper's mass-flow equation (`dm/dt = -T/(Isp·g0)`) is mathematically equivalent to what the code computes, so it can stay.

### Decisions only the team can make

- **Whether to finish the paper at all.** It was written as a Space Apps paper. If it's kept, it should describe Echo-Path as a separate project.
- **What the paper says the project is.** The team now describes the main purpose as mapping coordinates and navigating a vehicle to where the terrain says it can land, and the app is built around that. The paper is still written around comms outages, so its framing needs to change to match. See decision 3 in the draft.
- **Why losing comms matters.** Real landers already fly terminal descent on their own, because Earth is about 1.3 light-seconds away and the final phase is too fast for ground control to steer. If comms outages stay in the paper as a supporting feature, it still needs a clear reason. The draft proposes one for the team to accept or change.
- **Author list.** The paper names only Christian.
- **AI-use disclosure.** If the paper is published, say how AI tools were used, following the rules of wherever it's published.

### Smaller items

- **Obsidian frontmatter:** the Plan is missing its opening `---`, and in the Paper a `[[wikilink]]` comes before the frontmatter, so Obsidian ignores both files' properties.
- **The Plan** still describes the original phases, 8–12 week timeline and A\* requirement. It's fine as history, but the Paper shouldn't be read against it.
- **Unused code:** `matplotlib` in `requirements.txt`, `io` and `zipfile` imports in `app.py`, `config_dict()` in `trajectory.py`.

## Fixed

| Issue | Now |
|---|---|
| No git repo | On GitHub, with CI on every push and pull request |
| Demo only ran on synthetic terrain | Real LOLA data is the default, with sources in `NASA Project/data/README.md` |
| Lighting and comms ignored terrain beyond the crop | Terrain out to 186 km and lunar curvature in the 3D app |
| Site where Earth was never visible | Leibnitz Beta plateau, where Earth is visible and drops out during descent |
| Impossible Sun and Earth settings | The 3D app's sliders offer only what each site can see |
| Rover battery, dead-rover and route-smoothing bugs | Fixed, with regression tests |
| No live link | https://nasa-gitcantcommit.onrender.com/ |
| Hardcoded personal paths | Removed |
| Hazard weights, candidate pre-score and sampling bounds undocumented | In the root `README.md` |
| Scoring formula said "available mass" | Corrected to available propellant |
| Duplicate acceptance checklists | Dashboard checklist in `NASA Project/README.md`; 3D app checks in the root `README.md` |
| Repository layout left out root files | Updated |
| Phone layout broken | Redesigned; the app now works from 375 px wide |
