G0 = 9.80665               # standard gravity, m/s^2
SIGMA = 5.670374419e-8     # Stefan-Boltzmann, W/(m^2 K^4)
R_UNIVERSAL = 8.314462618  # J/(mol K)
G_NEWTON = 6.67430e-11     # m^3/(kg s^2)

# surface gravity (m/s^2), mean radius (m), GM (m^3/s^2)
BODIES = {
    "earth":   {"g": 9.80665, "radius": 6.371e6, "gm": 3.986004418e14},
    "moon":    {"g": 1.625,   "radius": 1.7374e6, "gm": 4.9048695e12},
    "mars":    {"g": 3.7207,  "radius": 3.3895e6, "gm": 4.282837e13},
    "venus":   {"g": 8.87,    "radius": 6.0518e6, "gm": 3.24859e14},
    "mercury": {"g": 3.70,    "radius": 2.4397e6, "gm": 2.2032e13},
    "jupiter": {"g": 24.79,   "radius": 6.9911e7, "gm": 1.26686534e17},
    "titan":   {"g": 1.352,   "radius": 2.5747e6, "gm": 8.978e12},
}

# typical residual acceleration levels, as a fraction of g0
MICROGRAVITY_LEVELS = {
    "iss": 1e-6,               # quasi-steady, order of magnitude (vibration adds more)
    "drop_tower": 1e-5,        # order of magnitude, depends on facility
    "parabolic_flight": 1e-2,  # g-jitter, order of magnitude
    "sounding_rocket": 1e-4,
}

# molar masses, g/mol
MOLAR = {"C": 12.011, "H": 1.008, "O": 15.999, "N": 14.007}
O2_MOLE_FRACTION_AIR = 0.2095
