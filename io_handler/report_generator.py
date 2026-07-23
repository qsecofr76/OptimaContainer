"""
Modulo per la generazione del report HTML sintetico delle soluzioni.
Ogni soluzione presenta un resoconto dell'ordine (pezzi soddisfatti) e un link diretto alla pagina 3D della soluzione.
"""

import os
from collections import Counter
from jinja2 import Template
from models.solution import Solution
from visualization.viewer_3d import create_3d_figure

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Report OptimaContainer — Sintesi Soluzioni</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f6f9; color: #333; }
        h1 { color: #1e293b; margin-bottom: 5px; }
        .subtitle { color: #64748b; margin-bottom: 20px; font-size: 1.1em; }
        
        .solution-card { background: #fff; padding: 25px; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .sol-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 15px; margin-bottom: 15px; }
        .sol-title { font-size: 1.4em; font-weight: bold; color: #0f172a; }
        .badge-best { background: #10b981; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 0.85em; margin-left: 8px; }

        .score-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .score-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px 15px; border-radius: 8px; }
        .score-box .label { font-size: 0.85em; color: #64748b; margin-bottom: 4px; }
        .score-box .value { font-size: 1.3em; font-weight: bold; color: #1e293b; }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.95em; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background-color: #f8fafc; color: #475569; font-weight: 600; }
        tr:hover { background-color: #f8fafc; }

        .btn-3d { display: inline-block; padding: 10px 18px; background: #2563eb; color: white; text-decoration: none; font-weight: bold; border-radius: 6px; transition: background 0.2s; }
        .btn-3d:hover { background: #1d4ed8; }
        
        .progress-bar-bg { background-color: #e2e8f0; border-radius: 6px; height: 12px; width: 100%; overflow: hidden; margin-top: 6px; }
        .progress-bar-fill { background-color: #10b981; height: 100%; border-radius: 6px; }
    </style>
</head>
<body>
    <h1>🚛 Report Ottimizzazione Carico Container</h1>
    <div class="subtitle">Sintesi Evasione Ordini e Dettaglio Soluzioni</div>
    
    {% for sol in solutions %}
    {% set s_data = sol_data[loop.index0] %}
    <div class="solution-card" id="sol-{{ loop.index }}">
        <div class="sol-header">
            <div class="sol-title">
                Soluzione #{{ loop.index }}
                {% if loop.first %}<span class="badge-best">Miglior Rating (BEST)</span>{% else %}<span style="color: #64748b; font-size: 0.85em; margin-left: 10px;">Rating Alternativo #{{ loop.index }}</span>{% endif %}
            </div>
            <div>
                <a href="solution_{{ loop.index }}_3d.html" target="_blank" class="btn-3d">🔍 Apri Vista 3D Interattiva (Soluzione #{{ loop.index }})</a>
            </div>
        </div>
        
        <div class="score-grid">
            <div class="score-box">
                <div class="label">Punteggio Totale Score</div>
                <div class="value" style="color: #2563eb;">{{ "%.4f"|format(sol.score) }}</div>
            </div>
            <div class="score-box">
                <div class="label">Evasione Totale Ordine</div>
                <div class="value" style="color: #10b981;">{{ sol.panel_count }} / {{ sol.total_order_panels }} ({{ "%.1f"|format(sol.placed_pct) }}%)</div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {{ '%.1f'|format(sol.placed_pct) }}%;"></div>
                </div>
            </div>
            <div class="score-box">
                <div class="label">Utilizzo Volume Container</div>
                <div class="value">{{ "%.1f"|format(sol.utilization_pct) }}%</div>
            </div>
            <div class="score-box">
                <div class="label">Totale Bancali Impiegati</div>
                <div class="value">{{ sol.pallet_count }}</div>
            </div>
            <div class="score-box">
                <div class="label">Pannelli Non Caricati</div>
                <div class="value" style="color: #ef4444;">{{ sol.unplaced_panel_ids|length }} pz</div>
            </div>
        </div>
        
        <h4>Resoconto Evasione Ordini per Modello / Articolo</h4>
        <table>
            <tr>
                <th>Codice Modello / Articolo</th>
                <th>Dimensioni (L x P x H mm)</th>
                <th>Pezzi nell'Ordine</th>
                <th>Pezzi Caricati</th>
                <th>Pezzi Rimasti (Inevasi)</th>
                <th>Stato Evasione Articolo</th>
            </tr>
            {% for item in s_data.order_summary %}
            <tr>
                <td><strong>{{ item.codice }}</strong></td>
                <td>{{ "%.0f"|format(item.l) }} x {{ "%.0f"|format(item.w) }} x {{ "%.0f"|format(item.h) }} mm</td>
                <td>{{ item.total }} pz</td>
                <td><strong style="color: #059669;">{{ item.placed }} pz</strong></td>
                <td><span style="color: {{ '#ef4444' if item.remaining > 0 else '#64748b' }};">{{ item.remaining }} pz</span></td>
                <td>
                    {% if item.remaining == 0 %}
                        <span style="background: #d1fae5; color: #065f46; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">Completato 100%</span>
                    {% else %}
                        <span style="background: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">Parziale ({{ '%.0f'|format(item.placed / item.total * 100) }}%)</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
        
        <div style="margin-top: 20px; text-align: right;">
            <a href="solution_{{ loop.index }}_3d.html" target="_blank" class="btn-3d">🔍 Visualizza Bancali e Carico 3D per Soluzione #{{ loop.index }} &rarr;</a>
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""


def generate_report(solutions: list[Solution], output_dir: str, all_panels: list = None, log_fn=print) -> str:
    """Genera report HTML sintetico con resoconto evasione ordine per articolo e link al 3D."""
    log_fn("[REPORT] Inizio generazione report...")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        log_fn(f"[REPORT] Creata cartella output: {output_dir}")

    sorted_solutions = sorted(solutions, key=lambda s: s.score, reverse=True)
    top_solutions = sorted_solutions[:4]
    log_fn(f"[REPORT] Elaborazione 3D per le Top {len(top_solutions)} soluzioni...")

    sol_data = []

    global_order_totals = Counter()
    global_article_dims = {}
    if all_panels:
        for p in all_panels:
            global_order_totals[p.codice_modello] += 1
            global_article_dims[p.codice_modello] = (p.larghezza_mm, p.profondita_mm, p.spessore_mm)

    for idx, sol in enumerate(top_solutions):
        rank_label = "BEST SOLUTION" if idx == 0 else f"Alternativa #{idx+1}"
        log_fn(f"[REPORT] Creazione figura 3D #{idx+1} ({rank_label})...")
        fig = create_3d_figure(sol, title=f"Soluzione #{idx+1} ({rank_label}) - Rating Score: {sol.score:.4f}", all_panels=all_panels)
        
        sol_filename = f"solution_{idx+1}_3d.html"
        sol_path = os.path.join(output_dir, sol_filename)
        log_fn(f"[REPORT] Scrittura file 3D #{idx+1}: {sol_filename}...")
        fig.write_html(sol_path, include_plotlyjs='cdn')
        log_fn(f"[REPORT] Salvato {sol_filename}")

        if idx == 0:
            best_path = os.path.join(output_dir, "best_solution_3d.html")
            fig.write_html(best_path, include_plotlyjs='cdn')
            log_fn(f"[REPORT] Salvato best_solution_3d.html")

        # Calcola il resoconto dell'ordine per articolo per la soluzione corrente
        order_placed = Counter()
        for pallet in sol.container.pallets:
            for p in pallet.all_panels():
                order_placed[p.codice_modello] += 1
                if p.codice_modello not in global_article_dims:
                    global_article_dims[p.codice_modello] = (p.larghezza_mm, p.profondita_mm, p.spessore_mm)

        order_summary = []
        target_keys = global_order_totals.keys() if global_order_totals else order_placed.keys()
        for mod in sorted(target_keys):
            placed_cnt = order_placed.get(mod, 0)
            total_cnt = global_order_totals.get(mod, placed_cnt)
            remaining_cnt = max(0, total_cnt - placed_cnt)
            l, w, h = global_article_dims.get(mod, (0, 0, 0))

            order_summary.append({
                'codice': mod,
                'l': l,
                'w': w,
                'h': h,
                'placed': placed_cnt,
                'total': total_cnt,
                'remaining': remaining_cnt
            })

        sol_data.append({'order_summary': order_summary})

    log_fn("[REPORT] Rendering HTML con Jinja2...")
    template = Template(HTML_TEMPLATE)
    html_content = template.render(solutions=top_solutions, sol_data=sol_data)
    
    report_path = os.path.join(output_dir, "report_optimacontainer.html")
    log_fn(f"[REPORT] Scrittura report HTML su {report_path}...")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    log_fn("[REPORT] Generazione report completata con successo!")
    return report_path
