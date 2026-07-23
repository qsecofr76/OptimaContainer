"""
Algoritmo genetico per trovare la soluzione ottimale di caricamento.
"""
import time
import random
from typing import Callable, List, Optional

from config.defaults import (
    GA_POPULATION_SIZE, GA_GENERATIONS, GA_MUTATION_RATE, 
    GA_CROSSOVER_RATE, GA_TOURNAMENT_SIZE, GA_ELITE_COUNT
)
from models.panel import Panel
from models.container import ContainerType
from models.solution import Solution

from optimizer.pallet_packer import pack_panels_to_pallets
from optimizer.container_packer import pack_pallets_in_container
from optimizer.stacking import apply_stacking

class Individual:
    """Rappresenta un singolo individuo nell'algoritmo genetico."""
    def __init__(self, strategy: str, permutation: List[int], rotations: List[bool]):
        self.strategy = strategy
        self.permutation = permutation
        self.rotations = rotations
        self.score = -1.0
        self.solution = None

def _create_random_individual(panels: List[Panel], timeout_at: Optional[float] = None) -> Individual:
    strategy = random.choice(['greedy_pianale', 'area_desc', 'height_desc', 'order_first', 'random'])
    pallets = pack_panels_to_pallets(panels, strategy, timeout_at=timeout_at)
    n = len(pallets)
    perm = list(range(n))
    random.shuffle(perm)
    rots = [random.choice([False, True]) for _ in range(n)]
    return Individual(strategy, perm, rots)

def _mutate(ind: Individual, panels: List[Panel], timeout_at: Optional[float] = None) -> Individual:
    strategy, perm, rots = ind.strategy, list(ind.permutation), list(ind.rotations)
    
    if random.random() < GA_MUTATION_RATE:
        strategy = random.choice(['greedy_pianale', 'area_desc', 'height_desc', 'order_first', 'random'])
        
    if strategy != ind.strategy:
        pallets = pack_panels_to_pallets(panels, strategy, timeout_at=timeout_at)
        n = len(pallets)
        perm = list(range(n))
        random.shuffle(perm)
        rots = [random.choice([False, True]) for _ in range(n)]
    else:
        if random.random() < GA_MUTATION_RATE and len(perm) > 1:
            i, j = random.sample(range(len(perm)), 2)
            perm[i], perm[j] = perm[j], perm[i]
        if random.random() < GA_MUTATION_RATE and len(rots) > 0:
            i = random.randrange(len(rots))
            rots[i] = not rots[i]
            
    return Individual(strategy, perm, rots)

def _crossover(p1: Individual, p2: Individual) -> Individual:
    if p1.strategy != p2.strategy or len(p1.permutation) != len(p2.permutation):
        return Individual(p1.strategy, list(p1.permutation), list(p1.rotations))
        
    n = len(p1.permutation)
    if n < 2:
        return Individual(p1.strategy, list(p1.permutation), list(p1.rotations))
        
    # Order Crossover (OX) per la permutazione
    start, end = sorted(random.sample(range(n), 2))
    child_perm = [-1] * n
    child_perm[start:end] = p1.permutation[start:end]
    p2_filtered = [x for x in p2.permutation if x not in child_perm]
    
    idx = 0
    for i in range(n):
        if child_perm[i] == -1:
            child_perm[i] = p2_filtered[idx]
            idx += 1
            
    # Crossover uniforme per le rotazioni
    child_rots = [p1.rotations[i] if random.random() < 0.5 else p2.rotations[i] for i in range(n)]
    
    return Individual(p1.strategy, child_perm, child_rots)

def _hash_solution(sol: Solution) -> str:
    h = []
    # Ordina i pallet per posizione finale
    for p in sorted(sol.container.pallets, key=lambda p: (p.x, p.y, p.z)):
        h.append(f"{p.x:.0f},{p.y:.0f},{p.z:.0f},{p.rotated}")
    return "|".join(h)

def _verify_no_conflicts(population: List[Individual], gen: int) -> int:
    """
    Verifica al termine di ogni generazione che non ci siano conflitti
    sull'asse X o sull'asse Y per ciascun individuo della popolazione.
    Penalizza con score -1.0 qualunque soluzione con conflitti.
    """
    conflicts_found = 0
    for ind in population:
        if ind.solution and ind.solution.container:
            c = ind.solution.container
            pallets = c.pallets
            has_conflict = False
            for i in range(len(pallets)):
                for j in range(i + 1, len(pallets)):
                    p1, p2 = pallets[i], pallets[j]
                    if abs(p1.z - p2.z) < 10.0:
                        if c._pallets_overlap_xy(p1, p2, gap=c.gap):
                            has_conflict = True
                            break
                    else:
                        if c._pallets_overlap_xy(p1, p2, gap=0.0) and c._pallets_overlap_z(p1, p2):
                            has_conflict = True
                            break
                if has_conflict:
                    conflicts_found += 1
                    ind.score = -1.0
                    break
    return conflicts_found


def run_genetic_algorithm(panels: list[Panel], container_type: ContainerType, score_fn: callable, config: dict = None, progress_callback: callable = None) -> list[Solution]:
    """
    Esegue l'algoritmo genetico per generare soluzioni.
    """
    unique_solutions = {}
    start_ga_time = time.time()
    max_allowed_time = 175.0  # 3 minuti (180s) meno margine di sicurezza (5s)
    timeout_timestamp = start_ga_time + max_allowed_time

    if config and 'generations' in config and config['generations']:
        n_generations = int(config['generations'])
        pop_size = 20 if len(panels) > 50 else GA_POPULATION_SIZE
    elif len(panels) > 50:
        pop_size = 20
        n_generations = 10
    else:
        pop_size = GA_POPULATION_SIZE
        n_generations = GA_GENERATIONS

    try:
        population = [_create_random_individual(panels, timeout_at=timeout_timestamp) for _ in range(pop_size)]
        
        for gen in range(n_generations):
            # Controllo tempo limite di 3 minuti
            if time.time() - start_ga_time > max_allowed_time:
                break
                
            best_score = -1.0
            
            # Valutazione
            for ind in population:
                if ind.solution is None:
                    start_t = time.time()
                    pallets = pack_panels_to_pallets(panels, ind.strategy, timeout_at=timeout_timestamp)
                    
                    valid_perm = [i for i in ind.permutation if i < len(pallets)]
                    ordered_pallets = [pallets[i] for i in valid_perm]
                    pallet_order = [p.pallet_id for p in ordered_pallets]
                    
                    container = pack_pallets_in_container(pallets, container_type, pallet_order, ind.rotations)
                    container = apply_stacking(container)
                    
                    sol = Solution(container=container, iteration=gen)
                    placed_ids = set()
                    for p in container.pallets:
                        for panel in p.all_panels():
                            placed_ids.add(panel.panel_id)
                            
                    all_ids = set(p.panel_id for p in panels)
                    sol.unplaced_panel_ids = list(all_ids - placed_ids)
                    
                    sol = score_fn(sol)  # evaluate_solution returns the Solution with .score set
                    sol.generation_time_s = time.time() - start_t
                    ind.score = sol.score
                    ind.solution = sol
                    
                    h = _hash_solution(sol)
                    if h not in unique_solutions or unique_solutions[h].score < sol.score:
                        unique_solutions[h] = sol
                        
                if ind.score > best_score:
                    best_score = ind.score

            # --- VERIFICA CONFLITTI POST-GENERAZIONE SU ASSE X ED Y ---
            n_conflicts = _verify_no_conflicts(population, gen)

            if progress_callback:
                progress_callback(gen, n_generations, best_score)
                
            # Evoluzione
            population.sort(key=lambda x: x.score, reverse=True)
            elite_cnt = min(GA_ELITE_COUNT, pop_size)
            new_pop = population[:elite_cnt]
            
            while len(new_pop) < pop_size:
                # Controllo tempo intermedio durante la riproduzione per evitare timeout
                if time.time() - start_ga_time > max_allowed_time:
                    break
                    
                t1 = max(random.sample(population, min(GA_TOURNAMENT_SIZE, len(population))), key=lambda x: x.score)
                t2 = max(random.sample(population, min(GA_TOURNAMENT_SIZE, len(population))), key=lambda x: x.score)
                
                if random.random() < GA_CROSSOVER_RATE:
                    child = _crossover(t1, t2)
                else:
                    child = Individual(t1.strategy, list(t1.permutation), list(t1.rotations))
                    
                child = _mutate(child, panels, timeout_at=timeout_timestamp)
                new_pop.append(child)
                
            population = new_pop
    except TimeoutError:
        # Se andiamo in timeout (sia nel packer che altrove), catturiamo l'errore 
        # e procediamo con le soluzioni parziali già accumulate
        pass

    # Passaggio Invertito di Post-Ottimizzazione (Inverted Space-First Void Filler):
    # Saturiamo gli spazi residui nel container eseguendo il riempimento ed il rabbocco
    # SOLO sulle migliori 6 soluzioni candidate (invece di tutte le 60+ soluzioni grezze accumulate)
    from optimizer.container_packer import fill_remaining_container_voids
    sorted_candidates = sorted(unique_solutions.values(), key=lambda s: s.score, reverse=True)[:6]
    final_solutions = []
    for sol in sorted_candidates:
        sol_filled = fill_remaining_container_voids(sol, panels, container_type, score_fn=score_fn)
        final_solutions.append(sol_filled)

    # Segnala completamento finale
    if progress_callback and final_solutions:
        best = max(final_solutions, key=lambda s: s.score)
        progress_callback(n_generations, n_generations, best.score)

    return sorted(final_solutions, key=lambda x: x.score, reverse=True)
