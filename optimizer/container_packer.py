"""
Algoritmo per inserire i bancali nel container.
"""
from typing import List, Optional

from config.defaults import GAP
from models.container import Container, ContainerType
from models.pallet import Pallet
from optimizer.stacking import get_stacking_points

def pack_pallets_in_container(
    pallets: list[Pallet], 
    container_type: ContainerType, 
    pallet_order: list[int] = None, 
    rotations: list[bool] = None, 
    gap: float = GAP
) -> Container:
    """
    Posiziona i pallet nel container a due livelli (Primo Livello + Pianale + Secondo Livello).
    """
    container = Container(container_type=container_type, gap=gap)
    
    if pallet_order:
        pallet_map = {p.pallet_id: p for p in pallets}
        sorted_pallets = [pallet_map[pid] for pid in pallet_order if pid in pallet_map]
        sorted_pallets += [p for p in pallets if p.pallet_id not in pallet_order]
    else:
        # Ordina prima per altezza decrescente e poi per ingombro
        sorted_pallets = sorted(
            pallets, 
            key=lambda p: (p.total_height, p.effective_footprint[0] * p.effective_footprint[1]), 
            reverse=True
        )

    # ── FASE 1: Caricamento Pavimento (Level 1, Z = 0) ────────────────
    level1_pallets: list[Pallet] = []
    remaining_pallets: list[Pallet] = []
    dynamic_floor_points = [(gap, gap, 0.0)]

    for i, pallet in enumerate(sorted_pallets):
        rot_preference = [rotations[i]] if (rotations and i < len(rotations)) else [False, True]
        placed = False
        floor_points = sorted(list(set(dynamic_floor_points)), key=lambda pt: (pt[0], pt[1]))

        for rot in rot_preference:
            pallet.rotated = rot
            for x, y, z in floor_points:
                pallet.x, pallet.y, pallet.z = x, y, z
                pallet.stacked_on = None
                pallet.has_pianale_below = False

                if container.is_valid_placement(pallet):
                    container.pallets.append(pallet)
                    level1_pallets.append(pallet)
                    p_eff_l, p_eff_w = pallet.effective_footprint
                    dynamic_floor_points.append((pallet.x + p_eff_l + gap, gap, 0.0))
                    dynamic_floor_points.append((gap, pallet.y + p_eff_w + gap, 0.0))
                    dynamic_floor_points.append((pallet.x + p_eff_l + gap, pallet.y, 0.0))
                    dynamic_floor_points.append((pallet.x, pallet.y + p_eff_w + gap, 0.0))
                    dynamic_floor_points.append((pallet.x + p_eff_l + gap, pallet.y + p_eff_w + gap, 0.0))
                    placed = True
                    break
            if placed:
                break

        if not placed:
            remaining_pallets.append(pallet)

    # ── FASE 2 & 3: Caricamento Secondo Livello su Pianale ───────────
    if remaining_pallets and level1_pallets:
        # Calcola la quota del pianale sopra i bancali del primo livello
        max_l1_top_z = max(p.top_z for p in level1_pallets)
        pianale_z = max_l1_top_z + 30.0  # spessore del pianale (30 mm)

        # Pre-calcola i punti base derivati dai bancali del Livello 1
        l2_base_points = []
        for p1 in level1_pallets:
            l2_base_points.append((p1.x, p1.y, pianale_z))
            p1_eff_l, p1_eff_w = p1.effective_footprint
            l2_base_points.append((p1.x + p1_eff_l + gap, p1.y, pianale_z))
            l2_base_points.append((p1.x, p1.y + p1_eff_w + gap, pianale_z))

        dynamic_l2_points = []

        for pallet in remaining_pallets:
            placed = False
            l2_points = sorted(list(set(l2_base_points + dynamic_l2_points)), key=lambda pt: (pt[0], pt[1]))

            for rot in [False, True]:
                pallet.rotated = rot
                for x, y, z in l2_points:
                    pallet.x, pallet.y, pallet.z = x, y, z
                    pallet.stacked_on = None
                    pallet.has_pianale_below = True

                    if container.is_valid_placement(pallet):
                        container.pallets.append(pallet)
                        p_eff_l, p_eff_w = pallet.effective_footprint
                        dynamic_l2_points.append((pallet.x + p_eff_l + gap, pallet.y, pianale_z))
                        dynamic_l2_points.append((pallet.x, pallet.y + p_eff_w + gap, pianale_z))
                        dynamic_l2_points.append((pallet.x + p_eff_l + gap, pallet.y + p_eff_w + gap, pianale_z))
                        placed = True
                        break
                if placed:
                    break

    return container


def fill_remaining_container_voids(
    sol,
    all_panels: list,
    container_type: ContainerType,
    gap: float = GAP,
    score_fn: callable = None
):
    """
    Passaggio Invertito di Post-Ottimizzazione (Inverted Space-First Void Filler):
    Rileva le nicchie 3D e gli spazi vuoti residui nel container (Livello 1 e Livello 2)
    e costruisce a ritroso nuovi bancali su misura utilizzando i pannelli inesi dell'ordine.
    """
    if not sol.unplaced_panel_ids:
        return sol

    unplaced_ids = set(sol.unplaced_panel_ids)
    unplaced_panels = [p for p in all_panels if p.panel_id in unplaced_ids]
    if not unplaced_panels:
        return sol

    container = sol.container
    if not container.pallets:
        return sol

    # Identifica i punti candidati a Livello 1 (z = 0) e Livello 2 (z = pianale_z)
    level1_pallets = [p for p in container.pallets if p.z <= 0.1]
    pianale_z = (max(p.top_z for p in level1_pallets) + 30.0) if level1_pallets else 0.0

    candidate_points = []

    # Genera punti a terra
    for p in level1_pallets:
        bx1, bx2, by1, by2 = p.collo_bbox_xy
        candidate_points.append((bx2 + gap, gap, 0.0, False))
        candidate_points.append((gap, by2 + gap, 0.0, False))
        candidate_points.append((bx2 + gap, by1, 0.0, False))
        candidate_points.append((bx1, by2 + gap, 0.0, False))
        candidate_points.append((bx2 + gap, by2 + gap, 0.0, False))

    # Genera punti su pianale
    if pianale_z > 30.0:
        for p in level1_pallets:
            bx1, bx2, by1, by2 = p.collo_bbox_xy
            candidate_points.append((bx1, by1, pianale_z, True))
            candidate_points.append((bx2 + gap, by1, pianale_z, True))
            candidate_points.append((bx1, by2 + gap, pianale_z, True))

    candidate_points = sorted(list(set(candidate_points)), key=lambda pt: (pt[2], pt[0], pt[1]))

    from optimizer.pallet_packer import pack_panels_greedy

    added_any = True
    while added_any and unplaced_panels:
        added_any = False
        
        # Prova diverse altezze di carico target (da massima 1056mm a 264mm) per entrare anche in nicchie ad altezza ridotta
        for target_h in [1056.0, 792.0, 528.0, 264.0]:
            extra_pallets = pack_panels_greedy(unplaced_panels, target_load_height=target_h)
            if not extra_pallets:
                continue

            for ep in extra_pallets:
                ep_placed = False
                for rot in [False, True]:
                    ep.rotated = rot
                    for cx, cy, cz, has_pianale in candidate_points:
                        ep.x, ep.y, ep.z = cx, cy, cz
                        ep.has_pianale_below = has_pianale

                        if container.is_valid_placement(ep):
                            container.pallets.append(ep)
                            ep_placed = True
                            added_any = True

                            placed_p_ids = set(p.panel_id for p in ep.all_panels())
                            unplaced_panels = [p for p in unplaced_panels if p.panel_id not in placed_p_ids]
                            unplaced_ids -= placed_p_ids

                            ebx1, ebx2, eby1, eby2 = ep.collo_bbox_xy
                            candidate_points.append((ebx2 + gap, eby1, cz, has_pianale))
                            candidate_points.append((ebx1, eby2 + gap, cz, has_pianale))
                            candidate_points.append((ebx2 + gap, eby2 + gap, cz, has_pianale))
                            candidate_points = sorted(list(set(candidate_points)), key=lambda pt: (pt[2], pt[0], pt[1]))
                            break
                    if ep_placed:
                        break

                if ep_placed:
                    break
            if added_any:
                break

    sol.unplaced_panel_ids = list(unplaced_ids)
    if score_fn:
        sol = score_fn(sol)

    return sol
