from dataclasses import dataclass, asdict
import numpy as np
from scipy.integrate import cumulative_trapezoid


@dataclass(frozen=True)
class Vehicle:
    dry_mass: float = 700.
    fuel: float = 300.
    max_thrust: float = 5000.
    isp: float = 310.
    gravity: float = 1.62
    g0: float = 9.80665


def trajectory(terrain, start, velocity, destination, duration, mass, vehicle):
    """Cubic position guidance, analytic derivatives, integrated required propellant.

    Endpoint is stationary at terrain contact. This evaluates required control;
    infeasible control is reported, never clamped and presented as flyable.
    """
    if duration <= 0 or mass <= 0 or min(vehicle.isp, vehicle.max_thrust, vehicle.dry_mass) <= 0:
        raise ValueError('Duration, mass, thrust and specific impulse must be positive.')
    p0, v0, end = np.asarray(start, float), np.asarray(velocity, float), np.asarray(destination, float)
    T = float(duration)
    a = (3*(end-p0)-2*v0*T)/T**2
    b = (2*(p0-end)+v0*T)/T**3
    # Sample at <=0.5 s and <= half a cell of conservative polynomial travel bound.
    bound = (np.linalg.norm(v0)+2*np.linalg.norm(a)*T+3*np.linalg.norm(b)*T*T)*T
    samples = max(121, int(np.ceil(T/.5))+1, int(np.ceil(bound/(min(terrain.dx, terrain.dy)/2)))+1)
    if samples > 15000:
        raise ValueError('Trajectory exceeds prototype sampling budget; reduce duration or region size.')
    t = np.linspace(0, T, samples)
    pos = p0 + t[:, None]*v0 + t[:, None]**2*a + t[:, None]**3*b
    vel = v0 + 2*t[:, None]*a + 3*t[:, None]**2*b
    acc = 2*a + 6*t[:, None]*b
    specific = np.linalg.norm(acc + [0, 0, vehicle.gravity], axis=1)
    dv = cumulative_trapezoid(specific, t, initial=0)
    masses = mass*np.exp(-dv/(vehicle.isp*vehicle.g0))
    thrust = specific*masses
    ground = terrain.sample(pos[:, 0], pos[:, 1])
    clearance = pos[:, 2]-ground
    reasons = []
    if not np.isfinite(ground).all(): reasons.append('Route leaves known terrain')
    if np.any(clearance < -1e-4): reasons.append('Terrain collision')
    if masses[-1] < vehicle.dry_mass: reasons.append('Insufficient fuel')
    if thrust.max() > vehicle.max_thrust: reasons.append('Thrust limit exceeded')
    if np.any((acc + [0, 0, vehicle.gravity])[:, 2] < -1e-6): reasons.append('Requires downward thrust')
    return {'t': t, 'position': pos, 'velocity': vel, 'mass': masses, 'thrust': thrust,
            'clearance': clearance, 'delta_v': float(dv[-1]), 'fuel_used': float(mass-masses[-1]),
            'peak_thrust': float(thrust.max()), 'feasible': not reasons, 'reasons': reasons}


def config_dict(vehicle):
    return asdict(vehicle)
