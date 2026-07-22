"""
Modello dati per un'anta o fianco.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

_panel_counter = itertools.count(1)


@dataclass
class Panel:
    """Un singolo pannello (anta o fianco) da caricare."""

    codice_modello: str
    larghezza_mm: float   # dimensione 1 (tipicamente la più corta)
    profondita_mm: float  # dimensione 2 (tipicamente la più lunga)
    spessore_mm: float    # spessore (altezza quando posato in piatto)
    ordine_id: str = ""
    panel_id: int = field(default_factory=lambda: next(_panel_counter))

    # ── Proprietà derivate ──────────────────────

    @property
    def min_dim(self) -> float:
        """Dimensione minore del pannello."""
        return min(self.larghezza_mm, self.profondita_mm)

    @property
    def max_dim(self) -> float:
        """Dimensione maggiore del pannello."""
        return max(self.larghezza_mm, self.profondita_mm)

    @property
    def area(self) -> float:
        """Area della faccia del pannello (mm²)."""
        return self.larghezza_mm * self.profondita_mm

    @property
    def volume(self) -> float:
        """Volume del pannello (mm³)."""
        return self.area * self.spessore_mm

    def __repr__(self) -> str:
        return (
            f"Panel(id={self.panel_id}, model='{self.codice_modello}', "
            f"{self.larghezza_mm}x{self.profondita_mm}x{self.spessore_mm}mm, "
            f"ordine='{self.ordine_id}')"
        )


def reset_panel_counter() -> None:
    """Resetta il contatore globale dei pannelli (utile per i test)."""
    global _panel_counter
    _panel_counter = itertools.count(1)
