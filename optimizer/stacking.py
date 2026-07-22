"""
Logica per l'impilamento dei pallet.
"""
from typing import List, Tuple
from models.container import Container

def get_stacking_points(container: Container) -> List[Tuple[float, float, float]]:
    """
    Ottiene i punti di impilamento validi (diretto e pianale) per il container.
    """
    points = []
    
    # Stacking diretto
    for p in container.pallets:
        if p.can_stack_pallet_on_top():
            points.append((p.x, p.y, p.top_z))
            
    # Stacking con Pianale
    for p1 in container.pallets:
        for p2 in container.pallets:
            if p1 != p2 and p1.can_form_pianale_with(p2):
                z = max(p1.top_z, p2.top_z) + 30.0
                points.append((min(p1.x, p2.x), min(p1.y, p2.y), z))
                
    return points

def apply_stacking(container: Container) -> Container:
    """
    Applica le regole di impilamento per compattare i pallet sul pavimento.
    """
    pallets_to_stack = [p for p in container.pallets if p.z == 0]
    pallets_to_stack.sort(key=lambda p: p.effective_footprint[0] * p.effective_footprint[1])
    
    for pallet in pallets_to_stack:
        stacked = False
        
        # 1. Prova lo stacking diretto
        for target in container.pallets:
            if target.pallet_id == pallet.pallet_id: 
                continue
            if target.can_stack_pallet_on_top():
                if target.top_z + pallet.total_height <= container.container_type.internal_height:
                    orig_x, orig_y, orig_z = pallet.x, pallet.y, pallet.z
                    pallet.x, pallet.y, pallet.z = target.x, target.y, target.top_z
                    pallet.stacked_on = target.pallet_id
                    
                    if container.is_valid_placement(pallet):
                        stacked = True
                        break
                    else:
                        pallet.x, pallet.y, pallet.z = orig_x, orig_y, orig_z
                        pallet.stacked_on = None
                        
        if stacked: 
            continue
            
        # 2. Prova il pianale
        for target1 in container.pallets:
            if target1.pallet_id == pallet.pallet_id: 
                continue
            for target2 in container.pallets:
                if target2.pallet_id in (pallet.pallet_id, target1.pallet_id): 
                    continue
                if target1.can_form_pianale_with(target2):
                    pianale_z = max(target1.top_z, target2.top_z) + 30.0
                    if pianale_z + pallet.total_height <= container.container_type.internal_height:
                        orig_x, orig_y, orig_z = pallet.x, pallet.y, pallet.z
                        pallet.x, pallet.y, pallet.z = min(target1.x, target2.x), min(target1.y, target2.y), pianale_z
                        pallet.stacked_on = target1.pallet_id
                        pallet.has_pianale_below = True
                        
                        if container.is_valid_placement(pallet):
                            stacked = True
                            break
                        else:
                            pallet.x, pallet.y, pallet.z = orig_x, orig_y, orig_z
                            pallet.stacked_on = None
                            pallet.has_pianale_below = False
            if stacked: 
                break

    return container
