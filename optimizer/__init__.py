"""
Motore di ottimizzazione per OptimaContainer.
"""
from .pallet_packer import pack_panels_to_pallets
from .container_packer import pack_pallets_in_container
from .stacking import apply_stacking, get_stacking_points
from .genetic import run_genetic_algorithm

__all__ = [
    "pack_panels_to_pallets",
    "pack_pallets_in_container",
    "apply_stacking",
    "get_stacking_points",
    "run_genetic_algorithm"
]
