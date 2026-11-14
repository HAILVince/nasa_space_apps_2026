import math

from .constants import BODIES, G0


def body(name: str) -> dict:
    key = name.strip().lower()
    if key not in BODIES:
        raise ValueError(f"unknown body '{name}'; known: {', '.join(BODIES)}")
    return BODIES[key]


def free_fall(height_m: float, g: float = G0) -> dict:
    """Drop from rest, no drag: time, impact speed."""
    if height_m <= 0 or g <= 0:
        raise ValueError("height and g must be positive")
    t = math.sqrt(2 * height_m / g)
    return {"time_s": t, "final_velocity_m_s": g * t, "height_m": height_m, "g_m_s2": g}


def drop_height_for_time(time_s: float, g: float = G0) -> dict:
    if time_s <= 0:
        raise ValueError("time must be positive")
    return {"height_m": 0.5 * g * time_s ** 2, "time_s": time_s, "g_m_s2": g}


def parabolic_flight_time(entry_speed_m_s: float, pitch_deg: float, g: float = G0) -> dict:
    """Duration of a free-fall (Keplerian) parabola entered at speed v and pitch angle."""
    vz = entry_speed_m_s * math.sin(math.radians(pitch_deg))
    if vz <= 0:
        raise ValueError("pitch must be above the horizon")
    return {"free_fall_time_s": 2 * vz / g, "apex_height_gain_m": vz ** 2 / (2 * g)}


def orbit(altitude_km: float, body_name: str = "earth") -> dict:
    b = body(body_name)
    r = b["radius"] + altitude_km * 1000
    v = math.sqrt(b["gm"] / r)
    period = 2 * math.pi * r / v
    g_local = b["gm"] / r ** 2
    return {"orbital_speed_m_s": v, "period_min": period / 60, "local_gravity_m_s2": g_local,
            "local_gravity_fraction_of_surface": g_local / b["g"],
            "note": "objects in orbit are in free fall: gravity is still ~this strong, but everything falls together"}


def gravity_compare(body_name: str) -> dict:
    b = body(body_name)
    return {"body": body_name.lower(), "surface_gravity_m_s2": b["g"], "fraction_of_earth": b["g"] / G0}
