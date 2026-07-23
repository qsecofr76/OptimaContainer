"""
Modulo per la visualizzazione 3D delle soluzioni.
"""

from collections import Counter
import plotly.graph_objects as go

from config.defaults import CONTAINER_EDGE_COLOR
from models.solution import Solution


MODEL_COLOR_PALETTE = [
    '#4361EE', '#3A0CA3', '#7209B7', '#F72585', '#4CC9F0',
    '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'
]


def _get_box_edges(x: float, y: float, z: float, l: float, w: float, h: float) -> list[list[float] | None]:
    """Restituisce le coordinate per disegnare i bordi di una scatola."""
    return [
        [x, y, z], [x+l, y, z], [x+l, y+w, z], [x, y+w, z], [x, y, z],
        None,
        [x, y, z+h], [x+l, y, z+h], [x+l, y+w, z+h], [x, y+w, z+h], [x, y, z+h],
        None,
        [x, y, z], [x, y, z+h],
        None,
        [x+l, y, z], [x+l, y, z+h],
        None,
        [x+l, y+w, z], [x+l, y+w, z+h],
        None,
        [x, y+w, z], [x, y+w, z+h]
    ]


def _get_mesh_box_coords(x1: float, x2: float, y1: float, y2: float, z1: float, z2: float):
    """Restituisce x, y, z, i, j, k per un Mesh3d 3D box completo."""
    x = [x1, x2, x2, x1, x1, x2, x2, x1]
    y = [y1, y1, y2, y2, y1, y1, y2, y2]
    z = [z1, z1, z1, z1, z2, z2, z2, z2]
    i = [7, 0, 0, 0, 4, 4, 2, 6, 4, 0, 3, 7]
    j = [3, 4, 1, 2, 5, 6, 3, 7, 0, 1, 2, 6]
    k = [0, 7, 2, 3, 6, 7, 7, 2, 1, 5, 6, 5]
    return x, y, z, i, j, k


def create_3d_figure(solution: Solution, title: str = '', all_panels: list = None) -> go.Figure:
    """Crea visualizzazione 3D interattiva nitida con ingombri visibili in verde (misura completata) o rosso (misura non completata)."""
    fig = go.Figure()
    ct = solution.container.container_type

    # 1. Wireframe Container
    c_edges = _get_box_edges(0, 0, 0, ct.internal_length, ct.internal_width, ct.internal_height)
    cx, cy, cz = [], [], []
    for pt in c_edges:
        if pt is None:
            cx.append(None); cy.append(None); cz.append(None)
        else:
            cx.append(pt[0]); cy.append(pt[1]); cz.append(pt[2])

    fig.add_trace(go.Scatter3d(
        x=cx, y=cy, z=cz,
        mode='lines',
        line=dict(color=CONTAINER_EDGE_COLOR, width=3),
        name="Container Outer Shell",
        hoverinfo='skip'
    ))

    # Calcola totale e piazzati per articolo/modello nell'ordine
    order_placed = Counter()
    placed_panels = []
    for pallet in solution.container.pallets:
        for p in pallet.all_panels():
            placed_panels.append(p)
            order_placed[p.codice_modello] += 1

    order_totals = Counter()
    if all_panels:
        for p in all_panels:
            order_totals[p.codice_modello] += 1
    else:
        for p in placed_panels:
            order_totals[p.codice_modello] += 1

    unique_models = sorted(list(set(p.codice_modello for p in placed_panels)))
    model_colors = {
        mod: MODEL_COLOR_PALETTE[idx % len(MODEL_COLOR_PALETTE)]
        for idx, mod in enumerate(unique_models)
    }

    pallet_summaries = {}

    for pallet in solution.container.pallets:
        # Raggruppamento articoli per questo bancale
        p_counts = Counter()
        p_details = {}
        has_incomplete_measure = False

        for panel in pallet.all_panels():
            mod = panel.codice_modello
            p_counts[mod] += 1
            p_details[mod] = f"{panel.larghezza_mm}x{panel.profondita_mm}x{panel.spessore_mm}mm (Ord: {panel.ordine_id})"

            # Se per questa misura nell'ordine sono rimasti pezzi inevasi -> misura incompleta!
            placed_cnt = order_placed[mod]
            tot_cnt = order_totals.get(mod, placed_cnt)
            if placed_cnt < tot_cnt:
                has_incomplete_measure = True

        art_lines = [f"• <b>{mod}</b>: {cnt} pz ({p_details[mod]})" for mod, cnt in p_counts.items()]
        art_summary = "<br>".join(art_lines)
        pallet_summaries[pallet.pallet_id] = art_summary

        bx1, bx2, by1, by2 = pallet.collo_bbox_xy
        bz1, bz2 = pallet.z, pallet.top_z
        collo_l, collo_w, collo_h = bx2 - bx1, by2 - by1, bz2 - bz1

        # Colore ingombro: ROSSO se ha una misura non completata al 100%, VERDE se completata
        if has_incomplete_measure:
            box_color = '#FF0000'  # Rosso nitido per misura non completata
            box_status = "⚠️ MISURA NON COMPLETATA AL 100% NELL'ORDINE"
            box_label = "Ingombro Rosso (Misura Incompleta)"
        else:
            box_color = '#00FF00'  # Verde brillante per misura completata al 100%
            box_status = "✅ MISURA COMPLETATA AL 100% NELL'ORDINE"
            box_label = "Ingombro Verde (Completato)"

        # ── 1. Trace Ingombro Mesh Trasparente ────────────────
        mx, my, mz, mi, mj, mk = _get_mesh_box_coords(bx1, bx2, by1, by2, bz1, bz2)
        box_hover_text = (
            f"<b>=== INGOMBRO COLLO BANCALE #{pallet.pallet_id} ===</b><br>"
            f"Stato: <b>{box_status}</b><br>"
            f"Livello: {'1 (Pavimento)' if pallet.z <= 0.1 else '2 (Pianale)'}<br>"
            f"Ingombro Totale: {collo_l:.0f} x {collo_w:.0f} x {collo_h:.0f} mm<br>"
            f"Pannelli totali: {pallet.panel_count}<br><br>"
            f"<b>Articoli contenuti:</b><br>{art_summary}"
        )

        fig.add_trace(go.Mesh3d(
            x=mx, y=my, z=mz, i=mi, j=mj, k=mk,
            color=box_color,
            opacity=0.18,
            name=f"Ingombro #{pallet.pallet_id}",
            hoverinfo='text',
            text=box_hover_text,
            showlegend=False
        ))

        # Wireframe bordi dell'ingombro (SEMPRE VISIBILE DI DEFAULT)
        g_edges = _get_box_edges(bx1, by1, bz1, collo_l, collo_w, collo_h)
        gx, gy, gz = [], [], []
        for pt in g_edges:
            if pt is None:
                gx.append(None); gy.append(None); gz.append(None)
            else:
                gx.append(pt[0]); gy.append(pt[1]); gz.append(pt[2])

        fig.add_trace(go.Scatter3d(
            x=gx, y=gy, z=gz,
            mode='lines',
            line=dict(color=box_color, width=3),
            name=f"{box_label} #{pallet.pallet_id}",
            hoverinfo='skip'
        ))

        # ── 2. Base EPAL di legno ─────────────────────────────────────────
        raw_l = 1200.0 * pallet.n_epal
        raw_w = 800.0
        if pallet.layers:
            first_ly = pallet.layers[0]
            pallet_ox = (first_ly.footprint_width - raw_l) / 2
            pallet_oy = (first_ly.footprint_depth - raw_w) / 2
        else:
            pallet_ox, pallet_oy = 0.0, 0.0

        if not pallet.rotated:
            p_draw_x = pallet.x + pallet_ox
            p_draw_y = pallet.y + pallet_oy
            p_draw_l = raw_l
            p_draw_w = raw_w
        else:
            p_draw_x = pallet.x + pallet_oy
            p_draw_y = pallet.y + pallet_ox
            p_draw_l = raw_w
            p_draw_w = raw_l

        px, py, pz, pi, pj, pk = _get_mesh_box_coords(p_draw_x, p_draw_x + p_draw_l, p_draw_y, p_draw_y + p_draw_w, pallet.z, pallet.z + pallet.pallet_height)
        fig.add_trace(go.Mesh3d(
            x=px, y=py, z=pz, i=pi, j=pj, k=pk,
            color='#8B5A2B',
            opacity=0.9,
            name=f"Base EPAL #{pallet.pallet_id}",
            hoverinfo='text',
            text=f"<b>Bancale EPAL #{pallet.pallet_id}</b> ({'Doppio 2400x800' if pallet.n_epal==2 else 'Singolo 1200x800'})<br>Posizione: X={pallet.x:.0f}, Y={pallet.y:.0f}, Z={pallet.z:.0f}"
        ))

        p_edges = _get_box_edges(p_draw_x, p_draw_y, pallet.z, p_draw_l, p_draw_w, pallet.pallet_height)
        pex, pey, pez = [], [], []
        for pt in p_edges:
            if pt is None:
                pex.append(None); pey.append(None); pez.append(None)
            else:
                pex.append(pt[0]); pey.append(pt[1]); pez.append(pt[2])
        fig.add_trace(go.Scatter3d(
            x=pex, y=pey, z=pez,
            mode='lines',
            line=dict(color='#5C3A21', width=2),
            showlegend=False,
            hoverinfo='skip'
        ))

        # Tag etichetta ID Bancale
        fig.add_trace(go.Scatter3d(
            x=[p_draw_x + p_draw_l / 2], y=[p_draw_y + p_draw_w / 2], z=[pallet.z + pallet.pallet_height / 2],
            mode='text',
            text=[f"#{pallet.pallet_id}"],
            textposition='middle center',
            textfont=dict(color='white', size=13),
            showlegend=False,
            hoverinfo='skip'
        ))

        # ── 3. Pianale 30mm ───────────────────────────────────────────────
        if pallet.has_pianale_below:
            eff_l, eff_w = pallet.effective_footprint
            p_mx, p_my, p_mz, p_mi, p_mj, p_mk = _get_mesh_box_coords(pallet.x, pallet.x + eff_l, pallet.y, pallet.y + eff_w, pallet.z - 30.0, pallet.z)
            fig.add_trace(go.Mesh3d(
                x=p_mx, y=p_my, z=p_mz, i=p_mi, j=p_mj, k=p_mk,
                color='#5C4033',
                opacity=0.85,
                name=f"Pianale 30mm #{pallet.pallet_id}",
                hoverinfo='text',
                text=f"Pianale di supporto 30mm sotto bancale #{pallet.pallet_id}"
            ))

        # ── 4. Disegno Nitido dei Singoli Pannelli ─────────────────────────
        layer_offsets = [(0.0, 0.0)]
        current_cum_ox, current_cum_oy = 0.0, 0.0
        for i in range(1, len(pallet.layers)):
            prev_ly = pallet.layers[i - 1]
            curr_ly = pallet.layers[i]
            current_cum_ox += (prev_ly.footprint_width - curr_ly.footprint_width) / 2
            current_cum_oy += (prev_ly.footprint_depth - curr_ly.footprint_depth) / 2
            layer_offsets.append((current_cum_ox, current_cum_oy))

        for layer_idx, layer in enumerate(pallet.layers):
            z_start = pallet.z + pallet.pallet_height + layer.z_offset
            ox, oy = layer_offsets[layer_idx]

            for plc in layer.placements:
                pw, pd = plc.effective_width, plc.effective_depth
                if not pallet.rotated:
                    px_start = pallet.x + ox + plc.x
                    px_end = px_start + pw
                    py_start = pallet.y + oy + plc.y
                    py_end = py_start + pd
                else:
                    px_start = pallet.x + oy + plc.y
                    px_end = px_start + pd
                    py_start = pallet.y + ox + plc.x
                    py_end = py_start + pw

                p_col = model_colors.get(plc.panel.codice_modello, '#E0E0E0')
                pmx, pmy, pmz, pmi, pmj, pmk = _get_mesh_box_coords(px_start, px_end, py_start, py_end, z_start, z_start + plc.panel.spessore_mm)

                fig.add_trace(go.Mesh3d(
                    x=pmx, y=pmy, z=pmz, i=pmi, j=pmj, k=pmk,
                    color=p_col,
                    opacity=0.92,
                    name=f"Modello {plc.panel.codice_modello}",
                    hoverinfo='text',
                    text=(
                        f"<b>Pannello: {plc.panel.codice_modello}</b><br>"
                        f"Bancale #{pallet.pallet_id} | Layer {layer_idx+1}<br>"
                        f"Dim: {plc.panel.larghezza_mm} x {plc.panel.profondita_mm} x {plc.panel.spessore_mm} mm<br>"
                        f"Ordine: {plc.panel.ordine_id}<br>"
                        f"Posizione Container: X=[{px_start:.0f}..{px_end:.0f}], Y=[{py_start:.0f}..{py_end:.0f}]"
                    )
                ))

                # Bordi neri per massima definizione
                pedges = _get_box_edges(px_start, py_start, z_start, px_end - px_start, py_end - py_start, plc.panel.spessore_mm)
                pex, pey, pez = [], [], []
                for pt in pedges:
                    if pt is None:
                        pex.append(None); pey.append(None); pez.append(None)
                    else:
                        pex.append(pt[0]); pey.append(pt[1]); pez.append(pt[2])

                fig.add_trace(go.Scatter3d(
                    x=pex, y=pey, z=pez,
                    mode='lines',
                    line=dict(color='#111111', width=1.5),
                    showlegend=False,
                    hoverinfo='skip'
                ))

    # ── 5. Menu a Tendina Interattivo per Ispezione Bancali ────────────────
    updatemenus = []
    buttons = []

    # Opzione 1: Vista Standard (Ingombri verdi nascosti)
    vis_standard = []
    for trace in fig.data:
        if "Ingombro Verde" in str(trace.name) or "Bordi Verde" in str(trace.name):
            vis_standard.append(False)
        else:
            vis_standard.append(True)

    buttons.append(dict(
        label="Vista Normale (Nascondi Ingombri Verdi)",
        method="update",
        args=[{"visible": vis_standard}, {"title": title if title else "OptimaContainer 3D Viewer"}]
    ))

    # Opzione 2: Mostra Tutti gli Ingombri Verdi
    vis_all_green = [True] * len(fig.data)
    buttons.append(dict(
        label="Mostra TUTTI gli Ingombri Verdi",
        method="update",
        args=[{"visible": vis_all_green}, {"title": "Evidenziati TUTTI gli ingombri reali dei colli (Verde)"}]
    ))

    # Opzione per ogni singolo bancale
    for pid, summary in pallet_summaries.items():
        vis_pid = []
        for trace in fig.data:
            tname = str(trace.name)
            if "Ingombro Verde" in tname or "Bordi Verde" in tname:
                if f"#{pid}" in tname:
                    vis_pid.append(True)
                else:
                    vis_pid.append(False)
            else:
                vis_pid.append(True)

        buttons.append(dict(
            label=f"Ispeziona Bancale #{pid}",
            method="update",
            args=[{"visible": vis_pid}, {"title": f"Bancale #{pid} | Articoli:<br>{summary}"}]
        ))

    updatemenus.append(dict(
        type="dropdown",
        direction="down",
        x=0.01,
        y=0.99,
        xanchor="left",
        yanchor="top",
        buttons=buttons,
        bgcolor="#FFFFFF",
        bordercolor="#00FF00",
        font=dict(size=12, color="#000000")
    ))

    # Layout finale
    fig.update_layout(
        title=title if title else "OptimaContainer 3D Viewer",
        updatemenus=updatemenus,
        scene=dict(
            xaxis=dict(title='X (Lunghezza) [mm]', range=[-100, ct.internal_length + 100]),
            yaxis=dict(title='Y (Larghezza) [mm]', range=[-100, ct.internal_width + 100]),
            zaxis=dict(title='Z (Altezza) [mm]', range=[0, ct.internal_height + 100]),
            aspectmode='data',
            camera=dict(eye=dict(x=1.6, y=1.6, z=1.2))
        ),
        margin=dict(l=0, r=0, b=0, t=50)
    )

    return fig


def save_visualization(fig: go.Figure, filepath: str) -> None:
    """Save as interactive HTML."""
    fig.write_html(filepath)


def export_screenshot(fig: go.Figure, filepath: str) -> None:
    """Export static PNG (requires kaleido)."""
    fig.write_image(filepath)
