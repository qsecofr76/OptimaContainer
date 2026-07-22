"""
Modello dati per il bancale EPAL e la disposizione dei pannelli su di esso.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from config.defaults import (
    EPAL_HEIGHT,
    EPAL_LENGTH,
    EPAL_WIDTH,
    MAX_PALLET_LOAD_HEIGHT,
)
from models.panel import Panel

_pallet_counter = itertools.count(1)


@dataclass
class PanelPlacement:
    """Un pannello posizionato su un layer del bancale."""

    panel: Panel
    x: float = 0.0       # posizione X sulla superficie del bancale (mm)
    y: float = 0.0       # posizione Y sulla superficie del bancale (mm)
    rotated: bool = False  # se True, larghezza e profondità sono scambiate

    @property
    def effective_width(self) -> float:
        """Larghezza effettiva considerando la rotazione."""
        return self.panel.profondita_mm if self.rotated else self.panel.larghezza_mm

    @property
    def effective_depth(self) -> float:
        """Profondità effettiva considerando la rotazione."""
        return self.panel.larghezza_mm if self.rotated else self.panel.profondita_mm

    @property
    def x_end(self) -> float:
        return self.x + self.effective_width

    @property
    def y_end(self) -> float:
        return self.y + self.effective_depth


@dataclass
class PalletLayer:
    """Uno strato (fila) di pannelli posati in piatto su un bancale."""

    placements: list[PanelPlacement] = field(default_factory=list)
    z_offset: float = 0.0  # altezza dal piano del bancale (mm)

    @property
    def thickness(self) -> float:
        """Spessore dello strato (= max spessore dei pannelli nello strato)."""
        if not self.placements:
            return 0.0
        return max(p.panel.spessore_mm for p in self.placements)

    @property
    def footprint_width(self) -> float:
        """Larghezza complessiva occupata (lungo l'asse X)."""
        if not self.placements:
            return 0.0
        return max(p.x_end for p in self.placements)

    @property
    def footprint_depth(self) -> float:
        """Profondità complessiva occupata (lungo l'asse Y)."""
        if not self.placements:
            return 0.0
        return max(p.y_end for p in self.placements)

    @property
    def panel_count(self) -> int:
        return len(self.placements)


@dataclass
class Pallet:
    """
    Bancale EPAL con pannelli caricati.

    Supporta bancale singolo (1200×800) o doppio (2400×800)
    per pannelli molto lunghi.
    """

    pallet_id: int = field(default_factory=lambda: next(_pallet_counter))
    n_epal: int = 1               # 1 = singolo, 2 = doppio (in tandem)
    layers: list[PalletLayer] = field(default_factory=list)
    rotated: bool = False          # rotazione nel container (0° o 90°)

    # Posizione nel container (mm)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # Sovrapposizione
    stacked_on: Optional[int] = None  # pallet_id del bancale sottostante
    has_pianale_below: bool = False    # se questo bancale poggia su un pianale

    # ── Dimensioni base ──────────────────────────

    @property
    def base_length(self) -> float:
        """Lunghezza base del bancale (asse X nel container se non ruotato)."""
        raw = EPAL_LENGTH * self.n_epal
        return EPAL_WIDTH if self.rotated else raw

    @property
    def base_width(self) -> float:
        """Larghezza base del bancale (asse Y nel container se non ruotato)."""
        raw = EPAL_LENGTH * self.n_epal
        return raw if self.rotated else EPAL_WIDTH

    @property
    def pallet_height(self) -> float:
        """Altezza struttura pallet EPAL (mm)."""
        return EPAL_HEIGHT

    # ── Altezze di carico ────────────────────────

    @property
    def load_height(self) -> float:
        """Altezza totale dei pannelli caricati (senza il pallet)."""
        if not self.layers:
            return 0.0
        last = self.layers[-1]
        return last.z_offset + last.thickness

    @property
    def total_height(self) -> float:
        """Altezza totale: pallet + carico."""
        return self.pallet_height + self.load_height

    @property
    def remaining_height(self) -> float:
        """Spazio rimanente prima di raggiungere MAX_PALLET_LOAD_HEIGHT."""
        return max(0.0, MAX_PALLET_LOAD_HEIGHT - self.total_height)

    # ── Ingombro effettivo ───────────────────────

    @property
    def local_collo_extent(self) -> tuple[float, float, float, float]:
        """Calcola l'estensione 2D locale (min_x, max_x, min_y, max_y) slegata dalla posizione nel container."""
        if hasattr(self, "_cached_local_extent"):
            return self._cached_local_extent

        raw_l = EPAL_LENGTH * self.n_epal
        raw_w = EPAL_WIDTH

        if self.layers:
            first_ly = self.layers[0]
            pallet_ox = (first_ly.footprint_width - raw_l) / 2
            pallet_oy = (first_ly.footprint_depth - raw_w) / 2
        else:
            pallet_ox = 0.0
            pallet_oy = 0.0

        min_x, max_x = pallet_ox, pallet_ox + raw_l
        min_y, max_y = pallet_oy, pallet_oy + raw_w

        cum_ox, cum_oy = 0.0, 0.0
        for i, ly in enumerate(self.layers):
            if i > 0:
                prev_ly = self.layers[i - 1]
                cum_ox += (prev_ly.footprint_width - ly.footprint_width) / 2
                cum_oy += (prev_ly.footprint_depth - ly.footprint_depth) / 2

            lx1, lx2 = cum_ox, cum_ox + ly.footprint_width
            ly1, ly2 = cum_oy, cum_oy + ly.footprint_depth

            min_x, max_x = min(min_x, lx1), max(max_x, lx2)
            min_y, max_y = min(min_y, ly1), max(max_y, ly2)

        self._cached_local_extent = (min_x, max_x, min_y, max_y)
        return self._cached_local_extent

    @property
    def collo_bbox_xy(self) -> tuple[float, float, float, float]:
        """
        Restituisce i limiti 2D reali dell'intero collo (bancale di legno + ante sporgenti):
        (x_min, x_max, y_min, y_max) in coordinate container.
        """
        min_lx, max_lx, min_ly, max_ly = self.local_collo_extent

        if not self.rotated:
            return (self.x + min_lx, self.x + max_lx, self.y + min_ly, self.y + max_ly)
        else:
            return (self.x + min_ly, self.x + max_ly, self.y + min_lx, self.y + max_lx)

    @property
    def effective_footprint(self) -> tuple[float, float]:
        """
        Ingombro effettivo in pianta considerando le sporgenze reali dei pannelli.
        Restituisce (lunghezza_effettiva, larghezza_effettiva).
        """
        x1, x2, y1, y2 = self.collo_bbox_xy
        return (x2 - x1, y2 - y1)

    # ── Query su pannelli ────────────────────────

    def all_panels(self) -> list[Panel]:
        """Tutti i pannelli caricati su questo bancale."""
        panels = []
        for layer in self.layers:
            for placement in layer.placements:
                panels.append(placement.panel)
        return panels

    @property
    def panel_count(self) -> int:
        return sum(layer.panel_count for layer in self.layers)

    def order_ids(self) -> set[str]:
        """Set di ordine_id presenti su questo bancale."""
        return {p.ordine_id for p in self.all_panels() if p.ordine_id}

    # ── Verifica impilabilità ────────────────────

    def can_stack_pallet_on_top(self) -> bool:
        """
        Verifica se è possibile impilare un altro bancale sopra.
        Condizione: la larghezza/profondità totale dei pannelli
        dell'ultimo strato deve essere >= larghezza EPAL (800mm).
        """
        if not self.layers:
            return False
        top_layer = self.layers[-1]
        # La copertura deve essere almeno quanto un EPAL
        covers_width = top_layer.footprint_width >= EPAL_WIDTH
        covers_depth = top_layer.footprint_depth >= EPAL_WIDTH
        return covers_width or covers_depth

    def can_form_pianale_with(self, other: "Pallet") -> bool:
        """
        Verifica se questo bancale e un altro possono formare
        un pianale (stessa altezza totale).
        """
        return abs(self.total_height - other.total_height) < 5.0  # tolleranza 5mm

    @property
    def top_z(self) -> float:
        """Quota Z del punto più alto del bancale caricato."""
        return self.z + self.total_height

    def __repr__(self) -> str:
        return (
            f"Pallet(id={self.pallet_id}, {self.n_epal}xEPAL, "
            f"panels={self.panel_count}, "
            f"h={self.total_height:.0f}mm, "
            f"pos=({self.x:.0f},{self.y:.0f},{self.z:.0f}))"
        )


def reset_pallet_counter() -> None:
    """Resetta il contatore globale dei bancali (utile per i test)."""
    global _pallet_counter
    _pallet_counter = itertools.count(1)
