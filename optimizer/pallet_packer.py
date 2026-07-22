"""
Algoritmo per imballare i pannelli sui bancali EPAL.

I pannelli vengono disposti in piatto su bancali EPAL (singoli 1200x800 o
doppi 2400x800). Ogni bancale ha più strati (layers/file) impilati.
La disposizione rispetta la regola piramidale e i limiti di sporgenza.
"""
import time
import random
from typing import List, Tuple, Optional

from config.defaults import (
    EPAL_LENGTH, EPAL_WIDTH, EPAL_HEIGHT,
    MAX_PALLET_LOAD_HEIGHT,
    OVERHANG_LONG_SIDE_PCT, OVERHANG_SHORT_SIDE_PCT,
)
from models.panel import Panel
from models.pallet import Pallet, PalletLayer, PanelPlacement


# ──────────────────────────────────────────────────────────
#  Utilità: calcolo dimensioni massime e adattamento
# ──────────────────────────────────────────────────────────

def _max_surface(n_epal: int) -> Tuple[float, float]:
    """
    Superficie massima ammessa su un bancale (singolo o doppio)
    considerando le sporgenze massime.
    
    Per il lato lungo (EPAL_LENGTH * n_epal):
        sporgenza max = 30% della dimensione minore del pannello.
        Poiché non conosciamo il pannello in anticipo, usiamo un valore
        generoso e controlliamo per-pannello al posizionamento.
    
    Per il lato corto (EPAL_WIDTH = 800mm):
        sporgenza max = 60% della dimensione maggiore del pannello.
        Stesso ragionamento.
    
    Qui restituiamo la superficie BASE (senza overhang).
    L'overhang è gestito per-pannello in _panel_fits.
    """
    return (EPAL_LENGTH * n_epal, EPAL_WIDTH)


def _needs_double_epal(panel: Panel) -> bool:
    """
    Un pannello necessita di 2 EPAL in tandem se nessuna delle sue
    dimensioni entra nel singolo EPAL + sporgenza consentita.
    """
    base_l = EPAL_LENGTH
    base_w = EPAL_WIDTH
    # Sporgenza lato lungo: 30% della dim minore del pannello
    oh_long = OVERHANG_LONG_SIDE_PCT * panel.min_dim
    # Sporgenza lato corto: 60% della dim maggiore del pannello
    oh_short = OVERHANG_SHORT_SIDE_PCT * panel.max_dim
    max_l = base_l + oh_long
    max_w = base_w + oh_short

    w, d = panel.larghezza_mm, panel.profondita_mm
    # Prova non ruotato
    if w <= max_l and d <= max_w:
        return False
    # Prova ruotato
    if d <= max_l and w <= max_w:
        return False
    return True


def _panel_effective_dims(panel: Panel, rotated: bool) -> Tuple[float, float]:
    """Dimensioni effettive del pannello (larghezza, profondita) considerando la rotazione."""
    if rotated:
        return panel.profondita_mm, panel.larghezza_mm
    return panel.larghezza_mm, panel.profondita_mm


def _panel_fits_at(
    panel: Panel,
    rotated: bool,
    x: float,
    y: float,
    surface_l: float,
    surface_w: float,
    n_epal: int,
    existing: List[PanelPlacement],
    max_footprint_l: float = None,
    max_footprint_w: float = None,
) -> bool:
    """
    Verifica se un pannello può essere posizionato in (x, y) sul bancale.
    
    - surface_l, surface_w: dimensioni della superficie base del pallet
    - n_epal: numero di EPAL (per calcolo sporgenze)
    - existing: pannelli già posizionati nello stesso layer
    - max_footprint_l/w: limiti piramidali dal layer sottostante (None = nessun limite)
    """
    ew, ed = _panel_effective_dims(panel, rotated)
    x_end = x + ew
    y_end = y + ed

    # --- Limiti di sporgenza ed appoggio su EPAL ---
    base_l = EPAL_LENGTH * n_epal
    base_w = EPAL_WIDTH

    # Ogni singolo pannello deve avere almeno il 50% della sua superficie appoggiata sulla base in legno dell'EPAL
    overlap_x = max(0.0, min(x_end, base_l) - max(x, 0.0))
    overlap_y = max(0.0, min(y_end, base_w) - max(y, 0.0))
    panel_area = ew * ed

    if (overlap_x * overlap_y) < (0.50 * panel_area):
        return False

    # --- Limiti piramidali ---
    if max_footprint_l is not None and x_end > max_footprint_l:
        return False
    if max_footprint_w is not None and y_end > max_footprint_w:
        return False

    # --- Sovrapposizione con pannelli esistenti ---
    for p in existing:
        if not (x >= p.x_end or x_end <= p.x or y >= p.y_end or y_end <= p.y):
            return False

    return True


def _try_place_in_layer(
    panel: Panel,
    layer: PalletLayer,
    surface_l: float,
    surface_w: float,
    n_epal: int,
    max_footprint_l: float = None,
    max_footprint_w: float = None,
) -> Optional[PanelPlacement]:
    """
    Tenta di posizionare il pannello nel layer esistente.
    Prova diversi punti candidati e entrambe le rotazioni.
    Restituisce il PanelPlacement o None.
    """
    # Genera punti candidati (bottom-left, after each existing panel)
    candidates = [(0.0, 0.0)]
    for p in layer.placements:
        candidates.append((p.x_end, 0.0))
        candidates.append((0.0, p.y_end))
        candidates.append((p.x_end, p.y))
        candidates.append((p.x, p.y_end))
        for p2 in layer.placements:
            if p2 is not p:
                candidates.append((p.x_end, p2.y_end))

    # Deduplica e ordina bottom-left
    candidates = sorted(set(candidates), key=lambda c: (c[1], c[0]))

    best_placement = None
    best_placement_overhang = float('inf')

    base_l = EPAL_LENGTH * n_epal
    base_w = EPAL_WIDTH

    for x, y in candidates:
        if x < 0 or y < 0:
            continue
        for rotated in [False, True]:
            if _panel_fits_at(
                panel, rotated, x, y,
                surface_l, surface_w, n_epal,
                layer.placements,
                max_footprint_l, max_footprint_w,
            ):
                ew, ed = _panel_effective_dims(panel, rotated)
                x_end, y_end = x + ew, y + ed
                oh_x = max(0.0, x_end - base_l)
                oh_y = max(0.0, y_end - base_w)
                tot_oh = oh_x + oh_y
                if tot_oh < best_placement_overhang:
                    best_placement_overhang = tot_oh
                    best_placement = PanelPlacement(panel, x, y, rotated)

    return best_placement


def _create_pallet_for_panels(
    panels_to_place: List[Panel],
    n_epal: int,
) -> Tuple[Pallet, List[Panel]]:
    """
    Crea un singolo bancale e ci mette quanti più pannelli possibile.
    Restituisce (pallet, pannelli_non_piazzati).
    """
    pallet = Pallet(n_epal=n_epal)
    surface_l, surface_w = _max_surface(n_epal)
    remaining = []

    for panel in panels_to_place:
        placed = False
        max_load = MAX_PALLET_LOAD_HEIGHT - EPAL_HEIGHT  # altezza carico ammessa

        # Tenta nei layer esistenti
        for i, layer in enumerate(pallet.layers):
            # Il nuovo spessore del layer sarà il max tra esistente e nuovo pannello
            new_thickness = max(layer.thickness, panel.spessore_mm)
            projected_height = layer.z_offset + new_thickness
            # Altezza degli strati sopra questo
            above_height = sum(
                pallet.layers[j].thickness
                for j in range(i + 1, len(pallet.layers))
            )
            if projected_height + above_height > max_load:
                continue

            # Limiti piramidali: footprint del layer precedente
            if i > 0:
                prev = pallet.layers[i - 1]
                mfl = prev.footprint_width  # nota: width del layer = asse X
                mfd = prev.footprint_depth  # depth del layer = asse Y
            else:
                mfl, mfd = None, None

            placement = _try_place_in_layer(
                panel, layer, surface_l, surface_w, n_epal, mfl, mfd
            )
            if placement:
                layer.placements.append(placement)
                placed = True
                break

        # Nuovo layer sopra
        if not placed:
            z_offset = pallet.load_height if pallet.layers else 0.0
            if z_offset + panel.spessore_mm <= max_load:
                # Limiti piramidali: footprint dell'ultimo layer
                if pallet.layers:
                    prev = pallet.layers[-1]
                    mfl = prev.footprint_width
                    mfd = prev.footprint_depth
                else:
                    mfl, mfd = None, None

                new_layer = PalletLayer(z_offset=z_offset)
                placement = _try_place_in_layer(
                    panel, new_layer, surface_l, surface_w, n_epal, mfl, mfd
                )
                if placement:
                    new_layer.placements.append(placement)
                    pallet.layers.append(new_layer)
                    placed = True

        if not placed:
            remaining.append(panel)

    return pallet, remaining


# ──────────────────────────────────────────────────────────
#  Funzione principale
# ──────────────────────────────────────────────────────────

from collections import defaultdict


def _compute_best_layer_pattern(
    sample_panel: Panel, n_epal: int
) -> Tuple[int, List[Tuple[float, float, bool]], float, float]:
    """
    Calcola il pattern 2D ottimale per disporre pannelli identici su un bancale.
    Garantisce che OGNI singolo pannello della griglia abbia almeno il 50% della sua superficie
    sostenuta fisicamente dalla base in legno EPAL.
    Restituisce: (items_per_layer, [(x, y, rotated), ...], footprint_width, footprint_depth)
    """
    base_l = EPAL_LENGTH * n_epal
    base_w = EPAL_WIDTH

    oh_long = OVERHANG_LONG_SIDE_PCT * sample_panel.min_dim
    oh_short = OVERHANG_SHORT_SIDE_PCT * sample_panel.max_dim
    max_l = base_l + oh_long
    max_w = base_w + oh_short

    best_count = 0
    best_overhang = float('inf')
    best_placements = []
    best_fw = base_l
    best_fd = base_w

    # Prova orientazioni
    for rotated in [False, True]:
        ew, ed = _panel_effective_dims(sample_panel, rotated)
        if ew > max_l or ed > max_w:
            continue

        max_nx = int(max_l // ew)
        max_ny = int(max_w // ed)

        if max_nx < 1 or max_ny < 1:
            continue

        # Prova tutte le combinazioni di nx e ny valide dal punto di vista dell'appoggio
        for nx in range(max_nx, 0, -1):
            for ny in range(max_ny, 0, -1):
                layer_l = nx * ew
                layer_w = ny * ed

                # Coordinate relative dell'EPAL rispetto al layer centrato
                bx1 = (layer_l - base_l) / 2.0
                bx2 = bx1 + base_l
                by1 = (layer_w - base_w) / 2.0
                by2 = by1 + base_w

                # Verifica che OGNI pannello della griglia (ix, iy) abbia almeno il 50% di appoggio sull'EPAL
                all_panels_supported = True
                panel_area = ew * ed

                for ix in range(nx):
                    px1 = ix * ew
                    px2 = px1 + ew
                    for iy in range(ny):
                        py1 = iy * ed
                        py2 = py1 + ed

                        overlap_x = max(0.0, min(px2, bx2) - max(px1, bx1))
                        overlap_y = max(0.0, min(py2, by2) - max(py1, by1))

                        if (overlap_x * overlap_y) < (0.50 * panel_area):
                            all_panels_supported = False
                            break
                    if not all_panels_supported:
                        break

                if all_panels_supported:
                    count = nx * ny
                    # Calcoliamo lo sbalzo totale rispetto alla base EPAL
                    overhang_x = max(0.0, layer_l - base_l)
                    overhang_y = max(0.0, layer_w - base_w)
                    total_overhang = overhang_x + overhang_y

                    is_better = False
                    if count > best_count:
                        is_better = True
                    elif count == best_count and total_overhang < best_overhang:
                        is_better = True

                    if is_better:
                        best_count = count
                        best_overhang = total_overhang
                        placements = []
                        for ix in range(nx):
                            for iy in range(ny):
                                placements.append((ix * ew, iy * ed, rotated))
                        best_placements = placements
                        best_fw = layer_l
                        best_fd = layer_w
                    # Trovata la combinazione nx, ny valida più grande per questa rotazione
                    break

    if best_count == 0:
        # Fallback: 1 singolo pannello al centro (0, 0)
        best_count = 1
        best_placements = [(0.0, 0.0, False)]
        best_fw = sample_panel.larghezza_mm
        best_fd = sample_panel.profondita_mm

    return best_count, best_placements, best_fw, best_fd


def pack_panels_greedy(
    panels: list[Panel],
    target_load_height: float = 1056.0,
    timeout_at: Optional[float] = None,
) -> list[Pallet]:
    """
    Algoritmo Greedy Batch per grandi volumi:
    Raggruppa i pannelli identici per modello, li imballa in bancali pieni omogenei
    fino all'altezza target uniforme del pianale in tempo O(modelli).
    I resti vengono poi distribuiti su bancali misti.
    """
    if timeout_at and time.time() > timeout_at:
        raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")

    # 1. Raggruppa i pannelli per modello e ordine
    groups = defaultdict(list)
    for p in panels:
        key = (p.codice_modello, p.larghezza_mm, p.profondita_mm, p.spessore_mm, p.ordine_id)
        groups[key].append(p)

    full_pallets: list[Pallet] = []
    mixed_pallets: list[Pallet] = []
    remainder_panels: list[Panel] = []

    # 2. Per ogni gruppo, genera i bancali omogenei completi
    for key, group_panels in groups.items():
        if timeout_at and time.time() > timeout_at:
            raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")

        sample = group_panels[0]
        n_epal = 2 if _needs_double_epal(sample) else 1

        items_per_layer, pattern, fw, fd = _compute_best_layer_pattern(sample, n_epal)

        max_load = target_load_height
        max_layers = max(1, int(max_load // sample.spessore_mm))
        items_per_full_pallet = items_per_layer * max_layers

        full_count = len(group_panels) // items_per_full_pallet
        rem_count = len(group_panels) % items_per_full_pallet

        idx = 0
        for _ in range(full_count):
            pallet = Pallet(n_epal=n_epal)
            for ly_idx in range(max_layers):
                layer = PalletLayer(z_offset=ly_idx * sample.spessore_mm)
                for x, y, rotated in pattern:
                    if idx < len(group_panels):
                        p_item = group_panels[idx]
                        idx += 1
                        layer.placements.append(PanelPlacement(p_item, x, y, rotated))
                pallet.layers.append(layer)
            full_pallets.append(pallet)

        # Genera bancali parziali per i resti dello stesso modello (pattern omogeneo)
        while idx < len(group_panels):
            pallet = Pallet(n_epal=n_epal)
            for ly_idx in range(max_layers):
                if idx >= len(group_panels):
                    break
                layer = PalletLayer(z_offset=ly_idx * sample.spessore_mm)
                for x, y, rotated in pattern:
                    if idx < len(group_panels):
                        p_item = group_panels[idx]
                        idx += 1
                        layer.placements.append(PanelPlacement(p_item, x, y, rotated))
                pallet.layers.append(layer)
            if pallet.layers:
                mixed_pallets.append(pallet)

    # 3. Se ci sono eventuali pannelli sciolti non impacchettati, usa il packer sequenziale per piccoli lotti (<= 30 pezzi)
    if remainder_panels:
        if len(remainder_panels) <= 30:
            extra_pallets = _pack_panels_sequential(remainder_panels, strategy="area_desc", timeout_at=timeout_at)
            mixed_pallets.extend(extra_pallets)

    # 4. Ordina prima i bancali omogenei completi (altezza uniforme) e poi i bancali misti/parziali
    all_pallets = full_pallets + mixed_pallets
    return all_pallets


def _pack_panels_sequential(
    panels: list[Panel],
    strategy: str = "area_desc",
    timeout_at: Optional[float] = None,
) -> list[Pallet]:
    """Imballamento sequenziale pezzo-per-pezzo per piccoli gruppi o resti."""
    sorted_panels = list(panels)

    if strategy == "area_desc":
        sorted_panels.sort(key=lambda p: (p.area, p.spessore_mm), reverse=True)
    elif strategy == "height_desc":
        sorted_panels.sort(key=lambda p: (p.spessore_mm, p.area), reverse=True)
    elif strategy == "order_first":
        sorted_panels.sort(key=lambda p: (p.ordine_id, -p.area))
    elif strategy == "random":
        random.shuffle(sorted_panels)

    singles = []
    doubles = []
    for p in sorted_panels:
        if _needs_double_epal(p):
            doubles.append(p)
        else:
            singles.append(p)

    pallets: list[Pallet] = []

    if doubles:
        if strategy == "order_first":
            doubles.sort(key=lambda p: (p.ordine_id, -p.area))

        remaining = doubles
        while remaining:
            if timeout_at and time.time() > timeout_at:
                raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")
            pallet, remaining = _create_pallet_for_panels(remaining, n_epal=2)
            if pallet.layers:
                pallets.append(pallet)
            else:
                panel = remaining.pop(0)
                forced_pallet = Pallet(n_epal=2)
                layer = PalletLayer(z_offset=0.0)
                layer.placements.append(PanelPlacement(panel, 0.0, 0.0, False))
                forced_pallet.layers.append(layer)
                pallets.append(forced_pallet)

    still_remaining = []
    for panel in singles:
        if timeout_at and time.time() > timeout_at:
            raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")
        placed = False
        same_order = [p for p in pallets if panel.ordine_id in p.order_ids()]
        other = [p for p in pallets if panel.ordine_id not in p.order_ids()]

        for pallet in same_order + other:
            surface_l, surface_w = _max_surface(pallet.n_epal)
            max_load = MAX_PALLET_LOAD_HEIGHT - EPAL_HEIGHT

            for i, layer in enumerate(pallet.layers):
                new_thickness = max(layer.thickness, panel.spessore_mm)
                projected = layer.z_offset + new_thickness
                above = sum(
                    pallet.layers[j].thickness
                    for j in range(i + 1, len(pallet.layers))
                )
                if projected + above > max_load:
                    continue

                if i > 0:
                    prev = pallet.layers[i - 1]
                    mfl, mfd = prev.footprint_width, prev.footprint_depth
                else:
                    mfl, mfd = None, None

                placement = _try_place_in_layer(
                    panel, layer, surface_l, surface_w, pallet.n_epal, mfl, mfd
                )
                if placement:
                    layer.placements.append(placement)
                    placed = True
                    break

            if placed:
                break

            if not placed:
                z_offset = pallet.load_height if pallet.layers else 0.0
                if z_offset + panel.spessore_mm <= max_load:
                    if pallet.layers:
                        prev = pallet.layers[-1]
                        mfl, mfd = prev.footprint_width, prev.footprint_depth
                    else:
                        mfl, mfd = None, None
                    new_layer = PalletLayer(z_offset=z_offset)
                    placement = _try_place_in_layer(
                        panel, new_layer, surface_l, surface_w, pallet.n_epal, mfl, mfd
                    )
                    if placement:
                        new_layer.placements.append(placement)
                        pallet.layers.append(new_layer)
                        placed = True
                        break

        if not placed:
            still_remaining.append(panel)

    remaining = still_remaining
    while remaining:
        if timeout_at and time.time() > timeout_at:
            raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")
        pallet, remaining = _create_pallet_for_panels(remaining, n_epal=1)
        if pallet.layers:
            pallets.append(pallet)
        else:
            panel = remaining.pop(0)
            forced_pallet = Pallet(n_epal=1)
            layer = PalletLayer(z_offset=0.0)
            layer.placements.append(PanelPlacement(panel, 0.0, 0.0, False))
            forced_pallet.layers.append(layer)
            pallets.append(forced_pallet)

    return pallets


def pack_panels_to_pallets(
    panels: list[Panel],
    strategy: str = "greedy_pianale",
    timeout_at: Optional[float] = None,
) -> list[Pallet]:
    """
    Imballa i pannelli su bancali EPAL.
    Usa l'algoritmo Greedy per grandi lotti o la strategia specificata.
    """
    if timeout_at and time.time() > timeout_at:
        raise TimeoutError("Tempo massimo di ottimizzazione scaduto!")

    if strategy in ("greedy_pianale", "greedy") or len(panels) > 50:
        return pack_panels_greedy(panels, timeout_at=timeout_at)

    return _pack_panels_sequential(panels, strategy=strategy, timeout_at=timeout_at)

