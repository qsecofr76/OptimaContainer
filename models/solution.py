"""
Modello dati per una soluzione di caricamento.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.container import Container


@dataclass
class Solution:
    """Una soluzione completa di caricamento container."""

    container: Container
    score: float = 0.0
    scores_detail: dict[str, float] = field(default_factory=dict)
    iteration: int = 0
    generation_time_s: float = 0.0
    # Pannelli non caricati (non entrano nel container)
    unplaced_panel_ids: list[int] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """True se tutti i pannelli sono stati caricati."""
        return len(self.unplaced_panel_ids) == 0

    @property
    def utilization_pct(self) -> float:
        return self.container.utilization_pct

    @property
    def pallet_count(self) -> int:
        return self.container.pallet_count

    @property
    def panel_count(self) -> int:
        return self.container.total_panels

    @property
    def total_order_panels(self) -> int:
        """Totale pannelli presenti nell'ordine originale."""
        return self.panel_count + len(self.unplaced_panel_ids)

    @property
    def placed_pct(self) -> float:
        """Percentuale di pannelli caricati rispetto al totale dell'ordine."""
        tot = self.total_order_panels
        return (self.panel_count / tot * 100.0) if tot > 0 else 100.0

    def summary(self) -> str:
        """Riepilogo testuale della soluzione."""
        tot_order = self.total_order_panels
        pct_str = f" ({self.placed_pct:.1f}%)" if tot_order > 0 else ""
        lines = [
            f"== Soluzione #{self.iteration} ==",
            f"  Container: {self.container.container_type.name}",
            f"  Bancali:   {self.pallet_count}",
            f"  Pannelli:  {self.panel_count} / {tot_order}{pct_str}",
            f"  Utilizzo:  {self.utilization_pct:.1f}%",
            f"  Score:     {self.score:.4f}",
        ]
        if self.scores_detail:
            lines.append("  Dettaglio:")
            for k, v in self.scores_detail.items():
                lines.append(f"    {k}: {v:.4f}")
        if self.unplaced_panel_ids:
            lines.append(
                f"  [!] Pannelli non caricati: {len(self.unplaced_panel_ids)}"
            )
        return "\n".join(lines)

    def __lt__(self, other: "Solution") -> bool:
        return self.score < other.score

    def __repr__(self) -> str:
        return (
            f"Solution(iter={self.iteration}, score={self.score:.4f}, "
            f"pallets={self.pallet_count}, util={self.utilization_pct:.1f}%)"
        )
