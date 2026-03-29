#!/usr/bin/env python3
# DDEV Manager Pro - Versione Stabile Definitiva (v5)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import json
import webbrowser
import threading
from pathlib import Path

THEMES = {
    'light': {
        'bg': '#f0f0f0', 'fg': '#000000',
        'entry_bg': '#ffffff', 'entry_fg': '#000000',
        'tree_bg': '#ffffff', 'tree_fg': '#000000', 'tree_selected': '#0078d7',
        'log_bg': '#ffffff', 'info': 'blue', 'success': 'green', 'error': 'red', 'warning': 'orange'
    },
    'dark': {
        'bg': '#1e1e1e', 'fg': '#e0e0e0',
        'entry_bg': '#333333', 'entry_fg': '#ffffff',
        'tree_bg': '#252526', 'tree_fg': '#e0e0e0', 'tree_selected': '#37373d',
        'log_bg': '#1e1e1e', 'info': '#4da6ff', 'success': '#b5cea8', 'error': '#f44747', 'warning': '#d7ba7d'
    }
}


class DDEVManager:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.root.title("DDEV Project Manager Pro")
        # Icona finestra
        icon_path = Path(__file__).parent / "icon.png"
        if icon_path.exists():
            try:
                img = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, img)
            except Exception:
                pass
        self.width, self.height = 1100, 750
        self.config_path = Path.home() / ".ddev_manager.json"
        cfg = self.load_config()
        self.projects = cfg.get('projects', {})
        self.current_theme = cfg.get('theme', 'dark')
        self.all_btns = []   # tutti i pulsanti che si disabilitano durante operazioni
        self.btns = {}
        self.style = ttk.Style()
        self.setup_ui()
        self.apply_theme(self.current_theme)
        self.center_window()
        self.root.deiconify()
        self.refresh_list()

    def center_window(self):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - self.width) // 2, (sh - self.height) // 2
        self.root.geometry(f'{self.width}x{self.height}+{x}+{y}')

    def load_config(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump({'theme': self.current_theme, 'projects': self.projects}, f, indent=2)

    # ─── UI Setup ────────────────────────────────────────────────────────────

    def _reg_btn(self, parent, text, cmd, **pack_opts):
        """Crea un pulsante, lo registra in all_btns e lo mostra."""
        b = ttk.Button(parent, text=text, command=cmd)
        self.all_btns.append(b)
        b.pack(**pack_opts)
        return b

    def setup_ui(self):
        # ── Toolbar ──
        tb = ttk.Frame(self.root, padding=10)
        tb.pack(fill='x')
        self._reg_btn(tb, "➕ Nuovo",     self.add_project_dialog,          side='left', padx=5)
        self._reg_btn(tb, "🔄 Refresh",   self.refresh_list,                side='left', padx=5)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=10)
        self._reg_btn(tb, "🚀 Start Tutti", lambda: self.bulk_action('start'), side='left', padx=5)
        self._reg_btn(tb, "🛑 Stop Tutti",  lambda: self.bulk_action('stop'),  side='left', padx=5)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=10)
        self._reg_btn(tb, "⚡ Poweroff",    self.ddev_poweroff,              side='left', padx=5)
        # Esci e Tema: sempre attivi, non in all_btns
        ttk.Button(tb, text="❌ Esci",   command=self.root.quit).pack(side='right', padx=5)
        ttk.Button(tb, text="🌓 Tema",   command=self.toggle_theme).pack(side='right', padx=5)
        self._reg_btn(tb, "🔍 Debug URL", self.debug_selected,              side='right', padx=5)

        # ── Treeview ──
        pw = ttk.PanedWindow(self.root, orient='vertical')
        pw.pack(fill='both', expand=True, padx=10, pady=5)
        lf = ttk.Frame(pw); pw.add(lf, weight=3)
        cols = ('nome', 'path', 'tipo', 'stato', 'url')
        self.tree = ttk.Treeview(lf, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=100)
        self.tree.column('path', width=300)
        self.tree.column('url', width=200)
        sc = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda e: self.open_site())
        self.tree.bind('<Button-3>', self.show_context_menu)

        # ── Console ──
        log_f = ttk.LabelFrame(pw, text="Output Console", padding=5)
        pw.add(log_f, weight=1)
        self.log_text = scrolledtext.ScrolledText(log_f, wrap='word', height=8, font=('monospace', 10))
        self.log_text.pack(fill='both', expand=True)

        # ── Controlli Rapidi ──
        ctrl = ttk.LabelFrame(self.root, text="Controlli Rapidi", padding=10)
        ctrl.pack(fill='x', padx=10, pady=5)
        for a in ['Start', 'Stop', 'Restart', 'Delete']:
            b = self._reg_btn(ctrl, a, lambda x=a.lower(): self.project_action(x), side='left', padx=2)
            self.btns[a.lower()] = b
        ttk.Separator(ctrl, orient='vertical').pack(side='left', fill='y', padx=10)
        self._reg_btn(ctrl, "🌐 Sito",       self.open_site,      side='left', padx=2)
        self._reg_btn(ctrl, "🐘 Adminer",    self.open_adminer,   side='left', padx=2)
        self._reg_btn(ctrl, "📂 PHPMyAdmin", self.open_pma,       side='left', padx=2)
        self._reg_btn(ctrl, "📁 Cartella",   self.open_folder,    side='left', padx=2)

        # ── Status Bar ──
        self.status = ttk.Label(self.root, text="Pronto", relief='sunken', anchor='w', padding=5)
        self.status.pack(fill='x', side='bottom')

        # ── Context Menu ──
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="ℹ️ Dettagli", command=self.show_project_details)
        self.context_menu.add_separator()
        for lbl, act in [("▶️ Start", 'start'), ("⏹️ Stop", 'stop'), ("🔄 Restart", 'restart')]:
            self.context_menu.add_command(label=lbl, command=lambda x=act: self.project_action(x))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ Rimuovi", command=lambda: self.project_action('delete'))

    # ─── UI State ────────────────────────────────────────────────────────────

    def set_ui_busy(self, msg="Operazione in corso..."):
        for b in self.all_btns:
            b.config(state='disabled')
        self.status.config(text=f"⏳ {msg}")

    def set_ui_idle(self):
        for b in self.all_btns:
            b.config(state='normal')
        self.status.config(text="Pronto")
        self.refresh_list()

    # ─── Theme ───────────────────────────────────────────────────────────────

    def apply_theme(self, t):
        self.current_theme = t
        c = THEMES[t]
        self.style.theme_use('clam')
        self.style.configure('.', background=c['bg'], foreground=c['fg'])
        self.style.configure('Treeview', background=c['tree_bg'], foreground=c['tree_fg'],
                             fieldbackground=c['tree_bg'])
        self.style.map('Treeview', background=[('selected', c['tree_selected'])])
        self.style.configure('TEntry', fieldbackground=c['entry_bg'], foreground=c['entry_fg'])
        self.log_text.configure(bg=c['log_bg'], fg=c['fg'], insertbackground=c['fg'])
        for k in ['info', 'success', 'error', 'warning']:
            self.log_text.tag_config(k, foreground=c[k])
        self.save_config()

    def toggle_theme(self):
        self.apply_theme('dark' if self.current_theme == 'light' else 'light')

    # ─── Logging ─────────────────────────────────────────────────────────────

    def log(self, m, t='info'):
        self.log_text.insert('end', f"{m}\n", t)
        self.log_text.see('end')
        self.root.update()

    def show_context_menu(self, e):
        i = self.tree.identify_row(e.y)
        if i:
            self.tree.selection_set(i)
            self.context_menu.post(e.x_root, e.y_root)

    # ─── DDEV Commands ───────────────────────────────────────────────────────

    def ddev_poweroff(self):
        if messagebox.askyesno("Poweroff", "Spegnere tutti i progetti e resettare il router DDEV?"):
            def run():
                self.root.after(0, lambda: self.set_ui_busy("DDEV Poweroff..."))
                self.log("🛑 DDEV Poweroff in corso...")
                subprocess.run(['ddev', 'poweroff'])
                self.log("✅ Router resettato. Riavvia il progetto.", 'success')
                self.root.after(0, self.set_ui_idle)
            threading.Thread(target=run, daemon=True).start()

    # ─── URL Discovery ───────────────────────────────────────────────────────

    def get_service_url_from_env(self, container_name):
        """DDEV 1.25: legge HTTPS_EXPOSE/HTTP_EXPOSE + VIRTUAL_HOST dalle env vars del container."""
        try:
            r = subprocess.run(
                ['docker', 'inspect', '--format', '{{range .Config.Env}}{{.}}\n{{end}}', container_name],
                capture_output=True, text=True)
            if r.returncode != 0:
                return None
            virtual_host, https_port, http_port = None, None, None
            for line in r.stdout.split('\n'):
                if line.startswith('VIRTUAL_HOST='):
                    virtual_host = line.split('=', 1)[1].strip()
                elif line.startswith('HTTPS_EXPOSE='):
                    val = line.split('=', 1)[1].strip()
                    https_port = val.split(':')[0]
                elif line.startswith('HTTP_EXPOSE='):
                    val = line.split('=', 1)[1].strip()
                    http_port = val.split(':')[0]
            if virtual_host and https_port:
                return f"https://{virtual_host}:{https_port}"
            if virtual_host and http_port:
                return f"http://{virtual_host}:{http_port}"
        except Exception:
            pass
        return None

    def get_urls(self, raw, name, project_path=None):
        res = {
            'site': (raw or {}).get('primary_url') or f"https://{name}.ddev.site",
            'adminer': None, 'phpmyadmin': None
        }
        for u in (raw or {}).get('db_utils', []):
            un = u.get('name', '').lower()
            url = u.get('https_url') or u.get('url') or u.get('http_url')
            if 'adminer' in un and not res['adminer']: res['adminer'] = url
            elif 'phpmyadmin' in un and not res['phpmyadmin']: res['phpmyadmin'] = url
        for svc, data in (raw or {}).get('extra_services', {}).items():
            url = data.get('https_url') or data.get('http_url')
            if 'adminer' in svc.lower() and not res['adminer']: res['adminer'] = url
            elif 'phpmyadmin' in svc.lower() and not res['phpmyadmin']: res['phpmyadmin'] = url
        if not res['adminer']:
            res['adminer'] = self.get_service_url_from_env(f"ddev-{name}-adminer")
        if not res['phpmyadmin']:
            res['phpmyadmin'] = self.get_service_url_from_env(f"ddev-{name}-phpmyadmin")
        return res

    # ─── Debug ───────────────────────────────────────────────────────────────

    def debug_selected(self):
        sel = self.get_selected()
        if not sel:
            self.log("⚠️ Seleziona un progetto prima.", 'warning'); return
        n, d = sel
        threading.Thread(target=self._run_debug, args=(n, d), daemon=True).start()

    def _run_debug(self, name, d):
        self.root.after(0, lambda: self.set_ui_busy("Debug URL..."))
        self.log("=" * 30, 'info')
        self.log(f"DEBUG: {name}", 'warning')
        r = subprocess.run(['ddev', 'describe', '-j'], cwd=d['path'], capture_output=True, text=True)
        raw = self.parse_ddev_json(r.stdout)
        status = (raw or {}).get('status', 'unknown')
        self.log(f"Status: {status}", 'info')
        if status != 'running':
            self.log("⛔ Progetto non attivo! Avvialo prima.", 'error')
            self.log("=" * 30, 'info')
            self.root.after(0, self.set_ui_idle); return
        self.log(f"primary_url: {(raw or {}).get('primary_url', 'N/A')}")
        self.log(f"db_utils: {(raw or {}).get('db_utils', [])}")
        self.log(f"extra_services: {list((raw or {}).get('extra_services', {}).keys())}")
        self.log("-" * 20, 'info')
        for svc in ['adminer', 'phpmyadmin']:
            cname = f"ddev-{name}-{svc}"
            ps = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True)
            if cname not in ps.stdout:
                self.log(f"❌ {svc}: container non attivo", 'error'); continue
            url = self.get_service_url_from_env(cname)
            if url:
                self.log(f"✅ {svc}: {url}", 'success')
            else:
                self.log(f"⚠️  {svc}: attivo ma URL non rilevato", 'warning')
                r2 = subprocess.run(['docker', 'inspect', '--format',
                                     '{{range .Config.Env}}{{.}}\n{{end}}', cname],
                                    capture_output=True, text=True)
                for line in r2.stdout.split('\n'):
                    if any(k in line for k in ['EXPOSE', 'VIRTUAL', 'HOST']):
                        self.log(f"  {line.strip()}")
        self.log("=" * 30, 'info')
        self.root.after(0, self.set_ui_idle)

    # ─── JSON Parsing ────────────────────────────────────────────────────────

    def parse_ddev_json(self, output):
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    d = json.loads(line)
                    raw = d.get('raw', d)
                    if 'primary_url' in raw or 'status' in raw:
                        return raw
                except Exception:
                    continue
        return None

    # ─── Project Management ──────────────────────────────────────────────────

    def add_project_dialog(self):
        import re

        def strip_ansi(text):
            return re.sub(r'(\x1b|\#)\[[0-9;]*m', '', text).strip()

        nuovo_btn = next((b for b in self.all_btns if "Nuovo" in str(b.cget('text'))), None)
        if nuovo_btn:
            nuovo_btn.config(state='disabled')

        dlg = tk.Toplevel(self.root)
        dlg.title("Nuovo Progetto")
        dlg.geometry("500x560")
        dlg.transient(self.root)
        dlg.grab_set()
        c = THEMES[self.current_theme]
        dlg.configure(bg=c['bg'])

        def on_close():
            if nuovo_btn: nuovo_btn.config(state='normal')
            dlg.destroy()
        dlg.protocol("WM_DELETE_WINDOW", on_close)

        # StringVar per ogni campo — lettura sempre affidabile
        sv_path = tk.StringVar()
        sv_name = tk.StringVar()
        sv_type = tk.StringVar(value='php')
        sv_dbn  = tk.StringVar(value='db')
        sv_dbu  = tk.StringVar(value='db')
        sv_dbp  = tk.StringVar(value='db')

        def LabelEntry(lbl, sv, **kw):
            ttk.Label(dlg, text=lbl).pack(anchor='w', padx=20, pady=(6, 0))
            e = tk.Entry(dlg, textvariable=sv, bg=c['entry_bg'], fg=c['entry_fg'],
                         insertbackground=c['fg'], relief='flat', bd=5, **kw)
            e.pack(fill='x', padx=20, pady=2)
            return e

        # ── Percorso ──
        ttk.Label(dlg, text="Percorso:").pack(anchor='w', padx=20, pady=(10, 0))
        rf = ttk.Frame(dlg); rf.pack(fill='x', padx=20)
        tk.Entry(rf, textvariable=sv_path, bg=c['entry_bg'], fg=c['entry_fg'],
                 relief='flat', bd=5).pack(side='left', fill='x', expand=True)

        def pick_dir():
            path = filedialog.askdirectory(parent=dlg)
            if path:
                sv_path.set(path)
                folder = Path(path).name.lower().replace(' ', '-')
                if not sv_name.get():
                    sv_name.set(folder)
                    # Auto-popola DB se ancora ai valori di default
                    if sv_dbn.get() == 'db': sv_dbn.set(folder[:16])
                    if sv_dbu.get() == 'db': sv_dbu.set(folder[:16])
                    # Password: NON auto-riempita — rimane 'db' finché l'utente non la cambia
            dlg.lift(); dlg.focus_force()

        ttk.Button(rf, text="...", command=pick_dir).pack(side='right', padx=(4, 0))

        # ── Campi ──
        LabelEntry("Nome progetto (minuscolo, no spazi):", sv_name)
        ttk.Label(dlg, text="Tipo:").pack(anchor='w', padx=20, pady=(6, 0))
        ttk.Combobox(dlg, textvariable=sv_type,
                     values=['php', 'laravel', 'wordpress', 'python'],
                     state='readonly').pack(fill='x', padx=20)
        LabelEntry("DB Name:",     sv_dbn)
        LabelEntry("User DB:",     sv_dbu)
        LabelEntry("Password DB:", sv_dbp, show='')

        # Forza nome DDEV-valido: solo lettere, cifre e trattini
        def on_name_changed(*_):
            import re as _re
            raw = sv_name.get()
            # Sostituisce qualsiasi carattere non valido (punti, underscore, slash...) con '-'
            clean = _re.sub(r'[^a-z0-9-]', '-', raw.lower())
            # Rimuove trattini multipli consecutivi
            clean = _re.sub(r'-+', '-', clean).strip('-')
            if raw != clean:
                sv_name.set(clean)
            if sv_dbn.get() == 'db' and clean: sv_dbn.set(clean[:16])
            if sv_dbu.get() == 'db' and clean: sv_dbu.set(clean[:16])

        sv_name.trace_add('write', on_name_changed)

        def save():
            p    = sv_path.get().strip()
            n    = sv_name.get().strip()
            db   = sv_dbn.get().strip() or n or 'db'
            user = sv_dbu.get().strip() or n or 'db'
            pwd  = sv_dbp.get().strip() or 'db'
            if not p or not n:
                messagebox.showwarning("Attenzione", "Inserisci percorso e nome.", parent=dlg)
                return
            res = subprocess.run(
                ['ddev', 'config', '--project-name', n, '--project-type', sv_type.get()],
                cwd=p, capture_output=True, text=True, input='\n')
            ok = (res.returncode == 0
                  or 'successfully' in res.stdout.lower()
                  or Path(p, '.ddev', 'config.yaml').exists())
            if ok:
                self.projects[n] = {'path': p, 'tipo': sv_type.get(),
                                    'db_name': db, 'db_user': user, 'db_pass': pwd}
                self.save_config(); self.refresh_list()
                if nuovo_btn: nuovo_btn.config(state='normal')
                dlg.destroy()
            else:
                err = strip_ansi(res.stderr or res.stdout or "Errore sconosciuto")
                messagebox.showerror("Errore DDEV", err, parent=dlg)

        ttk.Button(dlg, text="✅ Crea Progetto", command=save).pack(pady=20)

    def show_project_details(self):
        """Mostra i dettagli del progetto selezionato in una finestra read-only."""
        sel = self.get_selected()
        if not sel:
            self.log("⚠️ Seleziona un progetto dalla lista.", 'warning'); return
        n, d = sel
        c = THEMES[self.current_theme]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Dettagli: {n}")
        dlg.geometry("460x360")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=c['bg'])

        def Row(label, value):
            f = ttk.Frame(dlg); f.pack(fill='x', padx=20, pady=4)
            ttk.Label(f, text=f"{label}:", width=14, anchor='w').pack(side='left')
            sv = tk.StringVar(value=str(value))
            e = tk.Entry(f, textvariable=sv, bg=c['entry_bg'], fg=c['entry_fg'],
                         relief='flat', bd=4, state='readonly',
                         readonlybackground=c['entry_bg'])
            e.pack(side='left', fill='x', expand=True)

        ttk.Label(dlg, text=f"📋 Progetto: {n}",
                  font=('sans-serif', 12, 'bold')).pack(pady=(14, 6))
        ttk.Separator(dlg, orient='horizontal').pack(fill='x', padx=20)
        Row("Percorso",  d.get('path', '-'))
        Row("Tipo",      d.get('tipo', '-'))
        Row("DB Name",   d.get('db_name', 'db'))
        Row("User DB",   d.get('db_user', 'db'))
        Row("Password",  d.get('db_pass', 'db'))
        Row("URL",       d.get('url', '-'))
        ttk.Separator(dlg, orient='horizontal').pack(fill='x', padx=20, pady=8)
        ttk.Button(dlg, text="Chiudi", command=dlg.destroy).pack()

    def refresh_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for n, d in self.projects.items():
            try:
                r = subprocess.run(['ddev', 'describe', '-j'], cwd=d['path'],
                                   capture_output=True, text=True, timeout=4)
                raw = self.parse_ddev_json(r.stdout)
                s = "🟢 Attivo" if raw and raw.get('status') == 'running' else "🔴 Stop"
                url = (raw or {}).get('primary_url', d.get('url', ''))
            except Exception:
                s, url = "❓ Errore", d.get('url', '')
            self.tree.insert('', 'end', values=(n, d['path'], d['tipo'], s, url))

    def get_selected(self):
        s = self.tree.selection()
        if not s:
            return None
        n = self.tree.item(s[0])['values'][0]
        return n, self.projects.get(n)

    def project_action(self, a):
        sel = self.get_selected()
        if not sel:
            return
        n, d = sel
        if a == 'delete':
            if messagebox.askyesno("Conferma", f"Rimuovere '{n}' dalla lista?"):
                del self.projects[n]; self.save_config(); self.refresh_list()
            return
        self.set_ui_busy(f"{a.capitalize()} {n}...")
        threading.Thread(target=self.run_ddev_action, args=(a, n, d), daemon=True).start()

    def bulk_action(self, a):
        if not self.projects:
            return
        if not messagebox.askyesno("Conferma", f"{a.capitalize()} tutti i progetti?"):
            return
        def run():
            self.root.after(0, lambda: self.set_ui_busy(f"{a.capitalize()} tutti..."))
            for n, d in self.projects.items():
                self.log(f"🚀 {a} {n}...")
                subprocess.run(['ddev', a], cwd=d['path'])
            self.log("✅ Completato.", 'success')
            self.root.after(0, self.set_ui_idle)
        threading.Thread(target=run, daemon=True).start()

    def run_ddev_action(self, a, n, d):
        try:
            cmd = ['ddev', a]
            if a == 'start':
                cmd.append('-y')
            p = subprocess.Popen(cmd, cwd=d['path'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                self.log(line.strip())
            p.wait()
            if p.returncode == 0 and a in ['start', 'restart']:
                db_name = d.get('db_name', 'db')
                db_user = d.get('db_user', 'db')
                db_pass = d.get('db_pass', 'db')
                # Provisioning DB:
                # - CREATE USER IF NOT EXISTS non aggiorna la password se l'utente esiste già
                # - ALTER USER garantisce che la password sia sempre aggiornata
                # - GRANT ALL WITH GRANT OPTION assegna privilegi completi per-database
                sql = (
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}`;"
                    f"CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_pass}';"
                    f"ALTER USER '{db_user}'@'%' IDENTIFIED BY '{db_pass}';"
                    f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'%' WITH GRANT OPTION;"
                    f"FLUSH PRIVILEGES;"
                )
                r = subprocess.run(['ddev', 'mysql', '-e', sql], cwd=d['path'],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    self.log(f"✅ DB '{db_name}' | User '{db_user}' configurato.", 'success')
                else:
                    self.log(f"⚠️ SQL provisioning: {r.stderr.strip()}", 'warning')
                self.log_service_urls(n, d)
        except Exception as e:
            self.log(f"Errore: {e}", 'error')
        finally:
            self.root.after(0, self.set_ui_idle)

    def log_service_urls(self, n, d):
        r = subprocess.run(['ddev', 'describe', '-j'], cwd=d['path'], capture_output=True, text=True)
        raw = self.parse_ddev_json(r.stdout)
        urls = self.get_urls(raw, n, project_path=d['path'])
        self.log("-" * 30, 'info')
        self.log(f"🌐 SITO:      {urls['site']}", 'success')
        if urls['adminer']:
            self.log(f"🐘 ADMINER:   {urls['adminer']}", 'info')
        else:
            self.log("⚠️  ADMINER:   non trovato (add-on installato?)", 'warning')
        if urls['phpmyadmin']:
            self.log(f"📂 PMA:       {urls['phpmyadmin']}", 'info')
        self.log("-" * 30, 'info')
        if urls['site']:
            self.projects[n]['url'] = urls['site']; self.save_config()

    # ─── Open URL ────────────────────────────────────────────────────────────

    def _open(self, svc, addon):
        sel = self.get_selected()
        if not sel:
            self.log("⚠️ Seleziona prima un progetto.", 'warning'); return
        n, d = sel

        def run():
            self.root.after(0, lambda: self.set_ui_busy(f"Ricerca URL {svc}..."))
            try:
                r = subprocess.run(['ddev', 'describe', '-j'], cwd=d['path'],
                                   capture_output=True, text=True, timeout=5)
                raw = self.parse_ddev_json(r.stdout)
                urls = self.get_urls(raw, n, project_path=d['path'])
                url = urls.get(svc)
                if url:
                    self.log(f"🔗 Apertura: {url}", 'success')
                    webbrowser.open(url)
                elif addon:
                    if messagebox.askyesno("Add-on mancante", f"Installare {addon}?"):
                        self.log(f"📦 Download {addon} (potrebbero volerci alcuni minuti)...", 'warning')
                        for cmd in [['ddev', 'get', f'ddev/{addon}'], ['ddev', 'restart']]:
                            label = 'Download' if 'get' in cmd else 'Restart'
                            self.log(f"▶ {label}...", 'info')
                            p = subprocess.Popen(cmd, cwd=d['path'],
                                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                            for line in p.stdout:
                                line = line.strip()
                                if line: self.log(line)
                            p.wait()
                        self.log("✅ Add-on installato!", 'success')
                else:
                    self.log(f"⚠️  URL '{svc}' non trovato. Il progetto è avviato?", 'warning')
            except Exception as e:
                self.log(f"Errore apertura {svc}: {e}", 'error')
            finally:
                self.root.after(0, self.set_ui_idle)

        threading.Thread(target=run, daemon=True).start()

    def open_site(self):    self._open('site', '')
    def open_adminer(self):
        """Apre Adminer con il database del progetto pre-selezionato (?db=NOME)."""
        sel = self.get_selected()
        if not sel:
            self.log("⚠️ Seleziona prima un progetto.", 'warning'); return
        n, d = sel
        db_name = d.get('db_name', 'db')

        def run():
            self.root.after(0, lambda: self.set_ui_busy("Apertura Adminer..."))
            try:
                r = subprocess.run(['ddev', 'describe', '-j'], cwd=d['path'],
                                   capture_output=True, text=True, timeout=5)
                raw = self.parse_ddev_json(r.stdout)
                urls = self.get_urls(raw, n, project_path=d['path'])
                base_url = urls.get('adminer')
                if base_url:
                    # Aggiungi il db corretto ai parametri URL di Adminer
                    sep = '&' if '?' in base_url else '?'
                    url = f"{base_url}{sep}db={db_name}"
                    self.log(f"🔗 Apertura Adminer: {url}", 'success')
                    webbrowser.open(url)
                else:
                    if messagebox.askyesno("Add-on mancante", "Installare ddev-adminer?"):
                        self.log("📦 Download ddev-adminer...")
                        for cmd in [['ddev', 'get', 'ddev/ddev-adminer'], ['ddev', 'restart']]:
                            p = subprocess.Popen(cmd, cwd=d['path'],
                                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                            for line in p.stdout:
                                if line.strip(): self.log(line.strip())
                            p.wait()
                        self.log("✅ Adminer installato!", 'success')
            except Exception as e:
                self.log(f"Errore Adminer: {e}", 'error')
            finally:
                self.root.after(0, self.set_ui_idle)
        threading.Thread(target=run, daemon=True).start()
    def open_pma(self):     self._open('phpmyadmin', 'ddev-phpmyadmin')

    def open_folder(self):
        s = self.get_selected()
        if s:
            subprocess.run(['xdg-open', s[1]['path']])


if __name__ == "__main__":
    app = DDEVManager(tk.Tk())
    app.root.mainloop()
