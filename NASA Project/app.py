"""Run with: python -m streamlit run app.py"""
import io
import json
import zipfile
from dataclasses import asdict
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from echo_path.terrain import synthetic, load_dem, hazards
from echo_path.comms import visibility, shadow_map
from echo_path.trajectory import Vehicle, trajectory
from echo_path.routing import plan_fallbacks

st.set_page_config(page_title="Echo-Path | Mission planner", page_icon="🌙", layout="wide")
st.title("🌙 Echo-Path")
st.caption("Lunar descent contingency planner · Research prototype")


@st.cache_data(show_spinner=False)
def analyze(terrain, params):
    h = hazards(terrain, params["slope"], params["roughness"], params["footprint"])
    if params["shadows"]:
        light = shadow_map(terrain, params["sun_az"], params["sun_el"])
        h["illumination"] = light
        h["safe"] &= light == 1
        h["hazard"] = np.where(light == 1, h["hazard"], 1.)
    return h


@st.cache_data(show_spinner=False)
def fallback_cached(terrain, hazard, nominal, index, vehicle):
    return plan_fallbacks(terrain, hazard, nominal, index, vehicle)


from echo_path.export import route_frame, export_bundle


with st.sidebar:
    st.header("1 · Terrain")
    source = st.selectbox("Terrain source", ["Synthetic demo", "Upload GeoTIFF", "Local GeoTIFF path"])
    params = {}
    if source == "Synthetic demo":
        seed = st.number_input("Terrain seed", min_value=0, max_value=99999, value=42)
        terrain = synthetic(int(seed))
    else:
        st.caption("Use a north-up lunar projected GeoTIFF in metres. Raw PDS IMG/LBL pairs need conversion. Crop stays at native resolution.")
        item = st.file_uploader("LOLA DEM (.tif / .tiff)", type=["tif", "tiff"]) if source == "Upload GeoTIFF" else st.text_input("Absolute DEM file path")
        row = st.number_input("Crop start row (from north)", 0, value=0, step=1)
        col = st.number_input("Crop start column (from west)", 0, value=0, step=1)
        size = st.slider("Crop size (pixels)", 20, 240, 120, 10)
        factor = st.selectbox("Elevation units after band scale/offset", ["Metres", "Kilometres"])
        confirmed = st.checkbox("I confirm this is lunar elevation data and the selected vertical units are correct")
        if not item or not confirmed:
            st.info("Supply a DEM and confirm its units, or choose Synthetic demo.")
            st.stop()
        try:
            if source == "Upload GeoTIFF":
                from rasterio.io import MemoryFile
                with MemoryFile(item.getvalue()) as mem:
                    terrain = load_dem(mem.name, int(row), int(col), size, 1000. if factor == "Kilometres" else 1.)
                terrain.source = item.name
            else:
                terrain = load_dem(item, int(row), int(col), size, 1000. if factor == "Kilometres" else 1.)
        except Exception as exc:
            st.error(f"DEM could not be loaded: {exc}")
            st.stop()
    st.header("2 · Landing limits")
    params["slope"] = st.slider("Maximum slope (degrees)", 1., 30., 12.)
    params["roughness"] = st.slider("Maximum detrended roughness (m)", .1, 5., 1.5)
    params["footprint"] = st.slider("Landing neighbourhood (m)", 10., 100., 30., 5.)
    params["shadows"] = st.checkbox("Require sunlit landing sites")
    params["sun_az"] = st.slider("Sun azimuth (grid degrees)", 0., 360., 90., disabled=not params["shadows"])
    params["sun_el"] = st.slider("Sun elevation (degrees)", -5., 90., 10., disabled=not params["shadows"])
    st.header("3 · Descent & vehicle")
    sx = st.slider("Start X (% of tile)", 1, 99, 15)
    sy = st.slider("Start Y (% of tile)", 1, 99, 50)
    tx = st.slider("Target X (% of tile)", 1, 99, 75)
    ty = st.slider("Target Y (% of tile)", 1, 99, 50)
    altitude = st.number_input("Initial height above terrain (m)", 10., 2000., 350., 10.)
    duration = st.number_input("Nominal descent time (s)", 20., 300., 120., 10.)
    vx = st.number_input("Initial X velocity (m/s)", -50., 50., 4.)
    vy = st.number_input("Initial Y velocity (m/s)", -50., 50., 0.)
    vz = st.number_input("Initial vertical velocity (m/s)", -50., 0., -3.)
    dry = st.number_input("Dry mass (kg)", 100., 10000., 700., 50.)
    fuel = st.number_input("Initial propellant (kg)", 1., 5000., 300., 10.)
    thrust = st.number_input("Maximum thrust (N)", 100., 100000., 5000., 100.)
    isp = st.number_input("Specific impulse (s)", 50., 500., 310., 10.)
    st.header("4 · Communication geometry")
    earth_az = st.slider("Earth / relay azimuth (grid degrees)", 0., 360., 270.)
    earth_el = st.slider("Earth / relay elevation (degrees)", -5., 90., 3.)

with st.spinner("Computing terrain and descent…"):
    hazard = analyze(terrain, params)
    start = [sx/100*terrain.width, sy/100*terrain.height]
    end = [tx/100*terrain.width, ty/100*terrain.height]
    start.append(float(terrain.sample(*start))+altitude)
    end.append(float(terrain.sample(*end)))
    if not np.isfinite(start+end).all():
        st.error("Start or target is on missing DEM data. Move the coordinates.")
        st.stop()
    vehicle = Vehicle(dry, fuel, thrust, isp)
    try:
        nominal = trajectory(terrain, start, [vx, vy, vz], end, duration, dry+fuel, vehicle)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    sample_indices = np.unique(np.linspace(0, len(nominal["t"])-1, 31).astype(int))
    positions = nominal["position"][sample_indices]
    comms = visibility(terrain, positions, earth_az, earth_el)
    target_row, target_col = int(round(end[1]/terrain.dy)), int(round(end[0]/terrain.dx))
    target_safe = bool(hazard["safe"][target_row, target_col])

st.caption(f"{terrain.source} · {terrain.z.shape[1]} × {terrain.z.shape[0]} cells · {terrain.dx:g} × {terrain.dy:g} m/cell · local grid coordinates")
cols = st.columns(4)
cols[0].metric("Landing-eligible area", f"{100*hazard['safe'].mean():.1f}%")
cols[1].metric("Blocked comms samples", f"{np.sum(comms == 0)} / {len(comms)}")
cols[2].metric("Nominal propellant required", f"{nominal['fuel_used']:.1f} kg")
cols[3].metric("Peak required thrust", f"{nominal['peak_thrust']:.0f} N")
if not nominal["feasible"]:
    st.error("Nominal trajectory fails checks: " + "; ".join(nominal["reasons"]) + ". Adjust inputs before generating contingencies.")
if not target_safe:
    st.warning("Nominal landing target fails the selected terrain or illumination limits.")
if (comms == -1).any():
    st.warning("Some communication samples cross missing terrain and have unknown visibility.")
st.caption("Clear communication means no obstruction inside this DEM tile; terrain beyond its boundary is unknown. Azimuth is clockwise from grid north.")

st.subheader("Inspect an outage and its fallback options")
default_step = int(np.flatnonzero(comms == 0)[0]) if (comms == 0).any() else 15
step = st.select_slider("Outage waypoint (also allows manually injected outages)", options=list(range(len(sample_indices))), value=default_step,
                        format_func=lambda i: f"{nominal['t'][sample_indices[i]]:.1f}s · { {0:'blocked', 1:'clear', -1:'unknown'}[comms[i]]}")
index = int(sample_indices[step])
options, diagnostics = [], {"tested": 0, "rejected": {}}
if nominal["feasible"]:
    with st.spinner("Checking fallback candidates from the selected state…"):
        options, diagnostics = fallback_cached(terrain, hazard, nominal, index, vehicle)

config = {"terrain": {"source": terrain.source, "shape": list(terrain.z.shape), "dx_m": terrain.dx, "dy_m": terrain.dy, "metadata": terrain.metadata},
          "hazard_parameters": params, "vehicle": asdict(vehicle), "start_m": start, "initial_velocity_m_s": [vx, vy, vz],
          "target_m": end, "duration_s": duration, "earth_azimuth_deg": earth_az, "earth_elevation_deg": earth_el,
          "nominal_feasible": nominal["feasible"], "nominal_rejection_reasons": nominal["reasons"], "nominal_target_eligible": target_safe}
# Include raster contents: changing a file at the same path invalidates stored results.
import hashlib
fingerprint = json.dumps(config, sort_keys=True) + hashlib.sha256(terrain.z.tobytes()).hexdigest()
if st.session_state.get("fingerprint") != fingerprint:
    st.session_state["fingerprint"] = fingerprint
    st.session_state["batch"] = {}
    st.session_state["coverage"] = []

tabs = st.tabs(["Mission map", "3D descent", "Flight telemetry", "Outage coverage & export", "Data & model guide"])
with tabs[0]:
    layer = st.radio("Map layer", ["Elevation (m)", "Hazard (0–1)", "Slope (degrees)", "Roughness (m)"], horizontal=True)
    values = {"Elevation (m)": terrain.z, "Hazard (0–1)": hazard["hazard"], "Slope (degrees)": hazard["slope"], "Roughness (m)": hazard["roughness"]}[layer]
    fig = go.Figure(go.Heatmap(z=values, x=np.arange(terrain.z.shape[1])*terrain.dx, y=np.arange(terrain.z.shape[0])*terrain.dy,
                             colorscale="Cividis" if layer == "Elevation (m)" else "YlOrRd", colorbar={"title": layer}))
    fig.add_trace(go.Scatter(x=nominal["position"][:, 0], y=nominal["position"][:, 1], mode="lines", name="Nominal", line={"color": "#38bdf8", "width": 3}))
    for state, label, color in [(0, "Blocked LOS", "#f43f5e"), (-1, "Unknown LOS", "#a855f7")]:
        fig.add_trace(go.Scatter(x=positions[comms == state, 0], y=positions[comms == state, 1], mode="markers", name=label, marker={"color": color, "size": 9}))
    fig.add_trace(go.Scatter(x=[end[0]], y=[end[1]], mode="markers", name="Nominal target", marker={"symbol": "x", "size": 14, "color": "white"}))
    for rank, option in enumerate(options, 1):
        p = option["route"]["position"]
        fig.add_trace(go.Scatter(x=p[:, 0], y=p[:, 1], mode="lines", name=f"Fallback {rank}", line={"dash": "dash"}))
        fig.add_trace(go.Scatter(x=[p[-1, 0]], y=[p[-1, 1]], text=[str(rank)], mode="markers+text", textposition="top center", showlegend=False))
    fig.add_trace(go.Scatter(x=[positions[step, 0]], y=[positions[step, 1]], mode="markers", name="Selected outage", marker={"symbol": "diamond", "color": "#facc15", "size": 15}))
    fig.update_layout(height=590, xaxis_title="Grid X (m)", yaxis_title="Grid Y (m)", yaxis={"scaleanchor": "x"}, legend={"orientation": "h"})
    st.plotly_chart(fig, width="stretch")
with tabs[1]:
    fig = go.Figure(go.Surface(z=terrain.z, x=np.arange(terrain.z.shape[1])*terrain.dx, y=np.arange(terrain.z.shape[0])*terrain.dy,
                               surfacecolor=hazard["hazard"], colorscale="YlOrRd", colorbar={"title": "Hazard"}))
    for label, route in [("Nominal", nominal)] + [(f"Fallback {i+1}", r["route"]) for i, r in enumerate(options)]:
        p = route["position"]
        fig.add_trace(go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="lines", name=label, line={"width": 6}))
    fig.update_layout(height=620, legend={"orientation": "h", "y": -.12, "x": 0}, margin={"l": 0, "r": 25, "b": 65, "t": 25}, scene={"xaxis_title": "X (m)", "yaxis_title": "Y (m)", "zaxis_title": "Elevation (m)", "aspectmode": "data"})
    st.plotly_chart(fig, width="stretch")
with tabs[2]:
    frame = route_frame(nominal)
    st.line_chart(frame, x="time_s", y="clearance_m", x_label="Time (s)", y_label="Terrain clearance (m)")
    st.line_chart(frame, x="time_s", y="thrust_N", x_label="Time (s)", y_label="Required thrust (N)")
    st.dataframe(frame.iloc[sample_indices], hide_index=True, width="stretch")
with tabs[3]:
    st.write("Precompute fallback options for every blocked communication sample before touchdown (31 communication samples along the nominal descent).")
    if st.button("Precompute all sampled dropouts", disabled=not nominal["feasible"]):
        batch, coverage = {}, []
        blocked_steps = [int(s) for s in np.flatnonzero(comms == 0) if sample_indices[s] < len(nominal["t"])-1]
        bar = st.progress(0.)
        for n, s in enumerate(blocked_steps):
            idx = int(sample_indices[s])
            found, diag = fallback_cached(terrain, hazard, nominal, idx, vehicle)
            batch[str(idx)] = found
            coverage.append({"waypoint": idx, "time_s": float(nominal["t"][idx]), "options": len(found), "tested": diag["tested"], "rejections": diag["rejected"]})
            bar.progress((n+1)/len(blocked_steps))
        st.session_state["batch"], st.session_state["coverage"] = batch, coverage
        if not blocked_steps:
            st.info("No airborne blocked samples; use the manual outage selector to test contingencies.")
    if st.session_state["coverage"]:
        st.dataframe(st.session_state["coverage"], width="stretch")
    config["selected_outage_time_s"] = float(nominal["t"][index])
    st.download_button("Download mission bundle (.zip)", export_bundle(terrain, hazard, nominal, {**st.session_state["batch"], str(index): options}, config, st.session_state["coverage"]),
                       "echo-path-mission.zip", "application/zip")
    st.caption("Includes configuration, DEM crop, hazard layers, nominal telemetry, selected/precomputed fallback trajectories and coverage results.")
with tabs[4]:
    from pathlib import Path
    st.markdown(Path(__file__).with_name("MODEL_GUIDE.md").read_text(encoding="utf-8"))
    st.json(terrain.metadata)

st.subheader("Ranked fallbacks at the selected outage")
if options:
    st.dataframe([{k:v for k,v in o.items() if k != "route"} for o in options], hide_index=True, width="stretch")
else:
    st.warning("No fallback passed the checks at this waypoint." if nominal["feasible"] else "Fallback planning is disabled until the nominal trajectory passes the checks.")
with st.expander("Candidate rejection details"):
    st.json(diagnostics)
