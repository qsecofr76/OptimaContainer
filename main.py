"""
OptimaContainer — Entry point con GUI Tkinter e CLI.

Applicazione per l'ottimizzazione del carico di ante e fianchi
su bancali EPAL in container 20'/40'.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import pandas as pd

# ── Assicura che il root del progetto sia nel PYTHONPATH ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.defaults import CONTAINER_TYPES, GAP, MAX_PALLET_LOAD_HEIGHT
from io_handler.input_parser import create_sample_data, parse_csv, parse_excel, parse_dataframe
from models.panel import Panel, reset_panel_counter
from models.pallet import reset_pallet_counter
from models.container import available_container_names, get_container_type
from models.solution import Solution
from scoring.evaluator import evaluate_solution
from visualization.viewer_3d import create_3d_figure, save_visualization
from io_handler.report_generator import generate_report


# ═══════════════════════════════════════════════════════════
#  CLASSE PRINCIPALE GUI
# ═══════════════════════════════════════════════════════════

class OptimaContainerApp:
    """Interfaccia grafica tkinter per OptimaContainer."""

    COLUMNS = [
        ("codice_modello", "Codice Modello", 140),
        ("larghezza_mm", "Larghezza (mm)", 100),
        ("profondita_mm", "Profondità (mm)", 100),
        ("spessore_mm", "Spessore (mm)", 90),
        ("quantita", "Quantità", 70),
        ("ordine_id", "ID Ordine", 100),
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OptimaContainer — Ottimizzazione Carico Container")
        self.root.geometry("1050x720")
        self.root.minsize(900, 600)

        # Stile
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground="#2c3e50")
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Run.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self._build_ui()

    # ─── Costruzione UI ─────────────────────────────────

    def _build_ui(self):
        # Frame principale
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Titolo
        ttk.Label(main, text="🚛 OptimaContainer", style="Title.TLabel").pack(pady=(0, 10))

        # ── Sezione parametri ──
        params_frame = ttk.LabelFrame(main, text="Parametri Container", padding=10)
        params_frame.pack(fill=tk.X, pady=(0, 10))

        # Row 0: Container, Gap, Max height
        ttk.Label(params_frame, text="Tipo Container:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.container_var = tk.StringVar(value=available_container_names()[0])
        container_combo = ttk.Combobox(
            params_frame,
            textvariable=self.container_var,
            values=available_container_names(),
            state="readonly",
            width=18,
        )
        container_combo.grid(row=0, column=1, padx=5, pady=4)

        ttk.Label(params_frame, text="Gap (mm):").grid(row=0, column=2, sticky=tk.W, padx=(15, 5), pady=4)
        self.gap_var = tk.StringVar(value=str(GAP))
        ttk.Entry(params_frame, textvariable=self.gap_var, width=6).grid(row=0, column=3, padx=5, pady=4)

        ttk.Label(params_frame, text="Alt. max bancale (mm):").grid(row=0, column=4, sticky=tk.W, padx=(15, 5), pady=4)
        self.max_height_var = tk.StringVar(value=str(MAX_PALLET_LOAD_HEIGHT))
        ttk.Entry(params_frame, textvariable=self.max_height_var, width=6).grid(row=0, column=5, padx=5, pady=4)

        # Row 1: Generazioni Cerca, Top Soluzioni Mostra
        ttk.Label(params_frame, text="Generazioni (Cerca):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.generations_var = tk.StringVar(value="10")
        ttk.Spinbox(params_frame, from_=1, to=100, textvariable=self.generations_var, width=6).grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(params_frame, text="Top Soluzioni (Mostra):").grid(row=1, column=2, sticky=tk.W, padx=(15, 5), pady=4)
        self.top_k_var = tk.StringVar(value="4")
        ttk.Spinbox(params_frame, from_=1, to=10, textvariable=self.top_k_var, width=6).grid(row=1, column=3, sticky=tk.W, padx=5, pady=4)

        # ── Sezione dati griglia ──
        grid_frame = ttk.LabelFrame(main, text="Pannelli da Caricare", padding=10)
        grid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Barra bottoni griglia
        btn_bar = ttk.Frame(grid_frame)
        btn_bar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(btn_bar, text="➕ Aggiungi riga", command=self._add_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="🗑 Rimuovi selezionata", command=self._remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="📂 Carica CSV/Excel", command=self._load_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="💾 Salva CSV", command=self._save_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="🧪 Dati Demo", command=self._load_demo_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="🗑 Svuota tutto", command=self._clear_all).pack(side=tk.LEFT, padx=2)

        # Treeview come griglia editabile
        tree_container = ttk.Frame(grid_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        cols = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=12)
        for col_id, col_name, col_width in self.COLUMNS:
            self.tree.heading(col_id, text=col_name)
            self.tree.column(col_id, width=col_width, minwidth=60)

        scroll_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)

        # ── Sezione esecuzione ──
        run_frame = ttk.Frame(main)
        run_frame.pack(fill=tk.X, pady=(0, 5))

        self.run_btn = ttk.Button(
            run_frame,
            text="🚀 Avvia Ottimizzazione",
            style="Run.TButton",
            command=self._run_optimization,
        )
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(run_frame, mode="determinate", length=400)
        self.progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(run_frame, textvariable=self.status_var, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)

        # ── Log area ──
        log_frame = ttk.LabelFrame(main, text="Log", padding=5)
        log_frame.pack(fill=tk.X)

        self.log_text = tk.Text(log_frame, height=5, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=tk.X)

    # ─── Operazioni griglia ─────────────────────────────

    def _add_row(self, values: tuple = None):
        """Aggiunge una riga vuota o con valori precompilati."""
        if values is None:
            values = ("", "", "", "", "1", "")
        self.tree.insert("", tk.END, values=values)

    def _remove_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Seleziona una riga da rimuovere.")
            return
        for item in selected:
            self.tree.delete(item)

    def _clear_all(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _on_double_click(self, event):
        """Permette di editare una cella con doppio click."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        col_idx = int(column.replace("#", "")) - 1

        # Ottieni posizione e valore corrente
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return

        x, y, w, h = bbox
        current_value = self.tree.item(item, "values")[col_idx]

        # Crea entry sovrapposta
        entry = ttk.Entry(self.tree, width=w // 8)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()

        def _save(e=None):
            new_val = entry.get()
            values = list(self.tree.item(item, "values"))
            values[col_idx] = new_val
            self.tree.item(item, values=values)
            entry.destroy()

        entry.bind("<Return>", _save)
        entry.bind("<FocusOut>", _save)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _load_file(self):
        """Carica dati da file CSV o Excel."""
        filepath = filedialog.askopenfilename(
            title="Seleziona file",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx;*.xls"),
                ("All files", "*.*"),
            ],
        )
        if not filepath:
            return

        try:
            if filepath.endswith(".csv"):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            self._clear_all()
            for _, row in df.iterrows():
                self._add_row(
                    (
                        str(row.get("codice_modello", "")),
                        str(row.get("larghezza_mm", "")),
                        str(row.get("profondita_mm", "")),
                        str(row.get("spessore_mm", "")),
                        str(int(row.get("quantita", 1))),
                        str(row.get("ordine_id", "")),
                    )
                )
            self._log(f"✅ Caricati {len(df)} righe da {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare il file:\n{e}")

    def _save_csv(self):
        """Salva i dati della griglia in un CSV."""
        filepath = filedialog.asksaveasfilename(
            title="Salva CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not filepath:
            return

        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            rows.append(
                {
                    "codice_modello": values[0],
                    "larghezza_mm": values[1],
                    "profondita_mm": values[2],
                    "spessore_mm": values[3],
                    "quantita": values[4],
                    "ordine_id": values[5],
                }
            )
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)
        self._log(f"💾 Salvato CSV: {os.path.basename(filepath)}")

    def _load_demo_data(self):
        """Carica i dati demo nella griglia."""
        self._clear_all()
        demo_rows = [
            ("ANTA-60x40", "400", "600", "18", "4", "ORD-001"),
            ("ANTA-70x45", "450", "700", "22", "3", "ORD-001"),
            ("ANTA-80x50", "500", "800", "18", "2", "ORD-001"),
            ("ANTA-90x45", "450", "900", "22", "4", "ORD-001"),
            ("ANTA-60x40", "400", "600", "18", "2", "ORD-002"),
            ("ANTA-70x45", "450", "700", "22", "2", "ORD-002"),
            ("FIANCO-200x60", "600", "2000", "18", "2", "ORD-003"),
            ("FIANCO-180x50", "500", "1800", "18", "3", "ORD-003"),
            ("FIANCO-220x58", "580", "2200", "22", "2", "ORD-003"),
        ]
        for row in demo_rows:
            self._add_row(row)
        self._log("🧪 Dati demo caricati (24 pannelli, 3 ordini)")

    # ─── Estrazione dati dalla griglia ──────────────────

    def _get_panels_from_grid(self) -> Optional[list[Panel]]:
        """Legge i dati dalla griglia e crea la lista di Panel."""
        rows = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            try:
                rows.append(
                    {
                        "codice_modello": str(values[0]).strip(),
                        "larghezza_mm": float(values[1]),
                        "profondita_mm": float(values[2]),
                        "spessore_mm": float(values[3]),
                        "quantita": int(values[4]),
                        "ordine_id": str(values[5]).strip(),
                    }
                )
            except (ValueError, IndexError) as e:
                messagebox.showerror(
                    "Errore dati",
                    f"Errore nella riga '{values}': {e}\n\n"
                    "Verifica che tutte le colonne numeriche contengano valori validi.",
                )
                return None

        if not rows:
            messagebox.showwarning("Attenzione", "Nessun pannello inserito!")
            return None

        df = pd.DataFrame(rows)
        try:
            reset_panel_counter()
            panels = parse_dataframe(df)
        except ValueError as e:
            messagebox.showerror("Errore validazione", str(e))
            return None

        return panels

    # ─── Esecuzione ottimizzazione ──────────────────────

    def _run_optimization(self):
        """Avvia l'algoritmo di ottimizzazione in un thread separato."""
        panels = self._get_panels_from_grid()
        if panels is None:
            return

        container_name = self.container_var.get()
        try:
            gap = float(self.gap_var.get())
            max_h = float(self.max_height_var.get())
        except ValueError:
            messagebox.showerror("Errore", "Gap e altezza max devono essere numeri validi.")
            return

        # Disabilita il bottone
        self.run_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self.status_var.set("Ottimizzazione in corso...")

        # Esegui in un thread separato
        thread = threading.Thread(
            target=self._optimization_worker,
            args=(panels, container_name, gap, max_h),
            daemon=True,
        )
        thread.start()

    def _optimization_worker(self, panels, container_name, gap, max_h):
        """Worker thread per l'ottimizzazione."""
        try:
            from optimizer.genetic import run_genetic_algorithm
            from config import defaults

            # Override parametri configurabili
            orig_gap = defaults.GAP
            orig_max = defaults.MAX_PALLET_LOAD_HEIGHT
            try:
                n_generations = int(self.generations_var.get())
            except ValueError:
                n_generations = 10

            try:
                top_k = int(self.top_k_var.get())
            except ValueError:
                top_k = 4

            defaults.GAP = gap
            defaults.MAX_PALLET_LOAD_HEIGHT = max_h

            container_type = get_container_type(container_name)
            self._log(f"🚀 Avvio ottimizzazione: {len(panels)} pannelli → {container_name}")
            self._log(f"   Generazioni GA: {n_generations} | Top Soluzioni: {top_k}")
            self._log(f"   Gap: {gap}mm | Altezza max: {max_h}mm")

            def progress_cb(gen, total, best_score):
                pct = (gen / total) * 100
                self.root.after(0, lambda: self.progress.configure(value=pct))
                self.root.after(
                    0, lambda: self.status_var.set(
                        f"Generazione {gen}/{total} — Miglior score: {best_score:.4f}"
                    ),
                )

            reset_pallet_counter()
            solutions = run_genetic_algorithm(
                panels=panels,
                container_type=container_type,
                score_fn=evaluate_solution,
                config={'generations': n_generations},
                progress_callback=progress_cb,
            )

            # Ripristina defaults
            defaults.GAP = orig_gap
            defaults.MAX_PALLET_LOAD_HEIGHT = orig_max

            if not solutions:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Nessuna soluzione", "L'algoritmo non ha trovato soluzioni valide."
                ))
                return

            # Prendi le top_k soluzioni
            top_solutions = sorted(solutions, key=lambda s: s.score, reverse=True)[:top_k]

            self._log(f"✅ Trovate {len(solutions)} soluzioni uniche — Generazione Top {len(top_solutions)} Soluzioni")
            for i, sol in enumerate(top_solutions):
                self._log(
                    f"   #{i + 1} ({'BEST' if i==0 else 'Alternativa ' + str(i+1)}): Score={sol.score:.4f}, "
                    f"Bancali={sol.pallet_count}, "
                    f"Pannelli={sol.panel_count}/{sol.total_order_panels} ({sol.placed_pct:.1f}%), "
                    f"Utilizzo={sol.utilization_pct:.1f}%"
                )

            # Genera output
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)

            # Report HTML completo con confronto Top 4
            report_path = generate_report(top_solutions, output_dir, panels, log_fn=self._log)
            self._log(f"📄 Report HTML generato con successo: {report_path}")

            best_path = os.path.join(output_dir, "best_solution_3d.html")

            report_abs = os.path.abspath(report_path)

            def _open_report(r_path=report_abs):
                try:
                    if hasattr(os, 'startfile'):
                        os.startfile(r_path)
                    else:
                        import webbrowser
                        import pathlib
                        webbrowser.open(pathlib.Path(r_path).as_uri())
                except Exception as err:
                    self._log(f"⚠️ Impossibile aprire il browser automaticamente: {err}")

            self._log(f"🌐 Apertura automatica report nel browser: {report_abs}")
            self.root.after(0, _open_report)

            self.root.after(0, lambda: self.status_var.set("✅ Completato! Report aperto nel browser."))
            self.root.after(0, lambda: self.progress.configure(value=100))
            self.root.after(
                100,
                lambda b_path=best_path, r_path=report_path, n_sols=len(solutions), best_s=top_solutions[0]: messagebox.showinfo(
                    "Completato",
                    f"Ottimizzazione completata!\n\n"
                    f"Soluzioni trovate: {n_sols}\n"
                    f"Miglior score: {best_s.score:.4f}\n"
                    f"Pannelli caricati: {best_s.panel_count} / {best_s.total_order_panels} ({best_s.placed_pct:.1f}%)\n"
                    f"Utilizzo volume: {best_s.utilization_pct:.1f}%\n\n"
                    f"Report aperto nel browser:\n{r_path}",
                ),
            )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.root.after(0, lambda: messagebox.showerror("Errore", f"Errore durante l'ottimizzazione:\n{e}"))
            self._log(f"❌ Errore: {e}\n{tb}")
        finally:
            self.root.after(0, lambda: self.run_btn.configure(state=tk.NORMAL))

    # ─── Logging ────────────────────────────────────────

    def _log(self, msg: str):
        """Aggiunge un messaggio al log (thread-safe)."""
        def _append():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _append)


# ═══════════════════════════════════════════════════════════
#  MODALITÀ CLI
# ═══════════════════════════════════════════════════════════

def run_cli():
    """Esecuzione da riga di comando."""
    parser = argparse.ArgumentParser(
        description="OptimaContainer — Ottimizzazione Carico Container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", help="File CSV o Excel con i pannelli")
    parser.add_argument(
        "--container", "-c",
        default="40ft Standard",
        choices=available_container_names(),
        help="Tipo di container (default: 40ft Standard)",
    )
    parser.add_argument("--gap", type=float, default=GAP, help=f"Gap in mm (default: {GAP})")
    parser.add_argument(
        "--max-height", type=float, default=MAX_PALLET_LOAD_HEIGHT,
        help=f"Altezza max bancale in mm (default: {MAX_PALLET_LOAD_HEIGHT})",
    )
    parser.add_argument("--generations", "-g", type=int, default=10, help="Numero di generazioni GA (default: 10)")
    parser.add_argument("--top-k", "-k", type=int, default=4, help="Numero di soluzioni principali da mostrare (default: 4)")
    parser.add_argument("--output", "-o", default="output", help="Directory di output")
    parser.add_argument("--demo", action="store_true", help="Usa dati demo")

    args = parser.parse_args()

    # Carica pannelli
    if args.demo:
        reset_panel_counter()
        panels = create_sample_data()
        print(f"Caricati {len(panels)} pannelli demo")
    elif args.input:
        reset_panel_counter()
        if args.input.endswith(".csv"):
            panels = parse_csv(args.input)
        else:
            panels = parse_excel(args.input)
        print(f"Caricati {len(panels)} pannelli da {args.input}")
    else:
        print("Errore: specificare --input <file> o --demo")
        sys.exit(1)

    from optimizer.genetic import run_genetic_algorithm
    from config import defaults

    defaults.GAP = args.gap
    defaults.MAX_PALLET_LOAD_HEIGHT = args.max_height

    container_type = get_container_type(args.container)

    print(f"Container: {args.container}")
    print(f"Generazioni (GA): {args.generations} | Top Soluzioni: {args.top_k}")
    print(f"Gap: {args.gap}mm | Altezza max: {args.max_height}mm")
    print(f"Avvio ottimizzazione...")

    def progress_cb(gen, total, best):
        bar_len = 40
        filled = int(bar_len * gen / total)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] Gen {gen}/{total} - Score: {best:.4f}", end="", flush=True)

    reset_pallet_counter()
    solutions = run_genetic_algorithm(
        panels=panels,
        container_type=container_type,
        score_fn=evaluate_solution,
        config={'generations': args.generations},
        progress_callback=progress_cb,
    )
    print()

    if not solutions:
        print("Nessuna soluzione trovata!")
        sys.exit(1)

    top = sorted(solutions, key=lambda s: s.score, reverse=True)[:args.top_k]

    print(f"\n{'=' * 50}")
    print(f"Trovate {len(solutions)} soluzioni uniche — Generazione Top 4 Soluzioni")
    print(f"{'=' * 50}")
    for i, sol in enumerate(top):
        print(f"--- Soluzione #{i+1} ({'BEST' if i==0 else 'Alternativa ' + str(i+1)}) ---")
        print(sol.summary())
        print()

    # Output
    os.makedirs(args.output, exist_ok=True)
    report_path = generate_report(top, args.output, panels)
    print(f"[REPORT HTML COMPLETO] {report_path}")

    # File 3D e report generati da generate_report
    for idx, sol in enumerate(top):
        sol_filename = f"solution_{idx+1}_3d.html"
        sol_path = os.path.join(args.output, sol_filename)
        print(f"[3D VIEW #{idx+1}] {sol_path}")


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

def main():
    """Entry point: lancia GUI o CLI in base agli argomenti."""
    if len(sys.argv) > 1:
        run_cli()
    else:
        root = tk.Tk()
        app = OptimaContainerApp(root)
        root.mainloop()


if __name__ == "__main__":
    main()
