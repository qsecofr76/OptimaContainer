"""
Modulo per la generazione del report HTML con distinta articoli per bancale (senza suddivisione per livelli/file).
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
    <title>Report OptimaContainer — Top Soluzioni</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f4f6f9; color: #333; }
        h1 { color: #1e293b; margin-bottom: 5px; }
        .subtitle { color: #64748b; margin-bottom: 20px; font-size: 1.1em; }
        
        /* Navigation Tabs */
        .nav-tabs { display: flex; gap: 10px; margin-bottom: 25px; background: #fff; padding: 12px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); flex-wrap: wrap; }
        .tab-btn { text-decoration: none; padding: 10px 18px; font-weight: bold; border-radius: 6px; color: #475569; background: #f1f5f9; transition: all 0.2s; }
        .tab-btn:hover { background: #e2e8f0; color: #0f172a; }
        .tab-btn.active { background: #2563eb; color: #fff; box-shadow: 0 2px 5px rgba(37,99,235,0.3); }

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

        .btn-3d { display: inline-block; margin-top: 15px; padding: 10px 16px; background: #059669; color: white; text-decoration: none; font-weight: bold; border-radius: 6px; }
        .btn-3d:hover { background: #047857; }
        .chart-container { height: 650px; width: 100%; margin-top: 15px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
        
        ul.art-list { margin: 0; padding-left: 18px; line-height: 1.6em; list-style-type: square; }
        ul.art-list li { margin-bottom: 4px; }
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <h1>🚛 Report Ottimizzazione Carico Container</h1>
    <div class="subtitle">Sintesi Dettagliata per Bancale ed Elenco Articoli Caricati</div>
    
    <!-- Barra Navigazione Soluzioni -->
    <div class="nav-tabs">
        {% for sol in solutions %}
        <a href="#sol-{{ loop.index }}" class="tab-btn {% if loop.first %}active{% endif %}">
            {% if loop.first %}🏆 Soluzione #1 (BEST - Score: {{ "%.4f"|format(sol.score) }}){% else %}Alternativa #{{ loop.index }} (Score: {{ "%.4f"|format(sol.score) }}){% endif %}
        </a>
        {% endfor %}
    </div>
    
    {% for sol in solutions %}
    {% set s_data = sol_data[loop.index0] %}
    <div class="solution-card" id="sol-{{ loop.index }}">
        <div class="sol-header">
            <div class="sol-title">
                Soluzione #{{ loop.index }}
                {% if loop.first %}<span class="badge-best">Miglior Rating (BEST)</span>{% else %}<span style="color: #64748b; font-size: 0.85em; margin-left: 10px;">Rating Alternativo #{{ loop.index }}</span>{% endif %}
            </div>
            <div>
                <a href="solution_{{ loop.index }}_3d.html" target="_blank" class="btn-3d">🔍 Apri Vista 3D Separata (Soluzione #{{ loop.index }})</a>
            </div>
        </div>
        
        <div class="score-grid">
            <div class="score-box">
                <div class="label">Punteggio Totale</div>
                <div class="value" style="color: #2563eb;">{{ "%.4f"|format(sol.score) }}</div>
            </div>
            <div class="score-box">
                <div class="label">Utilizzo Volume</div>
                <div class="value">{{ "%.1f"|format(sol.utilization_pct) }}%</div>
            </div>
            <div class="score-box">
                <div class="label">Totale Bancali</div>
                <div class="value">{{ sol.pallet_count }}</div>
            </div>
            <div class="score-box">
                <div class="label">Pannelli Caricati</div>
                <div class="value">{{ sol.panel_count }}</div>
            </div>
            <div class="score-box">
                <div class="label">Compattezza</div>
                <div class="value">{{ "%.4f"|format(sol.scores_detail.get('compactness', 0.0)) }}</div>
            </div>
            <div class="score-box">
                <div class="label">Stabilità</div>
                <div class="value">{{ "%.4f"|format(sol.scores_detail.get('stability', 0.0)) }}</div>
            </div>
        </div>
        
        <h4>Distinta Articoli per Bancale</h4>
        <table>
            <tr>
                <th>Bancale</th>
                <th>Tipo Base</th>
                <th>Livello</th>
                <th>Altezza Tot (mm)</th>
                <th>Tot. Pezzi</th>
                <th>Elenco Articoli Contenuti</th>
            </tr>
            {% for item in s_data.pallets %}
            <tr>
                <td><strong>Bancale #{{ item.pallet_id }}</strong></td>
                <td>{{ item.n_epal }}x EPAL</td>
                <td>{{ 'Livello 1 (Pavimento)' if item.z <= 0.1 else 'Livello 2 (Pianale)' }}</td>
                <td>{{ "%.0f"|format(item.total_height) }} mm</td>
                <td><strong>{{ item.panel_count }}</strong> pz</td>
                <td>
                    <ul class="art-list">
                    {% for art in item.articles %}
                        <li>art <strong>{{ art.codice }}</strong> {{ "%.0f"|format(art.l) }}x{{ "%.0f"|format(art.w) }}x{{ "%.0f"|format(art.h) }} mm &nbsp;—&nbsp; <strong>{{ art.count }} pezzi</strong></li>
                    {% endfor %}
                    </ul>
                </td>
            </tr>
            {% endfor %}
        </table>
        
        <h4>Visualizzazione 3D Interattiva (Soluzione #{{ loop.index }})</h4>
        <div class="chart-container" id="plot-{{ loop.index }}">
            {{ plots[loop.index0] | safe }}
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""


def generate_report(solutions: list[Solution], output_dir: str) -> str:
    """Genera report HTML con la distinta articoli sintetica per ciascun bancale."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    sorted_solutions = sorted(solutions, key=lambda s: s.score, reverse=True)
    top_solutions = sorted_solutions[:4]
    
    plots = []
    sol_data = []

    for idx, sol in enumerate(top_solutions):
        rank_label = "BEST SOLUTION" if idx == 0 else f"Alternativa #{idx+1}"
        fig = create_3d_figure(sol, title=f"Soluzione #{idx+1} ({rank_label}) - Rating Score: {sol.score:.4f}")
        plot_html = fig.to_html(full_html=False, include_plotlyjs=False)
        plots.append(plot_html)

        # Prepara la distinta sintetica per bancale
        p_list = []
        for pallet in sol.container.pallets:
            # Conta gli articoli per questo bancale
            counts = Counter()
            dims = {}
            for panel in pallet.all_panels():
                key = (panel.codice_modello, panel.larghezza_mm, panel.profondita_mm, panel.spessore_mm)
                counts[key] += 1

            articles = []
            for (mod, l, w, h), cnt in counts.items():
                articles.append({
                    'codice': mod,
                    'l': l,
                    'w': w,
                    'h': h,
                    'count': cnt
                })

            p_list.append({
                'pallet_id': pallet.pallet_id,
                'n_epal': pallet.n_epal,
                'z': pallet.z,
                'total_height': pallet.total_height,
                'panel_count': pallet.panel_count,
                'articles': articles
            })

        sol_data.append({'pallets': p_list})

    template = Template(HTML_TEMPLATE)
    html_content = template.render(solutions=top_solutions, plots=plots, sol_data=sol_data)
    
    report_path = os.path.join(output_dir, "report_optimacontainer.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return report_path
