import io
import json
import zipfile
import pandas as pd


def route_frame(route):
    frame = pd.DataFrame(route["position"], columns=["x_m", "y_m", "z_m"])
    frame.insert(0, "time_s", route["t"])
    for i, name in enumerate(["vx_m_s", "vy_m_s", "vz_m_s"]):
        frame[name] = route["velocity"][:, i]
    frame["mass_kg"] = route["mass"]
    frame["thrust_N"] = route["thrust"]
    frame["clearance_m"] = route["clearance"]
    return frame


def export_bundle(terrain, hazard, nominal, routes, config, coverage):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mission.json", json.dumps(config, indent=2, allow_nan=False))
        z.writestr("nominal.csv", route_frame(nominal).to_csv(index=False))
        z.writestr("coverage.json", json.dumps(coverage, indent=2))
        for key in ["hazard", "slope", "roughness", "safe"]:
            z.writestr(f"{key}.csv", pd.DataFrame(hazard[key]).to_csv(index=False, header=False))
        z.writestr("elevation_m.csv", pd.DataFrame(terrain.z).to_csv(index=False, header=False))
        for waypoint, options in routes.items():
            z.writestr(f"outage_{waypoint}/ranking.json", json.dumps([{k:v for k,v in r.items() if k != "route"} for r in options], indent=2))
            for i, result in enumerate(options):
                z.writestr(f"outage_{waypoint}/route_{i+1}.csv", route_frame(result["route"]).to_csv(index=False))
        z.writestr("README.txt", "Local grid x/easting and y/northing in metres; array row 0 is south. Clear LOS is checked only inside the tile. CSV route times are relative to each route start. Coverage applies to sampled outage waypoints only. Feasible means passing sampled prototype checks. Unknown terrain rejects routes. No solution means none among the tested polynomial candidates, not proof of unreachability.")
    return buf.getvalue()
