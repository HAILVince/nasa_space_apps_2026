import math

from .constants import G0, MOLAR, O2_MOLE_FRACTION_AIR, SIGMA

AIR_MOLAR_MASS = 28.965  # g/mol


def stoichiometry(c: float, h: float, o: float = 0.0, n: float = 0.0) -> dict:
    """C_c H_h O_o N_n + a (O2 + 3.76 N2) -> c CO2 + h/2 H2O + ..."""
    if c < 0 or h < 0 or o < 0 or (c == 0 and h == 0):
        raise ValueError("need a fuel with carbon and/or hydrogen")
    a = c + h / 4 - o / 2
    if a <= 0:
        raise ValueError("this composition needs no oxygen")
    fuel_mw = c * MOLAR["C"] + h * MOLAR["H"] + o * MOLAR["O"] + n * MOLAR["N"]
    air_moles = a / O2_MOLE_FRACTION_AIR
    afr = air_moles * AIR_MOLAR_MASS / fuel_mw
    return {"o2_moles_per_mole_fuel": a, "air_moles_per_mole_fuel": air_moles,
            "fuel_molar_mass_g_mol": fuel_mw, "stoich_air_fuel_mass_ratio": afr,
            "stoich_fuel_mole_fraction_in_air": 1 / (1 + air_moles),
            "products_per_mole_fuel": {"CO2": c, "H2O": h / 2, "N2": a * 3.76 + n / 2}}


def equivalence_ratio(air_fuel_mass_ratio: float, stoich_air_fuel_mass_ratio: float) -> dict:
    phi = stoich_air_fuel_mass_ratio / air_fuel_mass_ratio
    return {"phi": phi, "mixture": "lean" if phi < 1 else "rich" if phi > 1 else "stoichiometric"}


def buoyant_velocity(length_m: float, flame_temp_k: float = 2000, ambient_temp_k: float = 300,
                     g: float = G0) -> dict:
    """Characteristic buoyant velocity U ~ sqrt(g L dT/T_ambient)."""
    if flame_temp_k <= ambient_temp_k:
        raise ValueError("flame must be hotter than ambient")
    u = math.sqrt(g * length_m * (flame_temp_k - ambient_temp_k) / ambient_temp_k)
    return {"velocity_m_s": u, "velocity_cm_s": u * 100, "g_m_s2": g}


def grashof(length_m: float, flame_temp_k: float = 2000, ambient_temp_k: float = 300,
            kinematic_viscosity_m2_s: float = 1.6e-5, g: float = G0) -> dict:
    """Gr = g * (dT/T) * L^3 / nu^2 (ideal gas, beta = 1/T)."""
    gr = g * ((flame_temp_k - ambient_temp_k) / ambient_temp_k) * length_m ** 3 / kinematic_viscosity_m2_s ** 2
    return {"grashof": gr, "regime": "buoyancy negligible" if gr < 1 else "buoyancy matters"}


def droplet_d2_law(d0_mm: float, k_mm2_s: float, time_s: float | None = None) -> dict:
    """d^2 = d0^2 - K t. Returns burnout time and (optionally) diameter at time_s."""
    if d0_mm <= 0 or k_mm2_s <= 0:
        raise ValueError("d0 and K must be positive")
    out = {"burnout_time_s": d0_mm ** 2 / k_mm2_s, "d0_mm": d0_mm, "k_mm2_s": k_mm2_s}
    if time_s is not None:
        d2 = d0_mm ** 2 - k_mm2_s * time_s
        out["diameter_at_time_mm"] = math.sqrt(d2) if d2 > 0 else 0.0
        out["time_s"] = time_s
    return out


def burning_rate_constant(transfer_number_b: float, gas_conductivity_w_mk: float = 0.07,
                          liquid_density_kg_m3: float = 680, gas_cp_j_kgk: float = 1200) -> dict:
    """Classical K = 8 k_g / (rho_l cp_g) * ln(1+B), in mm^2/s. Defaults ~ heptane-ish."""
    k = 8 * gas_conductivity_w_mk / (liquid_density_kg_m3 * gas_cp_j_kgk) * math.log(1 + transfer_number_b)
    return {"k_m2_s": k, "k_mm2_s": k * 1e6}


def damkohler(flow_time_s: float, chemical_time_s: float) -> dict:
    da = flow_time_s / chemical_time_s
    return {"damkohler": da, "meaning": "chemistry fast vs flow (flame can survive)" if da > 1
            else "chemistry slow vs flow (extinction likely)"}


def lewis_number(thermal_diffusivity_m2_s: float, mass_diffusivity_m2_s: float) -> dict:
    le = thermal_diffusivity_m2_s / mass_diffusivity_m2_s
    return {"lewis": le, "note": "Le < 1: fuel diffuses faster than heat (flame balls, cellular flames possible)"
            if le < 1 else "Le >= 1: heat diffuses at least as fast as fuel"}


def radiative_loss(temperature_k: float, ambient_k: float = 300, emissivity: float = 1.0,
                   area_m2: float = 1.0) -> dict:
    q = emissivity * SIGMA * (temperature_k ** 4 - ambient_k ** 4)
    return {"heat_flux_w_m2": q, "power_w": q * area_m2}


def adiabatic_flame_temp_estimate(heat_of_combustion_mj_kg: float, air_fuel_mass_ratio: float,
                                  initial_temp_k: float = 298, mean_cp_j_kgk: float = 1200) -> dict:
    """Constant-cp estimate T_ad = T0 + LHV / ((1 + AFR) cp). Ignores dissociation, so it
    overpredicts above ~2200 K."""
    dt = heat_of_combustion_mj_kg * 1e6 / ((1 + air_fuel_mass_ratio) * mean_cp_j_kgk)
    return {"t_ad_k": initial_temp_k + dt, "note": "constant-cp estimate, no dissociation (upper bound)"}
