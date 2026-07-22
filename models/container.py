"""
Modello dati per il container.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config.defaults import CONTAINER_TYPES, GAP
from models.pallet import Pallet


@dataclass
class ContainerType:
    """Definizione di un tipo di container."""

    name: str
    internal_length: float  # mm
    internal_width: float   # mm
    internal_height: float  # mm
    door_width: float       # mm
    door_height: float      # mm

    @property
    def internal_volume(self) -> float:
        """Volume interno in mm³."""
        return self.internal_length * self.internal_width * self.internal_height

    def usable_length(self, gap: float = GAP) -> float:
        """Lunghezza utilizzabile considerando il gap su entrambi i lati."""
        return self.internal_length - 2 * gap

    def usable_width(self, gap: float = GAP) -> float:
        """Larghezza utilizzabile considerando il gap su entrambi i lati."""
        return self.internal_width - 2 * gap

    def usable_height(self, gap: float = GAP) -> float:
        """Altezza utilizzabile (gap solo in alto)."""
        return self.internal_height - gap

    def __repr__(self) -> str:
        return (
            f"ContainerType('{self.name}', "
            f"{self.internal_length}x{self.internal_width}x{self.internal_height}mm)"
        )


def get_container_type(name: str) -> ContainerType:
    """Ottiene un ContainerType dal nome."""
    data = CONTAINER_TYPES.get(name)
    if data is None:
        available = ", ".join(CONTAINER_TYPES.keys())
        raise ValueError(
            f"Tipo container '{name}' non trovato. Disponibili: {available}"
        )
    return ContainerType(**data)


def available_container_names() -> list[str]:
    """Restituisce i nomi dei container disponibili."""
    return list(CONTAINER_TYPES.keys())


@dataclass
class Container:
    """Container con bancali posizionati."""

    container_type: ContainerType
    pallets: list[Pallet] = field(default_factory=list)
    gap: float = GAP

    # ── Volume ────────────────────────────────

    @property
    def volume_total(self) -> float:
        """Volume interno totale (mm³)."""
        return self.container_type.internal_volume

    @property
    def volume_used(self) -> float:
        """Volume occupato dai bancali caricati (mm³)."""
        vol = 0.0
        for p in self.pallets:
            eff_l, eff_w = p.effective_footprint
            vol += eff_l * eff_w * p.total_height
        return vol

    @property
    def utilization_pct(self) -> float:
        """Percentuale di utilizzo del volume."""
        if self.volume_total == 0:
            return 0.0
        return (self.volume_used / self.volume_total) * 100.0

    # ── Query ─────────────────────────────────

    @property
    def pallet_count(self) -> int:
        return len(self.pallets)

    @property
    def total_panels(self) -> int:
        return sum(p.panel_count for p in self.pallets)

    def get_pallet_by_id(self, pallet_id: int) -> Optional[Pallet]:
        for p in self.pallets:
            if p.pallet_id == pallet_id:
                return p
        return None

    def all_order_ids(self) -> set[str]:
        """Tutti gli ordine_id presenti nel container."""
        ids = set()
        for p in self.pallets:
            ids.update(p.order_ids())
        return ids

    def has_solid_support(self, pallet: Pallet, min_support_pct: float = 0.80, max_allowed_void_mm: float = 300.0) -> bool:
        """
        Per un bancale posizionato a Z > 0 (su pianale), verifica che:
        1. Almeno il min_support_pct (80%) della sua superficie sia sostenuto da bancali di Primo Livello (Z = 0).
        2. L'eventuale spazio vuoto / campata non supportata tra bancali di sostegno adiacenti non superi 300 mm (30 cm).
        """
        if pallet.z <= 0.1:
            return True  # Sul pavimento è sempre sostenuto

        px1, px2, py1, py2 = pallet.collo_bbox_xy
        pallet_area = (px2 - px1) * (py2 - py1)
        if pallet_area <= 0:
            return False

        supported_area = 0.0
        supporting_pallets = []

        for other in self.pallets:
            if other.pallet_id == pallet.pallet_id:
                continue
            # Verifica che other sia al Livello 1 (z == 0) e che la sua altezza + 30mm coincida con la quota di appoggio
            if other.z <= 0.1 and abs((other.top_z + 30.0) - pallet.z) < 10.0:
                ox1, ox2, oy1, oy2 = other.collo_bbox_xy
                inter_x1 = max(px1, ox1)
                inter_x2 = min(px2, ox2)
                inter_y1 = max(py1, oy1)
                inter_y2 = min(py2, oy2)

                if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                    supported_area += inter_area
                    supporting_pallets.append((other, ox1, ox2, oy1, oy2))

        # 1. Controllo percentuale di superficie minima
        if (supported_area / pallet_area) < min_support_pct:
            return False

        # 2. Controllo campata/vuoto massimo tra bancali di supporto adiacenti (max 30 cm)
        if len(supporting_pallets) > 1:
            # Controllo campate lungo X
            by_x = sorted(supporting_pallets, key=lambda item: item[1])
            for i in range(len(by_x) - 1):
                ox2_curr = by_x[i][2]
                ox1_next = by_x[i+1][1]
                gap_x = ox1_next - ox2_curr
                if gap_x > max_allowed_void_mm:
                    return False

            # Controllo campate lungo Y
            by_y = sorted(supporting_pallets, key=lambda item: item[3])
            for i in range(len(by_y) - 1):
                oy2_curr = by_y[i][4]
                oy1_next = by_y[i+1][3]
                gap_y = oy1_next - oy2_curr
                if gap_y > max_allowed_void_mm:
                    return False

        return True

    # ── Validazione ───────────────────────────

    def is_valid_placement(self, pallet: Pallet) -> bool:
        """
        Verifica che un bancale sia posizionato validamente:
        - Dentro i limiti del container (con gap di sicurezza sulle misure massime reali)
        - Non sovrapposto ad altri bancali in 3D (misurato sui bounding box reali dei colli)
        - Sostenuto dalla gravità se al Livello 2
        """
        ct = self.container_type
        g = self.gap

        # Limiti 2D reali del collo (bancale + sporgenze ante)
        px1, px2, py1, py2 = pallet.collo_bbox_xy

        # Controllo limiti container con gap
        if px1 < g:
            return False
        if py1 < g:
            return False
        if px2 > ct.internal_length - g:
            return False
        if py2 > ct.internal_width - g:
            return False
        if pallet.top_z > ct.internal_height:
            return False

        # Controllo supporto gravitazionale se a Z > 0
        if pallet.z > 0.1:
            if not self.has_solid_support(pallet, min_support_pct=0.80):
                return False

        # Controllo sovrapposizione con altri bancali
        for other in self.pallets:
            if other.pallet_id == pallet.pallet_id:
                continue
            # Stesso livello (z simile): devono rispettare il gap di sicurezza in pianta
            if abs(pallet.z - other.z) < 10.0:
                if self._pallets_overlap_xy(pallet, other, g):
                    return False
            else:
                # Livelli diversi: se c'è sovrapposizione in pianta (anche senza gap), devono rispettare la compenetrazione Z
                if self._pallets_overlap_xy(pallet, other, gap=0.0):
                    if self._pallets_overlap_z(pallet, other):
                        return False
        return True

    def _pallets_overlap_xy(
        self, a: Pallet, b: Pallet, gap: float
    ) -> bool:
        """Verifica sovrapposizione in pianta usando i bounding box 2D reali dei colli."""
        ax1, ax2, ay1, ay2 = a.collo_bbox_xy
        bx1, bx2, by1, by2 = b.collo_bbox_xy

        x_overlap = (ax1 < bx2 + gap) and (ax2 + gap > bx1)
        y_overlap = (ay1 < by2 + gap) and (ay2 + gap > by1)
        return x_overlap and y_overlap

    def _pallets_overlap_z(self, a: Pallet, b: Pallet) -> bool:
        """Verifica sovrapposizione in altezza."""
        return a.z < b.top_z and a.top_z > b.z

    def __repr__(self) -> str:
        return (
            f"Container('{self.container_type.name}', "
            f"pallets={self.pallet_count}, "
            f"panels={self.total_panels}, "
            f"util={self.utilization_pct:.1f}%)"
        )
