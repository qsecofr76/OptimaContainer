"""
Modulo per la valutazione multi-obiettivo delle soluzioni.
"""

import math
from collections import defaultdict

from config.defaults import SCORE_WEIGHTS
from models.solution import Solution


def evaluate_solution(solution: Solution) -> Solution:
    """
    Valuta la soluzione calcolando uno score multi-obiettivo.
    Aggiorna i campi score e scores_detail della soluzione e la restituisce.
    """
    # 0. Order fulfillment (0.50 - PRIORITÀ ASSOLUTA: % pannelli caricati sul totale ordine)
    order_fulfillment = solution.placed_pct / 100.0

    # 1. Volume utilization (0.25)
    vol_utilization = solution.utilization_pct / 100.0

    # 2. Compactness (0.10)
    # Bounding box ratio: ratio of used volume vs bounding box volume of all pallets
    if not solution.container.pallets:
        compactness = 0.0
    else:
        min_x = min(p.x for p in solution.container.pallets)
        min_y = min(p.y for p in solution.container.pallets)
        max_x = max(p.x + p.effective_footprint[0] for p in solution.container.pallets)
        max_y = max(p.y + p.effective_footprint[1] for p in solution.container.pallets)
        max_z = max(p.top_z for p in solution.container.pallets)
        bbox_vol = (max_x - min_x) * (max_y - min_y) * max_z
        if bbox_vol > 0:
            compactness = solution.container.volume_used / bbox_vol
        else:
            compactness = 0.0

    # 3. Order grouping (0.05)
    # Penalize orders split across distant pallets.
    order_positions = defaultdict(list)
    for p in solution.container.pallets:
        for order_id in p.order_ids():
            center_x = p.x + p.effective_footprint[0] / 2
            center_y = p.y + p.effective_footprint[1] / 2
            center_z = p.z + p.total_height / 2
            order_positions[order_id].append((center_x, center_y, center_z))

    grouping_scores = []
    ct = solution.container.container_type
    max_possible_dist = math.sqrt(
        ct.internal_length**2 + ct.internal_width**2 + ct.internal_height**2
    )

    for order_id, pos_list in order_positions.items():
        if len(pos_list) <= 1:
            grouping_scores.append(1.0)  # perfect grouping
        else:
            max_dist = 0.0
            for i in range(len(pos_list)):
                for j in range(i + 1, len(pos_list)):
                    p1, p2 = pos_list[i], pos_list[j]
                    dist = math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)
                    max_dist = max(max_dist, dist)
    order_grouping = sum(grouping_scores) / len(grouping_scores) if grouping_scores else 1.0

    # Penalizzazione per mixing ordini eccedente: mischiamento fino a 3 ordini per bancale consentito senza penalità,
    # degrado del rating applicato soltanto oltre i 3 ordini per singolo bancale.
    mixing_penalty = 0.0
    for p in solution.container.pallets:
        n_ord = len(p.order_ids())
        if n_ord > 3:
            mixing_penalty += (n_ord - 3) * 0.1

    order_grouping = max(0.0, order_grouping - mixing_penalty)

    # 4. Stability (0.05)
    # Penalize pallets with excessive overhang
    overhang_penalty = 0.0
    for p in solution.container.pallets:
        eff_l, eff_w = p.effective_footprint
        base_l, base_w = p.base_length, p.base_width
        
        overhang_l = max(0.0, eff_l - base_l)
        overhang_w = max(0.0, eff_w - base_w)
        
        if overhang_l > 0:
            overhang_penalty += (overhang_l / base_l) * 0.1
        if overhang_w > 0:
            overhang_penalty += (overhang_w / base_w) * 0.1
            
    stability = max(0.0, 1.0 - overhang_penalty)

    # 5. Accessibility (0.05)
    # Bonus for orders placed near the container door (high x = near door)
    if not solution.container.pallets:
        accessibility = 0.0
    else:
        max_x_container = ct.internal_length
        x_scores = [p.x / max_x_container for p in solution.container.pallets]
        accessibility = sum(x_scores) / len(x_scores)

    scores_detail = {
        "order_fulfillment": order_fulfillment,
        "volume_utilization": vol_utilization,
        "compactness": compactness,
        "order_grouping": order_grouping,
        "stability": stability,
        "accessibility": accessibility,
    }
    
    total_score = sum(scores_detail[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)
    
    solution.scores_detail = scores_detail
    solution.score = total_score
    
    return solution
