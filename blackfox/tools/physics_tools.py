"""Physics / combustion calculation tools over blackfox.physics. SI units unless
the parameter name says otherwise. Each returns a dict of results."""

from ..physics import combustion as c
from ..physics import mechanics as m
from ..physics.constants import BODIES, G0, MICROGRAVITY_LEVELS
from .registry import tool


def _safe(fn, *a, **kw) -> dict:
    try:
        return fn(*a, **kw)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        return {"error": str(e)}


@tool("physics")
def free_fall_time(height_m: float, body: str = "earth") -> dict:
    """Free-fall (microgravity) time and impact speed for a drop from height_m, no drag.
    Use for drop towers: e.g. 132 m on Earth -> ~5.18 s. body: earth, moon, mars, ..."""
    g = BODIES.get(body.lower(), {}).get("g")
    if g is None:
        return {"error": f"unknown body; known: {', '.join(BODIES)}"}
    return _safe(m.free_fall, height_m, g)


@tool("physics")
def drop_height_for_duration(time_s: float) -> dict:
    """Drop height (on Earth, no drag) needed for a given microgravity duration."""
    return _safe(m.drop_height_for_time, time_s, G0)


@tool("physics")
def parabolic_flight(entry_speed_m_s: float, pitch_deg: float) -> dict:
    """Free-fall duration and altitude gain of a parabolic (reduced-gravity) flight
    entered at entry_speed_m_s and pitch angle pitch_deg."""
    return _safe(m.parabolic_flight_time, entry_speed_m_s, pitch_deg)


@tool("physics")
def orbit_info(altitude_km: float, body: str = "earth") -> dict:
    """Circular orbit speed, period and local gravity at an altitude (ISS ~ 400 km).
    Shows why astronauts float: gravity is ~90% of surface value, but they are in free fall."""
    return _safe(m.orbit, altitude_km, body)


@tool("physics")
def gravity_levels() -> dict:
    """Surface gravity of solar-system bodies and typical residual-acceleration levels of
    microgravity platforms (ISS, drop tower, parabolic flight, sounding rocket), in g0."""
    return {"bodies_m_s2": {k: v["g"] for k, v in BODIES.items()},
            "microgravity_platforms_fraction_of_g0": MICROGRAVITY_LEVELS}


@tool("physics")
def fuel_stoichiometry(carbon: float, hydrogen: float, oxygen: float = 0, nitrogen: float = 0) -> dict:
    """Stoichiometric combustion of a fuel C_c H_h O_o N_n in air: O2 needed, air-fuel mass
    ratio, fuel mole fraction. Heptane = (7, 16), methanol = (1, 4, 1), methane = (1, 4)."""
    return _safe(c.stoichiometry, carbon, hydrogen, oxygen, nitrogen)


@tool("physics")
def buoyant_flow_velocity(length_m: float, flame_temp_k: float = 2000, ambient_temp_k: float = 300,
                          gravity_m_s2: float = G0) -> dict:
    """Characteristic buoyancy-driven flow speed near a flame, U ~ sqrt(g L dT/T). Compare
    gravity_m_s2=9.81 with 9.81e-6 (ISS) to see why flames become spherical in orbit."""
    return _safe(c.buoyant_velocity, length_m, flame_temp_k, ambient_temp_k, gravity_m_s2)


@tool("physics")
def grashof_number(length_m: float, flame_temp_k: float = 2000, ambient_temp_k: float = 300,
                   kinematic_viscosity_m2_s: float = 1.6e-5, gravity_m_s2: float = G0) -> dict:
    """Grashof number (buoyancy vs viscosity) for a flame of size length_m."""
    return _safe(c.grashof, length_m, flame_temp_k, ambient_temp_k, kinematic_viscosity_m2_s, gravity_m_s2)


@tool("physics")
def droplet_burning(d0_mm: float, k_mm2_s: float, time_s: float = -1) -> dict:
    """d-squared law: burnout time of a droplet with initial diameter d0_mm and burning-rate
    constant k_mm2_s (hydrocarbons ~0.5-1 mm^2/s); if time_s >= 0 also the diameter then."""
    return _safe(c.droplet_d2_law, d0_mm, k_mm2_s, None if time_s < 0 else time_s)


@tool("physics")
def droplet_burning_rate_constant(transfer_number_b: float, gas_conductivity_w_mk: float = 0.07,
                                  liquid_density_kg_m3: float = 680, gas_cp_j_kgk: float = 1200) -> dict:
    """Classical burning-rate constant K = 8 k/(rho_l cp) ln(1+B) from the Spalding transfer number."""
    return _safe(c.burning_rate_constant, transfer_number_b, gas_conductivity_w_mk,
                 liquid_density_kg_m3, gas_cp_j_kgk)


@tool("physics")
def damkohler_number(flow_time_s: float, chemical_time_s: float) -> dict:
    """Damkohler number Da = flow time / chemical time; Da < ~1 suggests extinction."""
    return _safe(c.damkohler, flow_time_s, chemical_time_s)


@tool("physics")
def lewis_number(thermal_diffusivity_m2_s: float, mass_diffusivity_m2_s: float) -> dict:
    """Lewis number Le = thermal / mass diffusivity (explains flame balls when Le < 1)."""
    return _safe(c.lewis_number, thermal_diffusivity_m2_s, mass_diffusivity_m2_s)


@tool("physics")
def radiative_heat_loss(temperature_k: float, ambient_k: float = 300, emissivity: float = 1.0,
                        area_m2: float = 1.0) -> dict:
    """Stefan-Boltzmann radiative loss from a hot surface/flame zone - the loss that
    extinguishes large droplets and weak flames in microgravity."""
    return _safe(c.radiative_loss, temperature_k, ambient_k, emissivity, area_m2)


@tool("physics")
def adiabatic_flame_temperature(heat_of_combustion_mj_kg: float, air_fuel_mass_ratio: float,
                                initial_temp_k: float = 298, mean_cp_j_kgk: float = 1200) -> dict:
    """Rough constant-cp adiabatic flame temperature (upper bound, no dissociation)."""
    return _safe(c.adiabatic_flame_temp_estimate, heat_of_combustion_mj_kg, air_fuel_mass_ratio,
                 initial_temp_k, mean_cp_j_kgk)


@tool("physics")
def simulate_cabin_fire(environment: str = "leo", location: str = "avionics_rack", material: str = "",
                        pressure_kpa: float = -1, o2_pct: float = -1, temp_c: float = -1, vent_cm_s: float = 12,
                        suppression: str = "co2", response_s: float = 60, auto_vent_shutdown: bool = True,
                        duration_s: float = 480) -> dict:
    """Fire-safety screening of one cabin fire (Black Fox fire lab). environment: leo, lunar_orbit,
    moon, mars, earth. location: avionics_rack, crew_quarters, galley,
    glovebox. material: ptfe_wire, nomex, silicone, polyethylene, nylon, pet_film, ultem, delrin,
    viton, kydex (empty = the location's default). Atmosphere values < 0 use the environment's
    default (ISS 101.4 kPa/21 %, Gateway 70.3/26.5, Moon and Mars 56.5/34). Returns the NASA-STD-6001
    MOC at that pressure, the gravity/flow corrected limit, the oxygen margin, spread rate, peak heat
    release, CO, alarm and extinguishment times and a risk level. suppression: none, co2, water_mist.
    auto_vent_shutdown: the crew switches the ventilation off at the alarm (true) or not (false).
    duration_s: simulated time. This is a what-if run: it does NOT change the user's lab; use
    set_fire_scenario for that (fire_scenario_options lists every valid value)."""
    from ..physics import fire
    try:
        r = fire.simulate(environment=environment, material=material or None, location=location,
                          pressure_kpa=None if pressure_kpa < 0 else pressure_kpa,
                          o2_pct=None if o2_pct < 0 else o2_pct, temp_c=None if temp_c < 0 else temp_c,
                          vent_cm_s=vent_cm_s, auto_vent_shutdown=auto_vent_shutdown, suppression=suppression,
                          response_s=response_s, duration_s=duration_s)
    except ValueError as e:
        return {"error": str(e)}
    r.pop("series")
    return r
