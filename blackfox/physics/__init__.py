"""Pure physics / combustion functions (no I/O). The tools layer wraps these;
they can also be imported and unit-tested directly."""

from . import combustion, mechanics  # noqa: F401
from .constants import BODIES, G0, R_UNIVERSAL, SIGMA  # noqa: F401
