# Data and model guide

## Real-region inputs

Provide a cropped LOLA lunar GeoTIFF, its projection and elevation units, and any scale/offset or nodata documentation. A raw PDS IMG needs its matching LBL and conversion to projected GeoTIFF before import. The app accepts north-up, unrotated, metre-based projected rasters. Geographic degree grids must first be reprojected with the appropriate lunar CRS. The app asks you to confirm that the source is lunar; projected Earth data are not a substitute.

Optional mission data: lander dry mass, propellant mass, thrust limit, specific impulse, initial position/velocity, and Earth/relay/Sun directions at the chosen epoch. Until these are provided, the defaults are illustrative test parameters.

Local coordinates use projected grid north, which can differ from geographic north near the poles; convert supplied directions accordingly. Elevation values retain the DEM datum. Band scale and offset are applied before the selected metres/kilometres conversion. Crops retain native resolution and are limited to 240 pixels per side in the UI and a 10 km region. No resampling hides hazards. Missing cells reject routes, and landing neighbourhoods touching missing data or map edges are excluded. Coarse LOLA cells cannot resolve lander-sized rocks.

## Terrain and illumination

Slope uses metre-scaled gradients. Roughness is RMS departure from a local fitted plane across an odd-sized neighbourhood at least three cells wide. Optional Sun raycasting excludes shaded or unknown sites. Thresholds are absolute, not terrain percentiles. Landing eligibility requires slope and roughness below their limits throughout the landing footprint; hazard ranks the remaining sites.

## Dynamics and routing

Descent uses cubic position guidance with analytical velocity/acceleration and zero terminal speed. Required thrust includes constant lunar gravity (1.62 m/s²); mass is integrated as m(t)=m(0) exp(-integral(|a-g| dt)/(Isp g0)), with g0=9.80665 m/s². This implements the point-mass force and propellant relationships, but evaluates commanded trajectories rather than integrating a saturated controller. Required thrust/fuel above the limits, downward thrust, excursions outside known terrain and terrain collisions reject a route. Samples are spaced at most 0.5 seconds and conservatively at most half a cell of travel. Checks are sampled, not a continuous collision proof.

Fallbacks start with the actual selected position, velocity and remaining mass. Search tests up to 16 spatially separated eligible sites at three durations (0.8, 1.0 and 1.25 times remaining nominal time, minimum 4 seconds). It ranks accepted polynomial trajectories by hazard plus 0.4 times the remaining fuel fraction consumed. It is not A* or a global optimizer. No result means none of these candidates passed, not proof of unreachability. Touchdown speed is a boundary condition, not a separately simulated landing controller. There are no attitude, tilt, throttle, gimbal or acceleration-change constraints beyond the displayed checks.

## Communication and coverage

Communication uses static directions and ray-terrain intersections inside the tile. Azimuth is clockwise from grid north. Directions at or below the local horizon are treated as blocked by this flat local model. Clear means locally unobstructed only; terrain beyond the tile remains unknown. Missing terrain along a ray yields unknown unless a known obstacle blocks it. Rays are sampled at half the smaller cell spacing.

Coverage evaluates 31 nominal communication samples, not every continuous instant. Precomputation handles airborne blocked samples and explicitly reports samples with no passing fallback. A manually selected clear sample can also be used to inject an outage. Touchdown cannot initiate a new descent. Changes to mission parameters or terrain clear stored coverage to prevent stale results.

Lunar curvature, ephemerides, radio link budget, terrain uncertainty and navigation errors are not modeled. These are research demonstrations, not flight-qualified plans. Communication loss is a contingency trigger and is not assumed to imply navigation failure.

## Export

The ZIP contains mission configuration and terrain metadata, cropped elevation and hazard CSV grids, nominal state/thrust/mass samples, ranked fallback trajectories, and coverage results. Grid row 0 is south; local X/Y and elevations are in metres. Each trajectory's time starts at zero; the outage time is recorded separately. Imported raster metadata includes the source crop transform and southwest pixel centre for mapping back to projected coordinates.

## References

- [NASA: specific impulse and propellant flow](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/)
- [NASA: ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/)
- [Rasterio: dataset metadata, scale/offset and masked reads](https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html)
