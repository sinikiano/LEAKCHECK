"""
LEAKCHECK Client — Main GUI
Tkinter dark-themed interface.
Developed by BionicSailor  |  Telegram: @BionicSailor
"""

import os
import re
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from config_client import CLIENT_VERSION, get_api_key, set_api_key
from api_client import (ping, get_status, check_combos, list_files,
                        download_file, get_key_info, get_plans,
                        create_order, check_order_status, get_messages,
                        search_email, get_search_quota,
                        get_user_stats, get_referral_code,
                        apply_referral_code, get_referral_stats,
                        APIError)


# ── Theme colours ────────────────────────────
BG       = "#0f0f1a"
BG2      = "#1a1a2e"
FG       = "#e0e0e0"
ACCENT   = "#e94560"
ACCENT2  = "#00d2ff"
GREEN    = "#00e676"
YELLOW   = "#ffab00"
DIM      = "#555566"
ENTRY_BG = "#16213e"


class LeakCheckApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"LEAKCHECK v{CLIENT_VERSION}")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(820, 700)
        self._set_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._checking = False
        self._log_entries: list[dict] = []
        self._last_messages: list[str] = []  # track displayed messages
        self._build_ui()
        self._refresh_connection()
        self._start_message_poll()

    # ── Layout ───────────────────────────────

    def _set_icon(self):
        """Set window icon from logo.ico (works for .exe and .py)."""
        import sys
        ico = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logo.ico")
        if not os.path.isfile(ico):
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
        if os.path.isfile(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def _center(self, w, h):
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 0))
        tk.Label(hdr, text="LEAKCHECK", font=("Consolas", 22, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(hdr, text=f"v{CLIENT_VERSION}", font=("Consolas", 10),
                 fg=DIM, bg=BG).pack(side="left", padx=(8, 0), pady=(8, 0))

        # Connection indicator
        self.conn_dot = tk.Label(hdr, text="●", font=("Consolas", 14), fg=DIM, bg=BG)
        self.conn_dot.pack(side="right")
        self.conn_label = tk.Label(hdr, text="checking...", font=("Consolas", 9),
                                   fg=DIM, bg=BG)
        self.conn_label.pack(side="right", padx=(0, 4))

        # ── API key row ──────────────────────
        key_frame = tk.Frame(self, bg=BG)
        key_frame.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(key_frame, text="API Key:", font=("Consolas", 10),
                 fg=FG, bg=BG).pack(side="left")
        self.key_var = tk.StringVar(value=get_api_key())
        self._key_visible = False
        self.key_entry = tk.Entry(key_frame, textvariable=self.key_var, width=50,
                                  font=("Consolas", 10), bg=ENTRY_BG, fg=FG,
                                  insertbackground=FG, relief="flat", bd=4,
                                  show="*" if get_api_key() else "")
        self.key_entry.pack(side="left", padx=(6, 6))
        self._key_toggle_btn = tk.Button(key_frame, text="👁", font=("Consolas", 9),
                                         bg=ENTRY_BG, fg=DIM, relief="flat", padx=6,
                                         command=self._toggle_key_visibility)
        self._key_toggle_btn.pack(side="left", padx=(0, 6))
        tk.Button(key_frame, text="Save", font=("Consolas", 9, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=10,
                  command=self._save_key).pack(side="left")

        # ── Key status bar ───────────────────
        self.key_status_frame = tk.Frame(self, bg=BG)
        self.key_status_frame.pack(fill="x", padx=16, pady=(4, 0))
        self.key_plan_label = tk.Label(self.key_status_frame, text="",
                                       font=("Consolas", 9, "bold"), fg=DIM, bg=BG)
        self.key_plan_label.pack(side="left")
        self.key_exp_label = tk.Label(self.key_status_frame, text="",
                                      font=("Consolas", 9), fg=DIM, bg=BG)
        self.key_exp_label.pack(side="left", padx=(12, 0))

        # ── Server messages banner ───────────
        self._msg_frame = tk.Frame(self, bg=BG)
        self._msg_frame.pack(fill="x", padx=16, pady=(4, 0))
        # Will be populated by _show_server_messages()

        # ── Tabs ─────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Client.TNotebook", background=BG, borderwidth=0)
        style.configure("Client.TNotebook.Tab", background=BG2, foreground=FG,
                        padding=[14, 6], font=("Consolas", 10, "bold"))
        style.map("Client.TNotebook.Tab",
                  background=[("selected", ENTRY_BG)],
                  foreground=[("selected", ACCENT2)])

        self.nb = ttk.Notebook(self, style="Client.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        # ── Tab 1: Check ─────────────────────
        tab_check = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_check, text="  🔍  Check  ")
        self._build_check_tab(tab_check)

        # ── Tab 2: Search ────────────────────
        tab_search = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_search, text="  🔎  Search  ")
        self._build_search_tab(tab_search)

        # ── Tab 3: Downloads ─────────────────
        tab_dl = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_dl, text="  📥  Downloads  ")
        self._build_downloads_tab(tab_dl)

        # ── Tab 4: Buy Key ───────────────────
        tab_buy = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_buy, text="  💳  Buy Key  ")
        self._build_buy_tab(tab_buy)

        # ── Tab 5: Stats ────────────────────
        tab_stats = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_stats, text="  📊  Stats  ")
        self._build_stats_tab(tab_stats)

        # ── Tab 6: Log ───────────────────────
        tab_log = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_log, text="  📋  Log  ")
        self._build_log_tab(tab_log)

        # ── Tab 6: About ─────────────────────
        tab_about = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_about, text="  ℹ️  About  ")
        self._build_about_tab(tab_about)

        # ── Footer ───────────────────────────
        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=16, pady=(6, 10))
        tk.Label(foot, text="Developed by BionicSailor  •  Telegram: @BionicSailor",
                 font=("Consolas", 9), fg=DIM, bg=BG).pack(side="left")

        self._combo_path = None
        self._results: list[str] = []

    # ── Check tab ────────────────────────────

    def _build_check_tab(self, parent):
        # ── Action row ───────────────────────
        act = tk.Frame(parent, bg=BG)
        act.pack(fill="x", padx=4, pady=(10, 0))

        self.file_label = tk.Label(act, text="No file selected", font=("Consolas", 9),
                                   fg=DIM, bg=BG, anchor="w")
        self.file_label.pack(side="left", expand=True, fill="x")

        tk.Button(act, text="📂  Select Combofile", font=("Consolas", 10, "bold"),
                  bg="#16213e", fg=FG, relief="flat", padx=12, pady=4,
                  command=self._select_file).pack(side="left", padx=(0, 6))

        self.check_btn = tk.Button(act, text="🔍  Check", font=("Consolas", 11, "bold"),
                                   bg=ACCENT, fg="white", relief="flat", padx=16, pady=4,
                                   command=self._start_check)
        self.check_btn.pack(side="left")

        # ── Options row ──────────────────────
        opt_row = tk.Frame(parent, bg=BG)
        opt_row.pack(fill="x", padx=4, pady=(6, 0))

        self.dedup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_row, text="Auto-remove duplicates",
                       variable=self.dedup_var, font=("Consolas", 9),
                       fg=FG, bg=BG, selectcolor=BG2,
                       activebackground=BG, activeforeground=FG).pack(side="left")

        # ── Progress bar ─────────────────────
        prog_frame = tk.Frame(parent, bg=BG)
        prog_frame.pack(fill="x", padx=4, pady=(10, 0))

        self.prog_canvas = tk.Canvas(prog_frame, height=18, bg=BG2,
                                     highlightthickness=0)
        self.prog_canvas.pack(fill="x")
        self.prog_bar = self.prog_canvas.create_rectangle(0, 0, 0, 18, fill=ACCENT2, width=0)
        self.prog_text = self.prog_canvas.create_text(370, 9, text="",
                                                      font=("Consolas", 9), fill=FG)

        # ── Log panel ────────────────────────
        log_frame = tk.Frame(parent, bg=BG2)
        log_frame.pack(fill="both", expand=True, padx=4, pady=(10, 4))

        self.log_text = tk.Text(log_frame, bg=BG2, fg=FG, font=("Consolas", 9),
                                relief="flat", bd=6, state="disabled",
                                insertbackground=FG, selectbackground="#333355",
                                wrap="word")
        scroll = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

        # Tag colours
        self.log_text.tag_configure("info", foreground=ACCENT2)
        self.log_text.tag_configure("ok", foreground=GREEN)
        self.log_text.tag_configure("err", foreground=ACCENT)
        self.log_text.tag_configure("dim", foreground=DIM)

        # Export button row inside check tab
        exp_row = tk.Frame(parent, bg=BG)
        exp_row.pack(fill="x", padx=4, pady=(2, 4))
        self.export_btn = tk.Button(exp_row, text="💾  Export Results",
                                    font=("Consolas", 9, "bold"),
                                    bg="#16213e", fg=FG, relief="flat", padx=10,
                                    state="disabled", command=self._export)
        self.export_btn.pack(side="right")

    # ── Search tab ───────────────────────────

    def _build_search_tab(self, parent):
        """Build the email search tab with input, results treeview, and quota."""
        # ── Header / instruction ─────────────
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=4, pady=(10, 0))
        tk.Label(hdr, text="Search leaked credentials by email address",
                 font=("Consolas", 10), fg=FG, bg=BG).pack(side="left")

        # ── Search row ──────────────────────
        search_row = tk.Frame(parent, bg=BG)
        search_row.pack(fill="x", padx=4, pady=(8, 0))

        tk.Label(search_row, text="Email:", font=("Consolas", 10),
                 fg=FG, bg=BG).pack(side="left")

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(search_row, textvariable=self._search_var,
                                      width=42, font=("Consolas", 10),
                                      bg=ENTRY_BG, fg=FG, insertbackground=FG,
                                      relief="flat", bd=4)
        self._search_entry.pack(side="left", padx=(6, 8))
        self._search_entry.bind("<Return>", lambda e: self._do_search())

        self._search_btn = tk.Button(search_row, text="🔎  Search",
                                     font=("Consolas", 10, "bold"),
                                     bg=ACCENT2, fg="#000", relief="flat",
                                     padx=14, pady=3, command=self._do_search)
        self._search_btn.pack(side="left")

        # ── Quota label ──────────────────────
        self._search_quota_label = tk.Label(search_row, text="",
                                            font=("Consolas", 9), fg=DIM, bg=BG)
        self._search_quota_label.pack(side="right", padx=(8, 0))

        # ── Status bar ──────────────────────
        self._search_status = tk.Label(parent, text="Enter an email and press Search (30 searches/day)",
                                       font=("Consolas", 9), fg=DIM, bg=BG, anchor="w")
        self._search_status.pack(fill="x", padx=4, pady=(6, 0))

        # ── Results treeview ─────────────────
        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=(8, 0))

        style = ttk.Style()
        style.configure("Search.Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, font=("Consolas", 10),
                        rowheight=24)
        style.configure("Search.Treeview.Heading", background=ENTRY_BG,
                        foreground=ACCENT2, font=("Consolas", 10, "bold"))

        cols = ("email", "password")
        self._search_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                         height=14, style="Search.Treeview")
        self._search_tree.heading("email", text="Email")
        self._search_tree.heading("password", text="Password")
        self._search_tree.column("email", width=340)
        self._search_tree.column("password", width=340)

        search_scroll = tk.Scrollbar(tree_frame, command=self._search_tree.yview)
        self._search_tree.configure(yscrollcommand=search_scroll.set)
        self._search_tree.pack(fill="both", expand=True, side="left")
        search_scroll.pack(fill="y", side="right")

        # ── Bottom buttons ───────────────────
        bot_row = tk.Frame(parent, bg=BG)
        bot_row.pack(fill="x", padx=4, pady=(6, 4))

        self._search_export_btn = tk.Button(bot_row, text="💾  Export Results",
                                            font=("Consolas", 9, "bold"),
                                            bg=ENTRY_BG, fg=FG, relief="flat",
                                            padx=10, state="disabled",
                                            command=self._export_search)
        self._search_export_btn.pack(side="right")

        self._search_copy_btn = tk.Button(bot_row, text="📋  Copy All",
                                          font=("Consolas", 9, "bold"),
                                          bg=ENTRY_BG, fg=FG, relief="flat",
                                          padx=10, state="disabled",
                                          command=self._copy_search_results)
        self._search_copy_btn.pack(side="right", padx=(0, 6))

        self._search_results_data: list[dict] = []
        self._searching = False

    def _do_search(self):
        """Execute an email search."""
        if self._searching:
            return
        email = self._search_var.get().strip()
        if not email:
            messagebox.showwarning("No Email", "Enter an email address to search.")
            return
        if not get_api_key():
            messagebox.showwarning("No Key", "Enter and save your API key first.")
            return
        # Basic client-side email validation
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            messagebox.showwarning("Invalid Email", "Please enter a valid email address.")
            return

        self._searching = True
        self._search_btn.configure(state="disabled", text="⏳  Searching...")
        self._search_status.configure(text=f"Searching for {email}...", fg=ACCENT2)

        def _do():
            try:
                data = search_email(email)
                results = data.get("results", [])
                count = data.get("count", 0)
                used = data.get("searches_used", 0)
                remaining = data.get("searches_remaining", 0)
                limit = data.get("daily_limit", 30)
                elapsed = data.get("elapsed_ms", 0)

                def _update():
                    # Clear tree
                    for item in self._search_tree.get_children():
                        self._search_tree.delete(item)

                    self._search_results_data = results

                    if count > 0:
                        for r in results:
                            self._search_tree.insert("", "end",
                                                     values=(r.get("email", ""), r.get("password", "")))
                        self._search_status.configure(
                            text=f"Found {count} result(s) for {email}  ({elapsed:.0f} ms)",
                            fg=GREEN)
                        self._search_export_btn.configure(state="normal")
                        self._search_copy_btn.configure(state="normal")
                        self._log(f"Search: {email} → {count} result(s)", "ok")
                    else:
                        self._search_status.configure(
                            text=f"No results found for {email}  ({elapsed:.0f} ms)",
                            fg=ACCENT)
                        self._search_export_btn.configure(state="disabled")
                        self._search_copy_btn.configure(state="disabled")
                        self._log(f"Search: {email} → no results", "info")

                    self._search_quota_label.configure(
                        text=f"Searches: {used}/{limit}  ({remaining} left)",
                        fg=GREEN if remaining > 5 else ("#ffab00" if remaining > 0 else ACCENT))

                    self._searching = False
                    self._search_btn.configure(state="normal", text="🔎  Search")

                self.after(0, _update)

            except APIError as e:
                def _err():
                    self._search_status.configure(text=str(e), fg=ACCENT)
                    self._searching = False
                    self._search_btn.configure(state="normal", text="🔎  Search")
                    self._log(f"Search error: {e}", "err")
                self.after(0, _err)
            except Exception as e:
                def _err2():
                    self._search_status.configure(text=f"Error: {e}", fg=ACCENT)
                    self._searching = False
                    self._search_btn.configure(state="normal", text="🔎  Search")
                    self._log(f"Search error: {e}", "err")
                self.after(0, _err2)

        threading.Thread(target=_do, daemon=True).start()

    def _export_search(self):
        """Export search results to a text file."""
        if not self._search_results_data:
            return
        path = filedialog.asksaveasfilename(
            title="Save Search Results",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="search_results.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                for r in self._search_results_data:
                    f.write(f"{r.get('email', '')}:{r.get('password', '')}\n")
            self._log(f"Exported {len(self._search_results_data)} search results", "ok")

    def _copy_search_results(self):
        """Copy all search results to clipboard."""
        if not self._search_results_data:
            return
        lines = [f"{r.get('email', '')}:{r.get('password', '')}" for r in self._search_results_data]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self._search_status.configure(text=f"Copied {len(lines)} result(s) to clipboard", fg=GREEN)

    # ── Downloads tab ────────────────────────

    def _build_downloads_tab(self, parent):
        # ── Button row ───────────────────────
        btn_row = tk.Frame(parent, bg=BG)
        btn_row.pack(fill="x", padx=4, pady=(10, 0))

        tk.Button(btn_row, text="🔄  Refresh", font=("Consolas", 10, "bold"),
                  bg=ENTRY_BG, fg=FG, relief="flat", padx=12, pady=4,
                  command=self._refresh_files).pack(side="left")

        self.dl_btn = tk.Button(btn_row, text="📥  Download Selected",
                                font=("Consolas", 10, "bold"),
                                bg=ACCENT, fg="white", relief="flat", padx=14, pady=4,
                                command=self._download_selected)
        self.dl_btn.pack(side="left", padx=(8, 0))

        self.dl_status_label = tk.Label(btn_row, text="", font=("Consolas", 9),
                                        fg=ACCENT2, bg=BG)
        self.dl_status_label.pack(side="right")

        # ── File list treeview ───────────────
        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=(10, 0))

        style = ttk.Style()
        style.configure("DL.Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, font=("Consolas", 9),
                        rowheight=24)
        style.configure("DL.Treeview.Heading", background=ENTRY_BG,
                        foreground=ACCENT2, font=("Consolas", 9, "bold"))

        cols = ("name", "size", "modified")
        self.dl_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                    height=14, style="DL.Treeview")
        self.dl_tree.heading("name", text="Filename")
        self.dl_tree.heading("size", text="Size")
        self.dl_tree.heading("modified", text="Modified")
        self.dl_tree.column("name", width=360)
        self.dl_tree.column("size", width=100, anchor="center")
        self.dl_tree.column("modified", width=160, anchor="center")

        dl_scroll = tk.Scrollbar(tree_frame, command=self.dl_tree.yview)
        self.dl_tree.configure(yscrollcommand=dl_scroll.set)
        self.dl_tree.pack(fill="both", expand=True, side="left")
        dl_scroll.pack(fill="y", side="right")

        # ── Download progress ────────────────
        dl_prog_frame = tk.Frame(parent, bg=BG)
        dl_prog_frame.pack(fill="x", padx=4, pady=(6, 4))

        self.dl_prog_canvas = tk.Canvas(dl_prog_frame, height=18, bg=BG2,
                                        highlightthickness=0)
        self.dl_prog_canvas.pack(fill="x")
        self.dl_prog_bar = self.dl_prog_canvas.create_rectangle(
            0, 0, 0, 18, fill=GREEN, width=0)
        self.dl_prog_text = self.dl_prog_canvas.create_text(
            370, 9, text="", font=("Consolas", 9), fill=FG)

        self._downloading = False

    # ── Helpers ──────────────────────────────

    def _log(self, msg: str, tag: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        level = tag.upper() if tag else "INFO"
        entry = {"ts": ts, "msg": msg, "tag": tag, "level": level}
        self._log_entries.append(entry)

        # Cap log entries to prevent unbounded memory growth
        if len(self._log_entries) > 5000:
            self._log_entries = self._log_entries[-4000:]

        # Write to Check-tab mini log
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] ", "dim")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

        # Write to Log-tab advanced viewer
        if hasattr(self, "adv_log_text"):
            cur_filter = self._log_filter_var.get() if hasattr(self, "_log_filter_var") else "ALL"
            self._append_adv_log(entry, cur_filter)

    def _set_progress(self, done: int, total: int):
        if total == 0:
            return
        frac = done / total
        width = self.prog_canvas.winfo_width()
        self.prog_canvas.coords(self.prog_bar, 0, 0, width * frac, 18)
        pct = int(frac * 100)
        self.prog_canvas.itemconfigure(self.prog_text,
                                       text=f"{done:,} / {total:,}  ({pct}%)")

    def _reset_progress(self):
        self.prog_canvas.coords(self.prog_bar, 0, 0, 0, 18)
        self.prog_canvas.itemconfigure(self.prog_text, text="")

    # ── Connection ───────────────────────────

    def _refresh_connection(self):
        def _do():
            self._log("Connecting to server...", "dim")
            t0 = time.time()
            resp = ping()
            ms = (time.time() - t0) * 1000
            if resp:
                self.conn_dot.configure(fg=GREEN)
                self.conn_label.configure(text="connected", fg=GREEN)
                self._log(f"Connected to server ({ms:.0f} ms)", "ok")
                self._log(f"Server version: {resp.get('version', 'unknown')}", "dim")
                self._log(f"Client version: {CLIENT_VERSION}", "dim")
                # Fetch key info
                self._fetch_key_info()
                # Fetch server messages
                msgs = get_messages()
                if msgs:
                    self.after(0, self._show_server_messages, msgs)
            else:
                self.conn_dot.configure(fg=ACCENT)
                self.conn_label.configure(text="offline", fg=ACCENT)
                self._log(f"Server unreachable (timeout {ms:.0f} ms)", "err")
                self.key_plan_label.configure(text="", fg=DIM)
                self.key_exp_label.configure(text="", fg=DIM)
        threading.Thread(target=_do, daemon=True).start()

    def _fetch_key_info(self):
        """Fetch and display key subscription status."""
        if not get_api_key():
            self.key_plan_label.configure(text="No API key set", fg=DIM)
            self.key_exp_label.configure(text="")
            return
        try:
            info = get_key_info()
        except APIError as e:
            self.key_plan_label.configure(text=str(e), fg=ACCENT)
            self.key_exp_label.configure(text="")
            self._log(f"Key error: {e}", "err")
            return
        if not info:
            self.key_plan_label.configure(text="Key info unavailable", fg=DIM)
            self.key_exp_label.configure(text="")
            return
        if info.get("error"):
            self.key_plan_label.configure(text=info.get("message", "Invalid key"), fg=ACCENT)
            self.key_exp_label.configure(text="")
            return

        plan_label = info.get("plan_label", "Unknown")
        days = info.get("days_remaining")
        expired = info.get("expired", False)

        self.key_plan_label.configure(text=f"Plan: {plan_label}", fg=ACCENT2)

        if expired:
            self.key_exp_label.configure(text="EXPIRED — Contact @BionicSailor to renew", fg=ACCENT)
            self._log("Your API key has expired!", "err")
        elif days is None:
            self.key_exp_label.configure(text="Lifetime — Never expires", fg=GREEN)
        elif days <= 7:
            self.key_exp_label.configure(text=f"{days} days remaining", fg="#ffab00")
            self._log(f"Key expires in {days} days!", "err")
        else:
            self.key_exp_label.configure(text=f"{days} days remaining", fg=GREEN)

    def _show_server_messages(self, messages: list[dict]):
        """Display server news/messages in the banner area."""
        # Check if messages changed
        new_texts = [m.get("text", "") for m in messages]
        if new_texts == self._last_messages:
            return  # no change, skip redraw
        self._last_messages = new_texts

        # Clear old messages
        for w in self._msg_frame.winfo_children():
            w.destroy()

        if not messages:
            return

        for msg in messages:
            text = msg.get("text", "")
            level = msg.get("level", "info")
            if not text:
                continue

            colors = {
                "info": ("#1a2a4a", ACCENT2),
                "warning": ("#3a2a00", YELLOW),
                "urgent": ("#3a0a0a", ACCENT),
                "success": ("#0a2a0a", GREEN),
            }
            bg_c, fg_c = colors.get(level, colors["info"])

            row = tk.Frame(self._msg_frame, bg=bg_c, padx=8, pady=3)
            row.pack(fill="x", pady=(2, 0))

            icon = {"info": "ℹ️", "warning": "⚠️", "urgent": "🚨", "success": "✅"}.get(level, "ℹ️")
            tk.Label(row, text=f"{icon}  {text}", font=("Consolas", 9, "bold"),
                     fg=fg_c, bg=bg_c, anchor="w").pack(side="left", fill="x")

            self._log(f"Server message: {text}", "info")

    def _start_message_poll(self):
        """Poll server messages every 60 seconds."""
        def _poll():
            def _fetch():
                try:
                    msgs = get_messages()
                    self.after(0, self._show_server_messages, msgs)
                except Exception:
                    pass
            threading.Thread(target=_fetch, daemon=True).start()
            self.after(60_000, _poll)
        # First poll after 30 seconds (initial fetch is in _refresh_connection)
        self.after(30_000, _poll)

    # ── Key ──────────────────────────────────

    def _save_key(self):
        key = self.key_var.get().strip()
        set_api_key(key)
        self._log("API key saved.", "info")
        # Mask the key after saving
        if key:
            self.key_entry.configure(show="*")
            self._key_visible = False
            self._key_toggle_btn.configure(text="👁")
        self._refresh_connection()

    def _toggle_key_visibility(self):
        """Toggle showing/hiding the API key."""
        if self._key_visible:
            self.key_entry.configure(show="*")
            self._key_toggle_btn.configure(text="👁")
            self._key_visible = False
        else:
            self.key_entry.configure(show="")
            self._key_toggle_btn.configure(text="🔒")
            self._key_visible = True

    # ── File selection ───────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Select Combofile",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self._combo_path = path
            name = os.path.basename(path)
            # count lines
            try:
                with open(path, "r", errors="ignore") as f:
                    count = sum(1 for _ in f)
            except Exception:
                count = 0
            self.file_label.configure(text=f"{name}  ({count:,} lines)", fg=FG)
            self._log(f"Selected: {name} ({count:,} lines)", "info")

    # ── Check ────────────────────────────────

    def _start_check(self):
        if self._checking:
            return
        if not self._combo_path:
            messagebox.showwarning("No File", "Select a combofile first.")
            return
        if not get_api_key():
            messagebox.showwarning("No Key", "Enter and save your API key first.")
            return

        self._checking = True
        self.check_btn.configure(state="disabled", text="⏳  Checking...")
        self.export_btn.configure(state="disabled")
        self._reset_progress()
        self._results = []
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        try:
            with open(self._combo_path, "r", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip()]
        except Exception as exc:
            self._log(f"Error reading file: {exc}", "err")
            self._finish_check()
            return

        total = len(lines)
        self._log(f"File loaded: {total:,} lines from {os.path.basename(self._combo_path)}", "dim")
        self._log(f"Starting check: {total:,} combos...", "info")

        # Auto-remove duplicates
        if self.dedup_var.get():
            lines = list(dict.fromkeys(lines))
            dupes = total - len(lines)
            if dupes:
                self._log(f"Removed {dupes:,} duplicate lines ({len(lines):,} unique)", "info")
                total = len(lines)

        # Validate email:password format
        _email_re = re.compile(
            r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}:.+$')
        valid = [l for l in lines if _email_re.match(l)]
        rejected = total - len(valid)
        if rejected:
            self._log(f"Rejected {rejected:,} invalid format lines "
                      f"({len(valid):,} valid email:pass)", "info")
        lines = valid
        total = len(lines)

        if total == 0:
            self._log("No valid email:password combos found.", "err")
            self._finish_check()
            return

        self._log(f"Checking {total:,} combos against database...", "dim")
        t_hash = time.time()

        def on_progress(done, total):
            self.after(0, self._set_progress, done, total)

        try:
            not_found, checked, elapsed = check_combos(lines, batch_size=25000,
                                                        progress_cb=on_progress)
        except APIError as e:
            self.after(0, lambda: self._log(f"Server error: {e}", "err"))
            self.after(0, lambda: messagebox.showerror("Access Denied", str(e)))
            self._finish_check()
            return

        hash_ms = (time.time() - t_hash) * 1000
        self._results = not_found
        found = checked - len(not_found)
        hit_pct = (found / checked * 100) if checked else 0

        self._log(f"─── Results ───", "dim")
        self._log(f"Total checked : {checked:,}", "info")
        self._log(f"Found in DB   : {found:,}", "ok")
        self._log(f"Private combo : {len(not_found):,}", "err")
        self._log(f"Hit rate      : {hit_pct:.1f}%", "dim")
        self._log(f"Server time   : {elapsed:,.0f} ms", "dim")
        self._log(f"Total time    : {hash_ms:,.0f} ms (network)", "dim")
        self._log(f"───────────────", "dim")

        self._finish_check()

    def _finish_check(self):
        def _ui():
            self._checking = False
            self.check_btn.configure(state="normal", text="🔍  Check")
            if self._results:
                self.export_btn.configure(state="normal")
        self.after(0, _ui)

    # ── Export ───────────────────────────────

    def _export(self):
        if not self._results:
            return
        path = filedialog.asksaveasfilename(
            title="Save Not-Found Combos",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="not_found.txt",
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write("\n".join(self._results))
                self._log(f"Exported {len(self._results):,} combos to {os.path.basename(path)}", "ok")
            except Exception as e:
                self._log(f"Export failed: {e}", "err")
                messagebox.showerror("Export Error", str(e))

    # ── Downloads helpers ────────────────────

    def _refresh_files(self):
        """Fetch file list from server and populate treeview."""
        if not get_api_key():
            messagebox.showwarning("No Key", "Enter and save your API key first.")
            return

        self.dl_status_label.configure(text="Loading...", fg=ACCENT2)
        for item in self.dl_tree.get_children():
            self.dl_tree.delete(item)

        def _do():
            files = list_files()
            if files is None:
                self.after(0, lambda: self.dl_status_label.configure(
                    text="Failed to load files", fg=ACCENT))
                return

            def _update():
                for item in self.dl_tree.get_children():
                    self.dl_tree.delete(item)
                for finfo in files:
                    size_mb = finfo.get("size_mb", 0)
                    if size_mb >= 1:
                        size_str = f"{size_mb:.1f} MB"
                    else:
                        size_kb = finfo.get("size_bytes", 0) / 1024
                        size_str = f"{size_kb:.1f} KB"
                    self.dl_tree.insert("", "end", values=(
                        finfo["name"], size_str, finfo.get("modified", "")))
                self.dl_status_label.configure(
                    text=f"{len(files)} file(s) available", fg=GREEN)

            self.after(0, _update)

        threading.Thread(target=_do, daemon=True).start()

    def _download_selected(self):
        """Download the selected file from server."""
        if self._downloading:
            return

        sel = self.dl_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a file to download.")
            return
        if not get_api_key():
            messagebox.showwarning("No Key", "Enter and save your API key first.")
            return

        item = self.dl_tree.item(sel[0])
        filename = item["values"][0]

        save_path = filedialog.asksaveasfilename(
            title="Save Downloaded File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=filename,
        )
        if not save_path:
            return

        self._downloading = True
        self.dl_btn.configure(state="disabled", text="⏳  Downloading...")
        self.dl_status_label.configure(text=f"Downloading {filename}...", fg=ACCENT2)

        def _do():
            def on_progress(downloaded, total):
                self.after(0, self._set_dl_progress, downloaded, total)

            ok = download_file(filename, save_path, progress_cb=on_progress)

            def _done():
                self._downloading = False
                self.dl_btn.configure(state="normal", text="📥  Download Selected")
                if ok:
                    size_mb = os.path.getsize(save_path) / (1024 * 1024)
                    self.dl_status_label.configure(
                        text=f"Downloaded {filename} ({size_mb:.1f} MB)", fg=GREEN)
                    self._log(f"Downloaded: {filename} -> {os.path.basename(save_path)}", "ok")
                else:
                    self.dl_status_label.configure(
                        text=f"Download failed: {filename}", fg=ACCENT)
                    self._log(f"Download failed: {filename}", "err")
                self._reset_dl_progress()

            self.after(0, _done)

        threading.Thread(target=_do, daemon=True).start()

    def _set_dl_progress(self, done: int, total: int):
        if total == 0:
            return
        frac = done / total
        width = self.dl_prog_canvas.winfo_width()
        self.dl_prog_canvas.coords(self.dl_prog_bar, 0, 0, width * frac, 18)
        pct = int(frac * 100)
        done_mb = done / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.dl_prog_canvas.itemconfigure(
            self.dl_prog_text,
            text=f"{done_mb:.1f} / {total_mb:.1f} MB  ({pct}%)")

    def _reset_dl_progress(self):
        self.dl_prog_canvas.coords(self.dl_prog_bar, 0, 0, 0, 18)
        self.dl_prog_canvas.itemconfigure(self.dl_prog_text, text="")

    # ── Buy Key tab ──────────────────────────

    def _build_buy_tab(self, parent):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        tk.Label(wrap, text="Purchase Subscription Key",
                 font=("Consolas", 13, "bold"), fg=ACCENT2, bg=BG).pack(anchor="w")
        tk.Label(wrap, text="Pay with USDT — your key is generated automatically.",
                 font=("Consolas", 9), fg=DIM, bg=BG).pack(anchor="w", pady=(2, 10))

        # ── Username + Plan row ──────────────
        form = tk.Frame(wrap, bg=BG)
        form.pack(fill="x")

        tk.Label(form, text="Username:", font=("Consolas", 10),
                 fg=FG, bg=BG).grid(row=0, column=0, sticky="w")
        self._buy_name_var = tk.StringVar()
        tk.Entry(form, textvariable=self._buy_name_var, width=20,
                 font=("Consolas", 10), bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).grid(
                     row=0, column=1, padx=(6, 16), sticky="w")

        tk.Label(form, text="Plan:", font=("Consolas", 10),
                 fg=FG, bg=BG).grid(row=0, column=2, sticky="w")
        self._buy_plan_var = tk.StringVar(value="Loading plans...")
        self._buy_plan_combo = ttk.Combobox(form, textvariable=self._buy_plan_var,
                                             state="readonly", width=24,
                                             font=("Consolas", 10))
        self._buy_plan_combo.grid(row=0, column=3, padx=(6, 0), sticky="w")

        self._refresh_plans_btn = tk.Button(
            form, text="🔄", font=("Consolas", 10),
            bg=ENTRY_BG, fg=FG, relief="flat", padx=6,
            command=lambda: threading.Thread(target=self._load_plans, daemon=True).start())
        self._refresh_plans_btn.grid(row=0, column=4, padx=(4, 0))

        # ── Create Order button ──────────────
        btn_row = tk.Frame(wrap, bg=BG)
        btn_row.pack(fill="x", pady=(12, 0))

        self._buy_btn = tk.Button(btn_row, text="💳  Create Order",
                                  font=("Consolas", 11, "bold"),
                                  bg=ACCENT, fg="white", relief="flat",
                                  padx=16, pady=4, command=self._create_order)
        self._buy_btn.pack(side="left")

        self._buy_status = tk.Label(btn_row, text="", font=("Consolas", 9),
                                    fg=DIM, bg=BG)
        self._buy_status.pack(side="left", padx=(12, 0))

        # ── Payment info card ────────────────
        self._pay_card = tk.Frame(wrap, bg=ENTRY_BG, padx=14, pady=12)
        self._pay_card.pack(fill="x", pady=(12, 0))

        self._pay_info_text = tk.Text(self._pay_card, bg=ENTRY_BG, fg=FG,
                                       font=("Consolas", 10), relief="flat",
                                       height=9, state="disabled", wrap="word",
                                       insertbackground=FG, selectbackground="#333355")
        self._pay_info_text.pack(fill="x")
        self._pay_info_text.tag_configure("label", foreground=DIM)
        self._pay_info_text.tag_configure("value", foreground=ACCENT2,
                                          font=("Consolas", 10, "bold"))
        self._pay_info_text.tag_configure("ok", foreground=GREEN,
                                          font=("Consolas", 11, "bold"))
        self._pay_info_text.tag_configure("err", foreground=ACCENT)
        self._pay_info_text.tag_configure("key", foreground=GREEN,
                                          font=("Consolas", 9))

        # ── Action buttons row ───────────────
        act_row = tk.Frame(wrap, bg=BG)
        act_row.pack(fill="x", pady=(8, 0))

        self._copy_addr_btn = tk.Button(act_row, text="📋 Copy Address",
                                        font=("Consolas", 9, "bold"),
                                        bg=ENTRY_BG, fg=FG, relief="flat",
                                        padx=8, state="disabled",
                                        command=self._copy_pay_address)
        self._copy_addr_btn.pack(side="left")

        self._copy_amt_btn = tk.Button(act_row, text="📋 Copy Amount",
                                       font=("Consolas", 9, "bold"),
                                       bg=ENTRY_BG, fg=FG, relief="flat",
                                       padx=8, state="disabled",
                                       command=self._copy_pay_amount)
        self._copy_amt_btn.pack(side="left", padx=(6, 0))

        self._check_pay_btn = tk.Button(act_row, text="🔄 Check Payment",
                                        font=("Consolas", 9, "bold"),
                                        bg=ENTRY_BG, fg=FG, relief="flat",
                                        padx=8, state="disabled",
                                        command=self._poll_order_once)
        self._check_pay_btn.pack(side="left", padx=(6, 0))

        self._copy_key_btn = tk.Button(act_row, text="📋 Copy Key & Save",
                                       font=("Consolas", 9, "bold"),
                                       bg=GREEN, fg="#000", relief="flat",
                                       padx=8, state="disabled",
                                       command=self._save_purchased_key)
        self._copy_key_btn.pack(side="right")

        # internal state
        self._current_order: dict | None = None
        self._plans_data: list[dict] = []
        self._poll_timer: str | None = None

        # Fetch plans on startup
        threading.Thread(target=self._load_plans, daemon=True).start()

    def _load_plans(self):
        self.after(0, lambda: self._buy_plan_var.set("Loading plans..."))
        plans = None
        for attempt in range(3):
            plans = get_plans()
            if plans:
                break
            time.sleep(2)
        if not plans:
            self.after(0, lambda: self._buy_plan_var.set("Server unreachable"))
            return
        self._plans_data = plans
        labels = [f"{p['label']}  —  ${p['price']:.2f}" for p in plans]

        def _set():
            self._buy_plan_combo["values"] = labels
            if labels:
                self._buy_plan_combo.current(0)

        self.after(0, _set)

    def _create_order(self):
        if not self._plans_data:
            # Try loading plans one more time before giving up
            plans = get_plans()
            if plans:
                self._plans_data = plans
                labels = [f"{p['label']}  —  ${p['price']:.2f}" for p in plans]
                self._buy_plan_combo["values"] = labels
                self._buy_plan_combo.current(0)
            else:
                messagebox.showwarning("No Plans",
                    "Plans not loaded. Check server connection and click 🔄 to retry.")
                return

        idx = self._buy_plan_combo.current()
        if idx < 0:
            return
        plan_key = self._plans_data[idx]["plan"]
        username = self._buy_name_var.get().strip() or "user"

        self._buy_btn.configure(state="disabled", text="⏳  Creating...")
        self._buy_status.configure(text="", fg=DIM)

        def _do():
            result = create_order(plan_key, username)

            def _done():
                self._buy_btn.configure(state="normal", text="💳  Create Order")
                if not result:
                    self._buy_status.configure(text="Failed to create order.", fg=ACCENT)
                    return

                self._current_order = result
                self._show_payment_info(result)
                self._buy_status.configure(
                    text=f"Order {result['order_id']} created!", fg=GREEN)

                # Enable action buttons
                self._copy_addr_btn.configure(state="normal")
                self._copy_amt_btn.configure(state="normal")
                self._check_pay_btn.configure(state="normal")
                self._copy_key_btn.configure(state="disabled")

                # Start auto-polling every 15 seconds
                self._start_order_polling(result["order_id"])

            self.after(0, _done)

        threading.Thread(target=_do, daemon=True).start()

    def _show_payment_info(self, order: dict):
        t = self._pay_info_text
        t.configure(state="normal")
        t.delete("1.0", "end")

        t.insert("end", "Send exactly ", "label")
        t.insert("end", f"${order['amount']:.4f} USDT", "value")
        t.insert("end", " to:\n\n", "label")

        t.insert("end", "Network:  ", "label")
        t.insert("end", f"{order['network']}\n", "value")

        t.insert("end", "Address:  ", "label")
        t.insert("end", f"{order['address']}\n\n", "value")

        t.insert("end", "Order ID: ", "label")
        t.insert("end", f"{order['order_id']}\n", "value")

        exp = order.get("expires_at", "")[:19].replace("T", " ")
        t.insert("end", "Expires:  ", "label")
        t.insert("end", f"{exp} UTC\n\n", "value")

        t.insert("end", "Status:   ", "label")
        t.insert("end", "Waiting for payment...", "err")

        t.configure(state="disabled")

    def _start_order_polling(self, order_id: str):
        """Poll order status every 15 seconds until paid/expired."""
        if self._poll_timer:
            self.after_cancel(self._poll_timer)

        def _tick():
            threading.Thread(target=self._poll_order, args=(order_id,),
                             daemon=True).start()
            self._poll_timer = self.after(15000, _tick)

        self._poll_timer = self.after(15000, _tick)

    def _poll_order(self, order_id: str):
        info = check_order_status(order_id)
        if not info:
            return
        if info.get("status") == "paid":
            self.after(0, lambda: self._on_order_paid(info))
        elif info.get("status") in ("expired", "cancelled"):
            self.after(0, lambda: self._on_order_failed(info))

    def _poll_order_once(self):
        """Manual check button."""
        if not self._current_order:
            return
        oid = self._current_order["order_id"]
        self._check_pay_btn.configure(state="disabled", text="⏳ Checking...")

        def _do():
            info = check_order_status(oid)

            def _done():
                self._check_pay_btn.configure(state="normal",
                                              text="🔄 Check Payment")
                if not info:
                    self._buy_status.configure(text="Failed to check.", fg=ACCENT)
                    return
                st = info.get("status", "unknown")
                if st == "paid":
                    self._on_order_paid(info)
                elif st == "pending":
                    self._buy_status.configure(
                        text="Still waiting for payment...", fg=DIM)
                else:
                    self._on_order_failed(info)

            self.after(0, _done)

        threading.Thread(target=_do, daemon=True).start()

    def _on_order_paid(self, info: dict):
        """Called when the order is confirmed paid."""
        # Stop polling
        if self._poll_timer:
            self.after_cancel(self._poll_timer)
            self._poll_timer = None

        api_key = info.get("api_key", "")
        self._current_order["api_key"] = api_key

        # Update payment card
        t = self._pay_info_text
        t.configure(state="normal")
        t.delete("1.0", "end")

        t.insert("end", "PAYMENT CONFIRMED!\n\n", "ok")
        t.insert("end", "Plan:     ", "label")
        t.insert("end", f"{info.get('plan_label', info.get('plan', ''))}\n", "value")
        t.insert("end", "Order:    ", "label")
        t.insert("end", f"{info.get('order_id', '')}\n\n", "value")
        t.insert("end", "Your API Key:\n", "label")
        t.insert("end", f"{api_key}\n\n", "key")
        t.insert("end", "Click 'Copy Key & Save' to activate →", "label")

        t.configure(state="disabled")

        self._buy_status.configure(text="Payment confirmed!", fg=GREEN)
        self._copy_key_btn.configure(state="normal")
        self._check_pay_btn.configure(state="disabled")
        self._copy_addr_btn.configure(state="disabled")
        self._copy_amt_btn.configure(state="disabled")

    def _on_order_failed(self, info: dict):
        """Called when the order expires or is cancelled."""
        if self._poll_timer:
            self.after_cancel(self._poll_timer)
            self._poll_timer = None

        st = info.get("status", "unknown")
        t = self._pay_info_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", f"Order {st.upper()}.\n\n", "err")
        t.insert("end", "Create a new order to try again.", "label")
        t.configure(state="disabled")

        self._buy_status.configure(text=f"Order {st}.", fg=ACCENT)
        self._check_pay_btn.configure(state="disabled")
        self._copy_addr_btn.configure(state="disabled")
        self._copy_amt_btn.configure(state="disabled")

    def _copy_pay_address(self):
        if self._current_order and self._current_order.get("address"):
            self.clipboard_clear()
            self.clipboard_append(self._current_order["address"])
            self._buy_status.configure(text="Address copied!", fg=GREEN)

    def _copy_pay_amount(self):
        if self._current_order:
            self.clipboard_clear()
            self.clipboard_append(f"{self._current_order['amount']:.4f}")
            self._buy_status.configure(text="Amount copied!", fg=GREEN)

    def _save_purchased_key(self):
        """Copy the received key to clipboard and auto-save to config."""
        if not self._current_order or not self._current_order.get("api_key"):
            return
        key = self._current_order["api_key"]
        set_api_key(key)
        self.key_var.set(key)
        self.clipboard_clear()
        self.clipboard_append(key)
        self._buy_status.configure(text="Key saved & copied!", fg=GREEN)
        self._log("Purchased key saved to config.", "ok")
        self._refresh_connection()
        messagebox.showinfo("Key Activated",
                            "Your new API key has been saved and activated.\n"
                            "You can now use the Check and Downloads tabs.")

    # ── Stats tab ────────────────────────────

    def _build_stats_tab(self, parent):
        # Header
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(hdr, text="📊 Personal Statistics", font=("Consolas", 13, "bold"),
                 fg=ACCENT2, bg=BG).pack(side="left")

        refresh_btn = tk.Button(hdr, text="🔄 Refresh", font=("Consolas", 9),
                                bg=ENTRY_BG, fg=FG, relief="flat", padx=8,
                                command=self._refresh_stats)
        refresh_btn.pack(side="right")

        # Stats frame
        self._stats_frame = tk.Frame(parent, bg=BG)
        self._stats_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Referral section
        ref_frame = tk.LabelFrame(parent, text="  Referral Program  ",
                                  font=("Consolas", 10, "bold"),
                                  fg=ACCENT2, bg=BG2, bd=1, relief="groove",
                                  labelanchor="nw")
        ref_frame.pack(fill="x", padx=10, pady=(0, 10))

        self._referral_label = tk.Label(ref_frame, text="Loading referral code...",
                                        font=("Consolas", 10), fg=FG, bg=BG2,
                                        anchor="w", justify="left")
        self._referral_label.pack(fill="x", padx=10, pady=(6, 2))

        ref_btn_frame = tk.Frame(ref_frame, bg=BG2)
        ref_btn_frame.pack(fill="x", padx=10, pady=(2, 6))

        tk.Button(ref_btn_frame, text="📋 Copy Code", font=("Consolas", 9),
                  bg=ENTRY_BG, fg=ACCENT2, relief="flat", padx=8,
                  command=self._copy_referral_code).pack(side="left", padx=(0, 8))

        tk.Label(ref_btn_frame, text="Apply code:", font=("Consolas", 9),
                 fg=DIM, bg=BG2).pack(side="left")
        self._apply_ref_var = tk.StringVar()
        tk.Entry(ref_btn_frame, textvariable=self._apply_ref_var, width=16,
                 font=("Consolas", 10), bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).pack(side="left", padx=4)
        tk.Button(ref_btn_frame, text="Apply", font=("Consolas", 9),
                  bg=ACCENT, fg="white", relief="flat", padx=8,
                  command=self._apply_referral).pack(side="left")

        self._referral_status_label = tk.Label(ref_frame, text="",
                                               font=("Consolas", 9), fg=DIM, bg=BG2)
        self._referral_status_label.pack(fill="x", padx=10, pady=(0, 6))

        self._referral_code_value = ""

        # Auto-load stats on tab shown
        self.after(500, self._refresh_stats)

    def _refresh_stats(self):
        def _fetch():
            try:
                data = get_user_stats()
                ref_data = get_referral_code()
            except Exception as e:
                self.after(0, lambda: self._show_stats_error(str(e)))
                return
            self.after(0, lambda: self._display_stats(data, ref_data))
        threading.Thread(target=_fetch, daemon=True).start()

    def _show_stats_error(self, msg):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        tk.Label(self._stats_frame, text=f"Error: {msg}",
                 font=("Consolas", 10), fg=ACCENT, bg=BG).pack(anchor="w")

    def _display_stats(self, data, ref_data):
        for w in self._stats_frame.winfo_children():
            w.destroy()

        if not data:
            tk.Label(self._stats_frame, text="No stats available. Enter your API key.",
                     font=("Consolas", 10), fg=DIM, bg=BG).pack(anchor="w")
            return

        stats_items = [
            ("Total Checks", f"{data.get('total_checks', 0):,}", ACCENT2),
            ("Total Combos Checked", f"{data.get('total_combos_checked', 0):,}", ACCENT2),
            ("Total Searches", f"{data.get('total_searches', 0):,}", ACCENT2),
            ("Searches Today", str(data.get("searches_today", 0)), YELLOW),
            ("Files Downloaded", str(data.get("files_downloaded", 0)), GREEN),
            ("Account Age", f"{data.get('account_age_days', 0)} days", FG),
            ("Last Active", data.get("last_active", "Never"), DIM),
            ("Referrals Made", str(data.get("referral_count", 0)), GREEN),
            ("Referral Bonus Days", f"+{data.get('referral_bonus_days', 0)} days", GREEN),
        ]

        for label, value, color in stats_items:
            row = tk.Frame(self._stats_frame, bg=BG2, bd=1, relief="flat")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"  {label}", font=("Consolas", 10),
                     fg=DIM, bg=BG2, width=26, anchor="w").pack(side="left", padx=(6, 0))
            tk.Label(row, text=value, font=("Consolas", 11, "bold"),
                     fg=color, bg=BG2, anchor="w").pack(side="left", padx=10)

        # Update referral info
        if ref_data:
            code = ref_data.get("referral_code", "")
            bonus = ref_data.get("bonus_days", 7)
            self._referral_code_value = code
            self._referral_label.config(
                text=f"Your referral code: {code}  —  Share it! Each referral = +{bonus} days")
        else:
            self._referral_label.config(text="Could not load referral code.")

    def _copy_referral_code(self):
        if self._referral_code_value:
            self.clipboard_clear()
            self.clipboard_append(self._referral_code_value)
            self._referral_status_label.config(text="✓ Referral code copied!", fg=GREEN)
        else:
            self._referral_status_label.config(text="No referral code loaded.", fg=ACCENT)

    def _apply_referral(self):
        code = self._apply_ref_var.get().strip()
        if not code:
            self._referral_status_label.config(text="Enter a referral code first.", fg=ACCENT)
            return

        def _do_apply():
            try:
                result = apply_referral_code(code)
                if result and result.get("status") == "ok":
                    msg = result.get("message", "Referral applied!")
                    self.after(0, lambda: self._referral_status_label.config(text=f"✓ {msg}", fg=GREEN))
                else:
                    msg = result.get("message", "Failed") if result else "Failed"
                    self.after(0, lambda: self._referral_status_label.config(text=f"✗ {msg}", fg=ACCENT))
            except APIError as e:
                self.after(0, lambda: self._referral_status_label.config(text=f"✗ {e}", fg=ACCENT))
            except Exception as e:
                self.after(0, lambda: self._referral_status_label.config(text=f"Error: {e}", fg=ACCENT))
        threading.Thread(target=_do_apply, daemon=True).start()

    # ── Log tab (advanced viewer) ──────────────

    def _build_log_tab(self, parent):
        # ── Toolbar ──────────────────────────
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", padx=4, pady=(10, 0))

        tk.Label(toolbar, text="Filter:", font=("Consolas", 9),
                 fg=FG, bg=BG).pack(side="left")

        self._log_filter_var = tk.StringVar(value="ALL")
        for lvl in ("ALL", "INFO", "OK", "ERR", "DIM"):
            tk.Radiobutton(toolbar, text=lvl, variable=self._log_filter_var,
                           value=lvl, font=("Consolas", 9, "bold"),
                           fg=FG, bg=BG, selectcolor=BG2,
                           activebackground=BG, activeforeground=ACCENT2,
                           indicatoron=False, padx=8, pady=2, relief="flat",
                           command=self._refresh_adv_log).pack(side="left", padx=2)

        tk.Frame(toolbar, width=16, bg=BG).pack(side="left")

        tk.Label(toolbar, text="Search:", font=("Consolas", 9),
                 fg=FG, bg=BG).pack(side="left")
        self._log_search_var = tk.StringVar()
        self._log_search_var.trace_add("write", lambda *_: self._refresh_adv_log())
        tk.Entry(toolbar, textvariable=self._log_search_var, width=18,
                 font=("Consolas", 9), bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).pack(side="left", padx=(4, 0))

        # ── Action buttons ───────────────────
        btn_frame = tk.Frame(toolbar, bg=BG)
        btn_frame.pack(side="right")

        tk.Button(btn_frame, text="🗑 Clear", font=("Consolas", 9, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=8,
                  command=self._clear_log).pack(side="right", padx=(4, 0))

        tk.Button(btn_frame, text="💾 Export", font=("Consolas", 9, "bold"),
                  bg=ENTRY_BG, fg=FG, relief="flat", padx=8,
                  command=self._export_log).pack(side="right", padx=(4, 0))

        tk.Button(btn_frame, text="📋 Copy All", font=("Consolas", 9, "bold"),
                  bg=ENTRY_BG, fg=FG, relief="flat", padx=8,
                  command=self._copy_log).pack(side="right")

        # ── Counter ──────────────────────────
        count_row = tk.Frame(parent, bg=BG)
        count_row.pack(fill="x", padx=4, pady=(6, 0))
        self._log_count_label = tk.Label(count_row, text="0 entries",
                                         font=("Consolas", 9), fg=DIM, bg=BG)
        self._log_count_label.pack(side="left")

        # ── Text area ────────────────────────
        log_frame = tk.Frame(parent, bg=BG2)
        log_frame.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        self.adv_log_text = tk.Text(log_frame, bg=BG2, fg=FG,
                                    font=("Consolas", 9), relief="flat", bd=6,
                                    state="disabled", insertbackground=FG,
                                    selectbackground="#333355", wrap="word")
        scroll = tk.Scrollbar(log_frame, command=self.adv_log_text.yview)
        self.adv_log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.adv_log_text.pack(fill="both", expand=True)

        # Same tag colours as check log
        self.adv_log_text.tag_configure("info", foreground=ACCENT2)
        self.adv_log_text.tag_configure("ok", foreground=GREEN)
        self.adv_log_text.tag_configure("err", foreground=ACCENT)
        self.adv_log_text.tag_configure("dim", foreground=DIM)
        self.adv_log_text.tag_configure("ts", foreground="#777788",
                                        font=("Consolas", 8))
        self.adv_log_text.tag_configure("level_tag",
                                        font=("Consolas", 8, "bold"))

    def _append_adv_log(self, entry: dict, cur_filter: str):
        """Append a single log entry to the advanced log viewer."""
        level = entry["level"]
        if cur_filter != "ALL" and level != cur_filter:
            return
        search = self._log_search_var.get().lower() if hasattr(self, "_log_search_var") else ""
        if search and search not in entry["msg"].lower():
            return

        self.adv_log_text.configure(state="normal")
        self.adv_log_text.insert("end", f"[{entry['ts']}] ", "ts")
        lvl_tag = entry["tag"] or "info"
        self.adv_log_text.insert("end", f"[{level:>4s}] ", lvl_tag)
        self.adv_log_text.insert("end", entry["msg"] + "\n", entry["tag"])
        self.adv_log_text.see("end")
        self.adv_log_text.configure(state="disabled")

        # Update count
        if hasattr(self, "_log_count_label"):
            visible = int(self.adv_log_text.index("end-1c").split(".")[0])
            self._log_count_label.configure(text=f"{visible} entries")

    def _refresh_adv_log(self):
        """Re-render entire advanced log based on current filter + search."""
        cur_filter = self._log_filter_var.get()
        search = self._log_search_var.get().lower()

        self.adv_log_text.configure(state="normal")
        self.adv_log_text.delete("1.0", "end")
        self.adv_log_text.configure(state="disabled")

        count = 0
        for entry in self._log_entries:
            level = entry["level"]
            if cur_filter != "ALL" and level != cur_filter:
                continue
            if search and search not in entry["msg"].lower():
                continue
            self._append_adv_log_raw(entry)
            count += 1

        self._log_count_label.configure(text=f"{count} entries")

    def _append_adv_log_raw(self, entry: dict):
        """Append entry without filtering (used by _refresh_adv_log)."""
        self.adv_log_text.configure(state="normal")
        self.adv_log_text.insert("end", f"[{entry['ts']}] ", "ts")
        lvl_tag = entry["tag"] or "info"
        self.adv_log_text.insert("end", f"[{entry['level']:>4s}] ", lvl_tag)
        self.adv_log_text.insert("end", entry["msg"] + "\n", entry["tag"])
        self.adv_log_text.see("end")
        self.adv_log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_entries.clear()
        self.adv_log_text.configure(state="normal")
        self.adv_log_text.delete("1.0", "end")
        self.adv_log_text.configure(state="disabled")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log_count_label.configure(text="0 entries")

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            title="Export Log", defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for e in self._log_entries:
                    f.write(f"[{e['ts']}] [{e['level']:>4s}] {e['msg']}\n")
            self._log(f"Log exported to {os.path.basename(path)}", "ok")
        except Exception as e:
            self._log(f"Log export failed: {e}", "err")
            messagebox.showerror("Export Error", str(e))

    def _copy_log(self):
        text = "\n".join(
            f"[{e['ts']}] [{e['level']:>4s}] {e['msg']}"
            for e in self._log_entries)
        self.clipboard_clear()
        self.clipboard_append(text)
        if hasattr(self, "_log_count_label"):
            self._log_count_label.configure(text=f"Copied {len(self._log_entries)} entries!")

    # ── About tab ────────────────────────────

    def _build_about_tab(self, parent):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        # Logo / Title
        tk.Label(wrap, text="LEAKCHECK", font=("Consolas", 22, "bold"),
                 fg=ACCENT2, bg=BG).pack(anchor="w")
        tk.Label(wrap, text=f"v{CLIENT_VERSION}",
                 font=("Consolas", 12), fg=DIM, bg=BG).pack(anchor="w", pady=(0, 16))

        # Description
        desc = (
            "LEAKCHECK is a professional antipublic credential leak detection tool.\n"
            "It allows you to check large combo lists (email:password) against a\n"
            "server-side database to identify which credentials have\n"
            "already been exposed in public data breaches.\n\n"
            "Combos NOT found in the database are considered private/unique — these\n"
            "can be exported for further analysis."
        )
        tk.Label(wrap, text=desc, font=("Consolas", 9), fg=FG, bg=BG,
                 justify="left", anchor="w").pack(fill="x", pady=(0, 16))

        # Features
        features_frame = tk.Frame(wrap, bg=BG2, padx=14, pady=12)
        features_frame.pack(fill="x", pady=(0, 16))

        tk.Label(features_frame, text="Features", font=("Consolas", 11, "bold"),
                 fg=ACCENT2, bg=BG2).pack(anchor="w", pady=(0, 6))

        features = [
            "🔍  Batch combo checking against leak database",
            "📧  Email:password format validation",
            "🔄  Auto-remove duplicate lines",
            "📥  Download shared combo files from server",
            "💳  Buy subscription keys with USDT (Binance)",
            "🔒  HWID-locked API keys for security",
            "📋  Advanced log viewer with search & filter",
            "💾  Export results and logs",
        ]
        for feat in features:
            tk.Label(features_frame, text=feat, font=("Consolas", 9),
                     fg=FG, bg=BG2, anchor="w").pack(fill="x", pady=1)

        # Contact
        contact_frame = tk.Frame(wrap, bg=BG2, padx=14, pady=12)
        contact_frame.pack(fill="x")

        tk.Label(contact_frame, text="Developer", font=("Consolas", 11, "bold"),
                 fg=ACCENT2, bg=BG2).pack(anchor="w", pady=(0, 6))

        tk.Label(contact_frame, text="BionicSailor", font=("Consolas", 10, "bold"),
                 fg=FG, bg=BG2).pack(anchor="w")

        tg_row = tk.Frame(contact_frame, bg=BG2)
        tg_row.pack(anchor="w", pady=(4, 0))
        tk.Label(tg_row, text="Telegram:", font=("Consolas", 9),
                 fg=DIM, bg=BG2).pack(side="left")
        tg_link = tk.Label(tg_row, text="@BionicSailor", font=("Consolas", 10, "bold"),
                           fg=ACCENT2, bg=BG2, cursor="hand2")
        tg_link.pack(side="left", padx=(6, 0))
        tg_link.bind("<Button-1>", lambda e: __import__("webbrowser").open(
            "https://t.me/BionicSailor"))

        support_row = tk.Frame(contact_frame, bg=BG2)
        support_row.pack(anchor="w", pady=(4, 0))
        tk.Label(support_row, text="Support & purchases via Telegram DM",
                 font=("Consolas", 9), fg=DIM, bg=BG2).pack(side="left")

    # ── Close ────────────────────────────────

    def _on_close(self):
        self.destroy()
