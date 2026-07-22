"""
Modulo per il parsing dei file di input e creazione dei pannelli.
"""

import pandas as pd
from models.panel import Panel


def parse_dataframe(df: pd.DataFrame) -> list[Panel]:
    """Crea una lista di oggetti Panel da un DataFrame pandas."""
    required_cols = ['codice_modello', 'larghezza_mm', 'profondita_mm', 'spessore_mm', 'quantita', 'ordine_id']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Colonna mancante nel DataFrame: {col}")

    panels = []
    for _, row in df.iterrows():
        quantita = int(row['quantita'])
        if quantita < 1:
            continue
            
        larghezza = float(row['larghezza_mm'])
        profondita = float(row['profondita_mm'])
        spessore = float(row['spessore_mm'])
        
        if larghezza <= 0 or profondita <= 0 or spessore <= 0:
            raise ValueError(f"Dimensioni non valide per il modello {row['codice_modello']}")

        for _ in range(quantita):
            panel = Panel(
                codice_modello=str(row['codice_modello']),
                larghezza_mm=larghezza,
                profondita_mm=profondita,
                spessore_mm=spessore,
                ordine_id=str(row['ordine_id'])
            )
            panels.append(panel)
            
    return panels


def parse_csv(filepath: str) -> list[Panel]:
    """Legge un file CSV e restituisce la lista dei pannelli."""
    df = pd.read_csv(filepath)
    return parse_dataframe(df)


def parse_excel(filepath: str) -> list[Panel]:
    """Legge un file Excel e restituisce la lista dei pannelli."""
    df = pd.read_excel(filepath)
    return parse_dataframe(df)


def create_sample_data() -> list[Panel]:
    """Create sample data for testing/demo."""
    data = [
        # Ante (ordine ORD-001)
        {"codice_modello": "ANTA-60x40", "larghezza_mm": 400, "profondita_mm": 600, "spessore_mm": 18, "quantita": 4, "ordine_id": "ORD-001"},
        {"codice_modello": "ANTA-70x45", "larghezza_mm": 450, "profondita_mm": 700, "spessore_mm": 22, "quantita": 3, "ordine_id": "ORD-001"},
        {"codice_modello": "ANTA-80x50", "larghezza_mm": 500, "profondita_mm": 800, "spessore_mm": 18, "quantita": 2, "ordine_id": "ORD-001"},
        {"codice_modello": "ANTA-90x45", "larghezza_mm": 450, "profondita_mm": 900, "spessore_mm": 22, "quantita": 4, "ordine_id": "ORD-001"},
        
        # Ante (ordine ORD-002)
        {"codice_modello": "ANTA-60x40", "larghezza_mm": 400, "profondita_mm": 600, "spessore_mm": 18, "quantita": 2, "ordine_id": "ORD-002"},
        {"codice_modello": "ANTA-70x45", "larghezza_mm": 450, "profondita_mm": 700, "spessore_mm": 22, "quantita": 2, "ordine_id": "ORD-002"},
        
        # Fianchi (ordine ORD-003)
        {"codice_modello": "FIANCO-200x60", "larghezza_mm": 600, "profondita_mm": 2000, "spessore_mm": 18, "quantita": 2, "ordine_id": "ORD-003"},
        {"codice_modello": "FIANCO-180x50", "larghezza_mm": 500, "profondita_mm": 1800, "spessore_mm": 18, "quantita": 3, "ordine_id": "ORD-003"},
        {"codice_modello": "FIANCO-220x58", "larghezza_mm": 580, "profondita_mm": 2200, "spessore_mm": 22, "quantita": 2, "ordine_id": "ORD-003"},
    ]
    df = pd.DataFrame(data)
    return parse_dataframe(df)
