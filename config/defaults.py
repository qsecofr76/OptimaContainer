"""
OptimaContainer — Costanti e parametri di configurazione globali.
"""

# ──────────────────────────────────────────────
# Dimensioni Pallet EPAL (mm)
# ──────────────────────────────────────────────
EPAL_LENGTH = 1200  # lato lungo
EPAL_WIDTH = 800    # lato corto
EPAL_HEIGHT = 144   # altezza pallet

# ──────────────────────────────────────────────
# Regole di carico bancali
# ──────────────────────────────────────────────
MAX_PALLET_LOAD_HEIGHT = 1200       # altezza massima bancale caricato (mm)
PIANALE_THICKNESS = 30              # spessore pannello pianale (mm)
GAP = 100                          # gap di sicurezza tra bancali e pareti (mm)

# ──────────────────────────────────────────────
# Regole di sporgenza ante dal bancale
# ──────────────────────────────────────────────
# Lato lungo del bancale (1200mm): max 30% della dimensione minore dell'anta
OVERHANG_LONG_SIDE_PCT = 0.30
# Lato corto del bancale (800mm): max 60% della dimensione maggiore dell'anta
OVERHANG_SHORT_SIDE_PCT = 0.60

# ──────────────────────────────────────────────
# Tipi di container disponibili
# ──────────────────────────────────────────────
CONTAINER_TYPES = {
    "20ft Standard": {
        "name": "20ft Standard",
        "internal_length": 5900,
        "internal_width": 2350,
        "internal_height": 2390,
        "door_width": 2340,
        "door_height": 2280,
    },
    "40ft Standard": {
        "name": "40ft Standard",
        "internal_length": 12030,
        "internal_width": 2350,
        "internal_height": 2390,
        "door_width": 2340,
        "door_height": 2280,
    },
    "40ft High Cube": {
        "name": "40ft High Cube",
        "internal_length": 12030,
        "internal_width": 2350,
        "internal_height": 2690,
        "door_width": 2340,
        "door_height": 2585,
    },
}

# ──────────────────────────────────────────────
# Parametri Algoritmo Genetico
# ──────────────────────────────────────────────
GA_POPULATION_SIZE = 200          # individui per generazione
GA_GENERATIONS = 50               # numero di generazioni
GA_MUTATION_RATE = 0.15           # probabilità di mutazione
GA_CROSSOVER_RATE = 0.80          # probabilità di crossover
GA_TOURNAMENT_SIZE = 5            # dimensione torneo di selezione
GA_ELITE_COUNT = 5                # individui élite preservati
GA_TARGET_UNIQUE_SOLUTIONS = 1000 # obiettivo soluzioni uniche

# ──────────────────────────────────────────────
# Pesi Scoring Multi-Obiettivo
# ──────────────────────────────────────────────
SCORE_WEIGHTS = {
    "order_fulfillment": 0.50,     # % pannelli dell'ordine evasi (PRIORITÀ ASSOLUTA)
    "volume_utilization": 0.25,    # % volume container utilizzato
    "compactness": 0.10,           # minimizzare vuoti tra bancali
    "order_grouping": 0.05,        # raggruppamento per ordine
    "stability": 0.05,             # stabilità impilamenti
    "accessibility": 0.05,         # accessibilità ordini dalla porta
}

# ──────────────────────────────────────────────
# Visualizzazione
# ──────────────────────────────────────────────
PALLET_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2",
    "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7",
    "#9C755F", "#BAB0AC", "#D37295", "#FABFD2",
    "#86BCB6", "#8CD17D", "#B6992D", "#499894",
]
CONTAINER_COLOR = "rgba(180, 180, 180, 0.15)"
CONTAINER_EDGE_COLOR = "#333333"
PIANALE_COLOR = "rgba(139, 119, 101, 0.5)"
