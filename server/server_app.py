"""
LEAKCHECK Server — Desktop Admin Panel
Tkinter dark-themed GUI to control the Flask server.
Developed by BionicSailor  |  Telegram: @BionicSailor
"""

import os
import re
import sys
import hashlib
import threading
import time
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime, timezone

# ── Ensure server/ is on sys.path so imports resolve ──
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import CONFIG, BASE_DIR, KEYS_FILE, SHARED_DIR, UPDATES_DIR, UPDATE_META, MESSAGES_FILE
from database import (init_db, get_db_stats, insert_leak_data, insert_leak_data_iter,
                      get_leak_data_count, vacuum_db,
                      get_table_sizes, purge_old_logs, optimize_db, rebuild_indexes,
                      repack_db_larger_pages)
from auth import generate_key, revoke_key, list_all_keys, PLANS, get_key_info
from logger import (get_recent_activity, get_recent_uploads,
                    log_activity, log_upload)
from binance_pay import (PRICES, list_all_orders, fulfill_order, cancel_order,
                         start_payment_monitor, stop_payment_monitor)
import json
import shutil

# ── Theme ────────────────────────────────────
BG       = "#0f0f1a"
BG2      = "#1a1a2e"
BG3      = "#16213e"
FG       = "#e0e0e0"
ACCENT   = "#e94560"
ACCENT2  = "#00d2ff"
GREEN    = "#00e676"
YELLOW   = "#ffd600"
DIM      = "#555566"


class _GUILogHandler(logging.Handler):
    """Routes Python logging messages into the Tkinter Server Log text widget."""

    def __init__(self, app: "ServerApp"):
        super().__init__()
        self._app = app

    def emit(self, record):
        try:
            msg = self.format(record)
            tag = "dim"
            lower = msg.lower()
            if "error" in lower or "fail" in lower or record.levelno >= logging.ERROR:
                tag = "err"
            elif "→ 2" in msg:  # successful HTTP responses
                tag = "ok"
            elif "→ 4" in msg:  # 4xx responses
                tag = "err"
            elif "search" in lower or "check" in lower:
                tag = "info"
            self._app.after(0, self._app._log, msg, tag)
        except Exception:
            pass


class ServerApp(tk.Tk):
    """Main server admin window."""

    def __init__(self):
        super().__init__()
        self.title("LEAKCHECK Server — Admin Panel")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(920, 720)
        self._set_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._flask_thread: threading.Thread | None = None
        self._flask_app = None
        self._server_running = False

        init_db()
        self._build_ui()
        self._refresh_stats()

    # ── helpers ──────────────────────────────

    def _set_icon(self):
        """Set window icon from logo.ico."""
        ico = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logo.ico")
        if not os.path.isfile(ico):
            ico = os.path.join(_HERE, "logo.ico")
        if not os.path.isfile(ico):
            ico = os.path.join(os.path.dirname(_HERE), "logo.ico")
        if os.path.isfile(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def _center(self, w, h):
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _log(self, msg: str, tag: str = ""):
        if not hasattr(self, "log_text"):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] ", "dim")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ── UI ───────────────────────────────────

    def _build_ui(self):
        # ── Header row ───────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(hdr, text="LEAKCHECK SERVER", font=("Consolas", 20, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")

        self.status_dot = tk.Label(hdr, text="●", font=("Consolas", 16),
                                   fg=DIM, bg=BG)
        self.status_dot.pack(side="right")
        self.status_label = tk.Label(hdr, text="stopped", font=("Consolas", 10),
                                     fg=DIM, bg=BG)
        self.status_label.pack(side="right", padx=(0, 6))

        # ── Control row ─────────────────────
        ctl = tk.Frame(self, bg=BG)
        ctl.pack(fill="x", padx=16, pady=(10, 0))

        self.start_btn = tk.Button(ctl, text="▶  Start Server", font=("Consolas", 11, "bold"),
                                   bg=GREEN, fg="#000", relief="flat", padx=14, pady=4,
                                   command=self._start_server)
        self.start_btn.pack(side="left")

        self.stop_btn = tk.Button(ctl, text="■  Stop Server", font=("Consolas", 11, "bold"),
                                  bg=ACCENT, fg="white", relief="flat", padx=14, pady=4,
                                  state="disabled", command=self._stop_server)
        self.stop_btn.pack(side="left", padx=(8, 0))

        port_str = str(CONFIG.get("port", 5000))
        tk.Label(ctl, text=f"Port: {port_str}", font=("Consolas", 10),
                 fg=ACCENT2, bg=BG).pack(side="right")

        # ── Tabs (notebook) ──────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background=BG2, foreground=FG,
                        padding=[12, 6], font=("Consolas", 10, "bold"))
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT2)])

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        # ── Tab 1: Dashboard ─────────────────
        tab_dash = tk.Frame(nb, bg=BG2)
        nb.add(tab_dash, text="  Dashboard  ")
        self._build_dashboard(tab_dash)

        # ── Tab 2: Keys ──────────────────────
        tab_keys = tk.Frame(nb, bg=BG2)
        nb.add(tab_keys, text="  API Keys  ")
        self._build_keys_tab(tab_keys)

        # ── Tab 3: Import ────────────────────
        tab_import = tk.Frame(nb, bg=BG2)
        nb.add(tab_import, text="  Import  ")
        self._build_import_tab(tab_import)

        # ── Tab 4: Files (shared) ────────────
        tab_files = tk.Frame(nb, bg=BG2)
        nb.add(tab_files, text="  Files  ")
        self._build_files_tab(tab_files)

        # ── Tab 5: Orders (payments) ─────────
        tab_orders = tk.Frame(nb, bg=BG2)
        nb.add(tab_orders, text="  Orders  ")
        self._build_orders_tab(tab_orders)

        # ── Tab 6: Update ────────────────────
        tab_update = tk.Frame(nb, bg=BG2)
        nb.add(tab_update, text="  Update  ")
        self._build_update_tab(tab_update)

        # ── Tab 7: Activity Log ─────────────
        tab_activity = tk.Frame(nb, bg=BG2)
        nb.add(tab_activity, text="  Activity Log  ")
        self._build_activity_log_tab(tab_activity)

        # ── Tab 8: Messages ──────────────────
        tab_msg = tk.Frame(nb, bg=BG2)
        nb.add(tab_msg, text="  Messages  ")
        self._build_messages_tab(tab_msg)

        # ── Tab 9: Server Log ────────────────
        tab_log = tk.Frame(nb, bg=BG2)
        nb.add(tab_log, text="  Server Log  ")
        self._build_log_tab(tab_log)

        # ── Footer ───────────────────────────
        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=16, pady=(6, 10))
        tk.Label(foot, text="Developed by BionicSailor  •  Telegram: @BionicSailor",
                 font=("Consolas", 9), fg=DIM, bg=BG).pack(side="left")

    # ── Dashboard tab ────────────────────────

    def _build_dashboard(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        # stat cards
        self._stat_vars: dict[str, tk.StringVar] = {}
        cards = [
            ("Email:Pass DB", "leak_data"),
            ("DB Size", "db_size"),
            ("Active Users (24h)", "active_users"),
            ("Queries (1h)", "queries_1h"),
            ("Queries (24h)", "queries_24h"),
        ]
        card_frame = tk.Frame(f, bg=BG2)
        card_frame.pack(fill="x")
        for i, (label, key) in enumerate(cards):
            cf = tk.Frame(card_frame, bg=BG3, padx=14, pady=10)
            cf.grid(row=0, column=i, padx=6, pady=6, sticky="nsew")
            card_frame.columnconfigure(i, weight=1)
            tk.Label(cf, text=label, font=("Consolas", 8), fg=DIM, bg=BG3).pack()
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            tk.Label(cf, textvariable=var, font=("Consolas", 16, "bold"),
                     fg=ACCENT2, bg=BG3).pack()

        # ── Action buttons row ──
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(pady=(14, 0))

        tk.Button(btn_row, text="🔄  Refresh Stats", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=4,
                  command=self._refresh_stats).pack(side="left", padx=4)

        tk.Button(btn_row, text="🧹  VACUUM", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=YELLOW, relief="flat", padx=10, pady=4,
                  command=self._maintain_db).pack(side="left", padx=4)

        btn_row2 = tk.Frame(f, bg=BG2)
        btn_row2.pack(pady=(6, 0))

        tk.Button(btn_row2, text="⚡  Full Optimize", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=GREEN, relief="flat", padx=10, pady=4,
                  command=self._full_optimize).pack(side="left", padx=4)

        tk.Button(btn_row2, text="🗑  Purge Old Logs", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=ACCENT, relief="flat", padx=10, pady=4,
                  command=self._purge_logs).pack(side="left", padx=4)

        tk.Button(btn_row2, text="🔧  Rebuild Indexes", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=ACCENT2, relief="flat", padx=10, pady=4,
                  command=self._rebuild_indexes).pack(side="left", padx=4)

        tk.Button(btn_row2, text="📊  Table Sizes", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=4,
                  command=self._show_table_sizes).pack(side="left", padx=4)

        # ── Row 3: Space-saving operations ──
        sep = tk.Frame(f, bg=DIM, height=1)
        sep.pack(fill="x", padx=20, pady=(10, 4))
        tk.Label(f, text="Space Reduction", font=("Consolas", 9, "bold"),
                 fg=DIM, bg=BG2).pack()

        btn_row3 = tk.Frame(f, bg=BG2)
        btn_row3.pack(pady=(4, 0))

        tk.Button(btn_row3, text="📦  Repack (8K pages)", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=ACCENT2, relief="flat", padx=10, pady=4,
                  command=self._repack_pages).pack(side="left", padx=4)

    def _refresh_stats(self):
        try:
            s = get_db_stats()
            self._stat_vars["leak_data"].set(f"{get_leak_data_count():,}")
            self._stat_vars["db_size"].set(f"{s['db_size_mb']:.1f} MB")
            self._stat_vars["active_users"].set(str(s.get("active_users_24h", 0)))
            self._stat_vars["queries_1h"].set(str(s.get("queries_1h", 0)))
            self._stat_vars["queries_24h"].set(str(s.get("queries_24h", 0)))
        except Exception as e:
            self._log(f"Stats error: {e}", "err")

    def _maintain_db(self):
        def _do():
            self._log("Running VACUUM maintenance...", "info")
            vacuum_db()
            self._log("VACUUM complete.", "ok")
            self.after(0, self._refresh_stats)
        threading.Thread(target=_do, daemon=True).start()

    def _full_optimize(self):
        """Purge old logs + ANALYZE + VACUUM in one click."""
        def _do():
            self._log("Running full optimization (purge logs > 30d + ANALYZE + VACUUM)...", "info")
            try:
                result = optimize_db()
                saved = result['saved_mb']
                self._log(
                    f"Optimization complete — "
                    f"Before: {result['size_before_mb']:.1f} MB → After: {result['size_after_mb']:.1f} MB "
                    f"(saved {saved:.1f} MB)",
                    "ok"
                )
                lp = result['logs_purged']
                self._log(
                    f"  Logs purged: activity={lp.get('activity_log',0):,}, "
                    f"search={lp.get('search_log',0):,}, "
                    f"upload={lp.get('upload_log',0):,}",
                    "info"
                )
            except Exception as e:
                self._log(f"Optimization error: {e}", "err")
            self.after(0, self._refresh_stats)
        threading.Thread(target=_do, daemon=True).start()

    def _purge_logs(self):
        """Prompt for days and purge old log entries."""
        days = simpledialog.askinteger(
            "Purge Old Logs",
            "Delete log entries older than how many days?",
            initialvalue=30, minvalue=1, maxvalue=3650,
            parent=self
        )
        if days is None:
            return

        def _do():
            self._log(f"Purging logs older than {days} days...", "info")
            try:
                deleted = purge_old_logs(days)
                total = sum(deleted.values())
                self._log(
                    f"Purged {total:,} log entries — "
                    f"activity={deleted.get('activity_log',0):,}, "
                    f"search={deleted.get('search_log',0):,}, "
                    f"upload={deleted.get('upload_log',0):,}",
                    "ok"
                )
                # VACUUM after purge to actually reclaim disk space
                self._log("Running VACUUM to reclaim space...", "info")
                vacuum_db()
                self._log("VACUUM complete.", "ok")
            except Exception as e:
                self._log(f"Purge error: {e}", "err")
            self.after(0, self._refresh_stats)
        threading.Thread(target=_do, daemon=True).start()

    def _rebuild_indexes(self):
        """Drop and recreate all secondary indexes."""
        def _do():
            self._log("Rebuilding indexes...", "info")
            try:
                count = rebuild_indexes()
                self._log(f"Rebuilt {count} indexes. Running VACUUM...", "info")
                vacuum_db()
                self._log("Index rebuild + VACUUM complete.", "ok")
            except Exception as e:
                self._log(f"Rebuild error: {e}", "err")
            self.after(0, self._refresh_stats)
        threading.Thread(target=_do, daemon=True).start()

    def _show_table_sizes(self):
        """Show a popup with per-table size breakdown."""
        def _do():
            try:
                sizes = get_table_sizes()
                # Build popup on the main thread
                self.after(0, lambda: self._display_table_sizes(sizes))
            except Exception as e:
                self._log(f"Table sizes error: {e}", "err")
        threading.Thread(target=_do, daemon=True).start()

    def _display_table_sizes(self, sizes: list[dict]):
        """Display table size breakdown in a top-level window."""
        win = tk.Toplevel(self)
        win.title("Database Table Sizes")
        win.configure(bg=BG)
        win.resizable(False, False)
        w, h = 620, 400
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(win, text="Table / Index Size Breakdown",
                 font=("Consolas", 12, "bold"), fg=ACCENT2, bg=BG).pack(pady=(10, 4))

        cols = ("name", "rows", "pages", "size")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        tree.heading("name", text="Table / Index")
        tree.heading("rows", text="Rows")
        tree.heading("pages", text="Pages")
        tree.heading("size", text="Size (MB)")
        tree.column("name", width=280)
        tree.column("rows", width=100, anchor="e")
        tree.column("pages", width=80, anchor="e")
        tree.column("size", width=100, anchor="e")

        total_mb = 0
        for t in sizes:
            tree.insert("", "end", values=(
                t["name"],
                f"{t['row_count']:,}" if t["row_count"] else "",
                f"{t['page_count']:,}",
                f"{t['size_mb']:.2f}",
            ))
            total_mb += t["size_mb"]

        tree.insert("", "end", values=("─" * 30, "", "", f"{total_mb:.2f}"))
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tk.Button(win, text="Close", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=16, pady=4,
                  command=win.destroy).pack(pady=(0, 10))

    def _repack_pages(self):
        """Rebuild DB with larger page size for better space efficiency."""
        if not messagebox.askyesno(
            "Repack Database",
            "This will rebuild the database with 8KB pages (currently 4KB).\n"
            "Larger pages reduce B-tree overhead and can save 5-15%.\n\n"
            "Requires ~2x free disk space during the operation.\n"
            "This may take several minutes. Continue?",
            parent=self
        ):
            return

        def _do():
            self._log("Repacking database with 8KB pages...", "info")
            try:
                result = repack_db_larger_pages(8192)
                if result.get("status") == "skipped":
                    self._log(f"Repack skipped: {result['reason']}", "info")
                else:
                    self._log(
                        f"Repack complete — "
                        f"Pages: {result['old_page_size']} → {result['new_page_size']} bytes\n"
                        f"  Before: {result['size_before_mb']:.1f} MB → "
                        f"After: {result['size_after_mb']:.1f} MB "
                        f"(saved {result['saved_mb']:.1f} MB)",
                        "ok"
                    )
            except Exception as e:
                self._log(f"Repack error: {e}", "err")
            self.after(0, self._refresh_stats)
        threading.Thread(target=_do, daemon=True).start()

    # ── Keys tab ─────────────────────────────

    def _build_keys_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill="x")

        tk.Button(btn_row, text="➕  Generate Key", font=("Consolas", 10, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=10, pady=3,
                  command=self._gen_key).pack(side="left")
        tk.Button(btn_row, text="🗑  Revoke Selected", font=("Consolas", 10, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=10, pady=3,
                  command=self._revoke_selected).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="🔄  Refresh", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._refresh_keys).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="📋  Copy Key", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._copy_key).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="🔓  Reset HWID", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._reset_hwid).pack(side="left", padx=(8, 0))

        # Keys list
        cols = ("key", "username", "plan", "expires", "hwid", "status")
        self.keys_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        self.keys_tree.heading("key", text="API Key")
        self.keys_tree.heading("username", text="Username")
        self.keys_tree.heading("plan", text="Plan")
        self.keys_tree.heading("expires", text="Expires")
        self.keys_tree.heading("hwid", text="HWID")
        self.keys_tree.heading("status", text="Status")
        self.keys_tree.column("key", width=180)
        self.keys_tree.column("username", width=90)
        self.keys_tree.column("plan", width=70, anchor="center")
        self.keys_tree.column("expires", width=100, anchor="center")
        self.keys_tree.column("hwid", width=100, anchor="center")
        self.keys_tree.column("status", width=80, anchor="center")

        style = ttk.Style()
        style.configure("Treeview", background=BG3, foreground=FG,
                        fieldbackground=BG3, font=("Consolas", 9))
        style.configure("Treeview.Heading", background=BG2, foreground=ACCENT2,
                        font=("Consolas", 9, "bold"))

        scroll_k = tk.Scrollbar(f, command=self.keys_tree.yview)
        self.keys_tree.configure(yscrollcommand=scroll_k.set)

        self.keys_tree.pack(fill="both", expand=True, pady=(8, 0), side="left")
        scroll_k.pack(fill="y", side="right", pady=(8, 0))

        # Tag colours for treeview rows
        self.keys_tree.tag_configure("expired", foreground=ACCENT)
        self.keys_tree.tag_configure("warning", foreground=YELLOW)
        self.keys_tree.tag_configure("active", foreground=GREEN)
        self.keys_tree.tag_configure("revoked", foreground=DIM)

        self._refresh_keys()

    def _refresh_keys(self):
        for item in self.keys_tree.get_children():
            self.keys_tree.delete(item)
        keys = list_all_keys()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for k, v in keys.items():
            plan_label = v.get("plan_label", v.get("plan", "legacy"))
            expires_at = v.get("expires_at")
            active = v.get("active", False)

            if not active:
                status_str = "❌ Revoked"
                tag = "revoked"
                exp_str = "—"
            elif not expires_at:
                status_str = "✅ Active"
                tag = "active"
                exp_str = "Lifetime"
            else:
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                    days_left = (exp_dt - now).days
                    exp_str = expires_at[:10]
                    if days_left < 0:
                        status_str = "❌ Expired"
                        tag = "expired"
                    elif days_left <= 7:
                        status_str = f"⚠ {days_left}d left"
                        tag = "warning"
                    else:
                        status_str = f"✅ {days_left}d left"
                        tag = "active"
                except Exception:
                    exp_str = expires_at[:10] if expires_at else "?"
                    status_str = "?"
                    tag = "active"

            hwid_str = v.get("hwid") or "—"
            if hwid_str != "—":
                hwid_str = hwid_str[:12] + "..."

            self.keys_tree.insert("", "end",
                                  values=(k, v.get("username", ""), plan_label, exp_str, hwid_str, status_str),
                                  tags=(tag,))

    def _reset_hwid(self):
        sel = self.keys_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a key to reset HWID.")
            return
        item = self.keys_tree.item(sel[0])
        target_key = item["values"][0]
        username = item["values"][1]
        if not messagebox.askyesno("Reset HWID",
                                   f"Unbind HWID for '{username}'?\nKey can be used on a new device."):
            return
        from auth import reset_hwid
        reset_hwid(str(target_key))
        self._log(f"Reset HWID for '{username}'", "info")
        self._refresh_keys()

    def _gen_key(self):
        # Dialog window for username + plan selection
        dlg = tk.Toplevel(self)
        dlg.title("Generate API Key")
        dlg.configure(bg=BG2)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        w, h = 380, 240
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dlg, text="Generate New API Key", font=("Consolas", 12, "bold"),
                 fg=ACCENT2, bg=BG2).pack(pady=(14, 10))

        # Username
        row1 = tk.Frame(dlg, bg=BG2)
        row1.pack(fill="x", padx=20)
        tk.Label(row1, text="Username:", font=("Consolas", 10), fg=FG, bg=BG2).pack(side="left")
        name_var = tk.StringVar()
        tk.Entry(row1, textvariable=name_var, width=24, font=("Consolas", 10),
                 bg=BG3, fg=FG, insertbackground=FG, relief="flat", bd=4).pack(side="left", padx=(8, 0))

        # Plan dropdown
        row2 = tk.Frame(dlg, bg=BG2)
        row2.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(row2, text="Plan:", font=("Consolas", 10), fg=FG, bg=BG2).pack(side="left")
        plan_labels = [p["label"] for p in PLANS.values()]
        plan_keys = list(PLANS.keys())
        plan_var = tk.StringVar(value=plan_labels[0])
        plan_menu = ttk.Combobox(row2, textvariable=plan_var, values=plan_labels,
                                  state="readonly", width=16, font=("Consolas", 10))
        plan_menu.pack(side="left", padx=(8, 0))
        plan_menu.current(0)

        result = {"key": None}

        def _do_gen():
            username = name_var.get().strip()
            if not username:
                messagebox.showwarning("Required", "Enter a username.", parent=dlg)
                return
            sel_label = plan_var.get()
            sel_plan = "1_month"
            for pk, pv in PLANS.items():
                if pv["label"] == sel_label:
                    sel_plan = pk
                    break
            key = generate_key(username, sel_plan)
            result["key"] = key
            self._log(f"Generated key for '{username}' ({sel_label}): {key[:20]}...", "ok")
            self._refresh_keys()
            self.clipboard_clear()
            self.clipboard_append(key)
            dlg.destroy()
            messagebox.showinfo("Key Generated",
                                f"Username: {username}\nPlan: {sel_label}\nKey: {key}\n\n(Copied to clipboard)")

        tk.Button(dlg, text="➕  Generate", font=("Consolas", 11, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=16, pady=6,
                  command=_do_gen).pack(pady=(20, 0))

    def _revoke_selected(self):
        sel = self.keys_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a key to revoke.")
            return
        item = self.keys_tree.item(sel[0])
        target_key = item["values"][0]
        username = item["values"][1]
        if not messagebox.askyesno("Confirm Revoke",
                                   f"Revoke key for '{username}'?\n{target_key[:30]}..."):
            return
        revoke_key(str(target_key))
        self._log(f"Revoked key for '{username}'", "err")
        self._refresh_keys()

    def _copy_key(self):
        sel = self.keys_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a key first.")
            return
        key = self.keys_tree.item(sel[0])["values"][0]
        self.clipboard_clear()
        self.clipboard_append(str(key))
        self._log(f"Copied key to clipboard: {str(key)[:20]}...", "info")

    # ── Import tab ───────────────────────────

    def _build_import_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(f, text="Import combolist into the leak database",
                 font=("Consolas", 11), fg=FG, bg=BG2).pack(anchor="w")
        tk.Label(f, text="Each line (email:password) is stored for duplicate detection.",
                 font=("Consolas", 9), fg=DIM, bg=BG2).pack(anchor="w", pady=(2, 8))

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill="x")

        tk.Button(btn_row, text="📂  Select Combofile", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=12, pady=4,
                  command=self._import_file).pack(side="left")

        # Options row
        opt_row = tk.Frame(f, bg=BG2)
        opt_row.pack(fill="x", pady=(6, 0))

        self.import_dedup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_row, text="Auto-remove duplicates",
                       variable=self.import_dedup_var, font=("Consolas", 9),
                       fg=FG, bg=BG2, selectcolor=BG3,
                       activebackground=BG2, activeforeground=FG).pack(side="left")

        self.import_status = tk.Label(f, text="", font=("Consolas", 10),
                                      fg=ACCENT2, bg=BG2, anchor="w")
        self.import_status.pack(fill="x", pady=(8, 0))

        # Progress bar for import
        self.import_prog_canvas = tk.Canvas(f, height=18, bg=BG3,
                                            highlightthickness=0)
        self.import_prog_canvas.pack(fill="x", pady=(6, 0))
        self.import_prog_bar = self.import_prog_canvas.create_rectangle(
            0, 0, 0, 18, fill=ACCENT2, width=0)
        self.import_prog_text = self.import_prog_canvas.create_text(
            400, 9, text="", font=("Consolas", 9), fill=FG)

    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Select Combofile to Import",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        def _do():
            try:
                filename = os.path.basename(path)
                self.after(0, lambda: self.import_status.configure(
                    text=f"Reading {filename}..."))

                # Count lines without loading entire file into memory
                total = 0
                with open(path, "r", errors="ignore") as fh:
                    for _ in fh:
                        total += 1
                if total == 0:
                    self.after(0, lambda: self.import_status.configure(
                        text=f"No lines in {filename}"))
                    return

                self._log(f"Import: streaming {filename} ({total:,} lines)", "info")
                self.after(0, lambda: self.import_status.configure(
                    text=f"Importing {total:,} lines from {filename}..."))

                # Validate + dedup regex
                _email_re = re.compile(
                    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}:.+$')
                do_dedup = self.import_dedup_var.get()

                def _validated_lines():
                    """Generator that yields valid, optionally deduped lines."""
                    seen = set() if do_dedup else None
                    rejected = 0
                    dupes = 0
                    for raw in open(path, "r", errors="ignore"):
                        line = raw.strip()
                        if not line:
                            continue
                        if not _email_re.match(line):
                            rejected += 1
                            continue
                        if seen is not None:
                            if line in seen:
                                dupes += 1
                                continue
                            seen.add(line)
                        yield line
                    # Log rejection / dedup summary via closure
                    _validated_lines._rejected = rejected
                    _validated_lines._dupes = dupes

                _validated_lines._rejected = 0
                _validated_lines._dupes = 0

                # Progress callback updates the GUI
                _last_update = [0.0]
                def _prog(inserted_so_far, parsed_so_far):
                    now = time.time()
                    if now - _last_update[0] < 0.15:  # throttle UI updates
                        return
                    _last_update[0] = now
                    self.after(0, self._update_import_prog, parsed_so_far, total)

                total_inserted = insert_leak_data_iter(
                    _validated_lines(), batch_size=50_000, progress_cb=_prog)

                # Final progress
                self.after(0, self._update_import_prog, total, total)

                rejected = _validated_lines._rejected
                dupes = _validated_lines._dupes
                if rejected:
                    self._log(f"Import: skipped {rejected:,} invalid format lines", "info")
                if dupes:
                    self._log(f"Import: skipped {dupes:,} duplicate lines", "info")

                self.after(0, lambda: self.import_status.configure(
                    text=f"Done — {total_inserted:,} new combos imported from {filename}"))
                self._log(f"Import complete: {total_inserted:,} new email:pass pairs from {filename}", "ok")
                self.after(0, self._refresh_stats)

            except Exception as e:
                self._log(f"Import error: {e}", "err")
                self.after(0, lambda: self.import_status.configure(
                    text=f"Error: {e}"))

        threading.Thread(target=_do, daemon=True).start()

    def _update_import_prog(self, done, total):
        if total == 0:
            return
        frac = done / total
        w = self.import_prog_canvas.winfo_width()
        self.import_prog_canvas.coords(self.import_prog_bar, 0, 0, w * frac, 18)
        pct = int(frac * 100)
        self.import_prog_canvas.itemconfigure(
            self.import_prog_text, text=f"{done:,} / {total:,}  ({pct}%)")

    # ── Files tab (shared private combos) ────

    def _build_files_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(f, text="Shared files available for client download",
                 font=("Consolas", 11), fg=FG, bg=BG2).pack(anchor="w")
        tk.Label(f, text="Upload combo files here — clients can browse and download them.",
                 font=("Consolas", 9), fg=DIM, bg=BG2).pack(anchor="w", pady=(2, 8))

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill="x")

        tk.Button(btn_row, text="📂  Upload File", font=("Consolas", 10, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=10, pady=3,
                  command=self._upload_shared_file).pack(side="left")
        tk.Button(btn_row, text="🗑  Delete Selected", font=("Consolas", 10, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=10, pady=3,
                  command=self._delete_shared_file).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="🔄  Refresh", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._refresh_shared_files).pack(side="left", padx=(8, 0))

        # Files treeview
        cols = ("name", "size", "modified")
        self.files_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        self.files_tree.heading("name", text="Filename")
        self.files_tree.heading("size", text="Size")
        self.files_tree.heading("modified", text="Modified")
        self.files_tree.column("name", width=360)
        self.files_tree.column("size", width=120, anchor="center")
        self.files_tree.column("modified", width=180, anchor="center")

        scroll_f = tk.Scrollbar(f, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scroll_f.set)

        self.files_tree.pack(fill="both", expand=True, pady=(8, 0), side="left")
        scroll_f.pack(fill="y", side="right", pady=(8, 0))

        self.shared_file_count = tk.Label(f, text="", font=("Consolas", 9),
                                          fg=DIM, bg=BG2)
        # Place count label at bottom via a wrapper
        self._refresh_shared_files()

    def _refresh_shared_files(self):
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        os.makedirs(SHARED_DIR, exist_ok=True)
        count = 0
        for fname in sorted(os.listdir(SHARED_DIR)):
            fpath = os.path.join(SHARED_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                size_mb = stat.st_size / (1024 * 1024)
                if size_mb >= 1:
                    size_str = f"{size_mb:.1f} MB"
                else:
                    size_str = f"{stat.st_size / 1024:.1f} KB"
                mod = time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(stat.st_mtime))
                self.files_tree.insert("", "end", values=(fname, size_str, mod))
                count += 1
        self._log(f"Shared files refreshed — {count} file(s)", "info")

    def _upload_shared_file(self):
        paths = filedialog.askopenfilenames(
            title="Select File(s) to Share",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not paths:
            return
        import shutil
        os.makedirs(SHARED_DIR, exist_ok=True)
        for path in paths:
            fname = os.path.basename(path)
            dest = os.path.join(SHARED_DIR, fname)
            shutil.copy2(path, dest)
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            self._log(f"Uploaded shared file: {fname} ({size_mb:.1f} MB)", "ok")
        self._refresh_shared_files()

    def _delete_shared_file(self):
        sel = self.files_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a file to delete.")
            return
        item = self.files_tree.item(sel[0])
        fname = item["values"][0]
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete shared file '{fname}'?\nClients will no longer be able to download it."):
            return
        fpath = os.path.join(SHARED_DIR, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
            self._log(f"Deleted shared file: {fname}", "err")
        self._refresh_shared_files()

    # ── Orders tab (Binance payments) ────────

    def _build_orders_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Binance settings row ─────────────
        settings_frame = tk.Frame(f, bg=BG3, padx=10, pady=8)
        settings_frame.pack(fill="x", pady=(0, 8))

        tk.Label(settings_frame, text="Binance Payment Settings",
                 font=("Consolas", 9, "bold"), fg=DIM, bg=BG3).grid(
                     row=0, column=0, columnspan=6, sticky="w", pady=(0, 4))

        tk.Label(settings_frame, text="API Key:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=1, column=0, sticky="w")
        self._bn_key_var = tk.StringVar(value=CONFIG.get("binance_api_key", ""))
        tk.Entry(settings_frame, textvariable=self._bn_key_var, width=28,
                 font=("Consolas", 8), bg=BG2, fg=FG, show="*",
                 insertbackground=FG, relief="flat", bd=3).grid(
                     row=1, column=1, padx=(4, 8))

        tk.Label(settings_frame, text="Secret:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=1, column=2, sticky="w")
        self._bn_secret_var = tk.StringVar(value=CONFIG.get("binance_api_secret", ""))
        tk.Entry(settings_frame, textvariable=self._bn_secret_var, width=28,
                 font=("Consolas", 8), bg=BG2, fg=FG, show="*",
                 insertbackground=FG, relief="flat", bd=3).grid(
                     row=1, column=3, padx=(4, 8))

        tk.Label(settings_frame, text="USDT Addr:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self._bn_addr_var = tk.StringVar(value=CONFIG.get("usdt_address", ""))
        tk.Entry(settings_frame, textvariable=self._bn_addr_var, width=36,
                 font=("Consolas", 8), bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", bd=3).grid(
                     row=2, column=1, columnspan=2, padx=(4, 8), pady=(4, 0), sticky="w")

        tk.Label(settings_frame, text="Network:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=2, column=3, sticky="w", pady=(4, 0))
        self._bn_net_var = tk.StringVar(value=CONFIG.get("usdt_network", "TRC20"))
        ttk.Combobox(settings_frame, textvariable=self._bn_net_var,
                     values=["TRC20", "BEP20", "ERC20", "SOL", "TON"],
                     state="readonly", width=8, font=("Consolas", 8)).grid(
                         row=2, column=4, padx=(4, 0), pady=(4, 0), sticky="w")

        tk.Button(settings_frame, text="💾 Save", font=("Consolas", 8, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=8,
                  command=self._save_binance_settings).grid(
                      row=2, column=5, padx=(8, 0), pady=(4, 0))

        # ── Order buttons ────────────────────
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill="x")

        tk.Button(btn_row, text="🔄  Refresh", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._refresh_orders).pack(side="left")
        tk.Button(btn_row, text="✅  Manual Fulfill", font=("Consolas", 10, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=10, pady=3,
                  command=self._manual_fulfill_order).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="❌  Cancel Order", font=("Consolas", 10, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=10, pady=3,
                  command=self._cancel_order).pack(side="left", padx=(8, 0))

        # ── Orders treeview ──────────────────
        cols = ("oid", "plan", "amount", "username", "status", "key", "created")
        self.orders_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        self.orders_tree.heading("oid", text="Order ID")
        self.orders_tree.heading("plan", text="Plan")
        self.orders_tree.heading("amount", text="Amount")
        self.orders_tree.heading("username", text="Username")
        self.orders_tree.heading("status", text="Status")
        self.orders_tree.heading("key", text="API Key")
        self.orders_tree.heading("created", text="Created")
        self.orders_tree.column("oid", width=100)
        self.orders_tree.column("plan", width=70, anchor="center")
        self.orders_tree.column("amount", width=80, anchor="center")
        self.orders_tree.column("username", width=80)
        self.orders_tree.column("status", width=80, anchor="center")
        self.orders_tree.column("key", width=160)
        self.orders_tree.column("created", width=130, anchor="center")

        self.orders_tree.tag_configure("paid", foreground=GREEN)
        self.orders_tree.tag_configure("pending", foreground=YELLOW)
        self.orders_tree.tag_configure("expired", foreground=ACCENT)
        self.orders_tree.tag_configure("cancelled", foreground=DIM)

        scroll_o = tk.Scrollbar(f, command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scroll_o.set)
        self.orders_tree.pack(fill="both", expand=True, pady=(8, 0), side="left")
        scroll_o.pack(fill="y", side="right", pady=(8, 0))

        self._refresh_orders()

    def _save_binance_settings(self):
        """Persist Binance settings to server_config.json and reload CONFIG."""
        CONFIG["binance_api_key"] = self._bn_key_var.get().strip()
        CONFIG["binance_api_secret"] = self._bn_secret_var.get().strip()
        CONFIG["usdt_address"] = self._bn_addr_var.get().strip()
        CONFIG["usdt_network"] = self._bn_net_var.get().strip()

        from config import CONFIG_FILE
        import json as _json
        try:
            with open(CONFIG_FILE, "w") as fh:
                _json.dump(CONFIG, fh, indent=4)
            self._log("Binance settings saved.", "ok")
        except Exception as e:
            self._log(f"Error saving settings: {e}", "err")

    def _refresh_orders(self):
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        orders = list_all_orders()
        for oid, o in sorted(orders.items(), key=lambda x: x[1].get("created_at", ""),
                              reverse=True):
            status = o.get("status", "?")
            key_str = (o.get("api_key") or "—")
            if key_str != "—" and len(key_str) > 20:
                key_str = key_str[:20] + "..."
            created = (o.get("created_at") or "")[:19].replace("T", " ")

            tag = status if status in ("paid", "pending", "expired", "cancelled") else ""
            status_icon = {"paid": "✅", "pending": "⏳", "expired": "❌",
                           "cancelled": "🚫"}.get(status, "?")

            self.orders_tree.insert("", "end", values=(
                oid,
                o.get("plan_label", o.get("plan", "")),
                f"${o.get('amount', 0):.4f}",
                o.get("username", ""),
                f"{status_icon} {status.title()}",
                key_str,
                created,
            ), tags=(tag,))

    def _manual_fulfill_order(self):
        sel = self.orders_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a pending order to fulfill.")
            return
        item = self.orders_tree.item(sel[0])
        oid = item["values"][0]
        username = item["values"][3]

        if not messagebox.askyesno("Manual Fulfill",
                                   f"Manually fulfill order {oid} for '{username}'?\n"
                                   "An API key will be generated."):
            return

        key = fulfill_order(str(oid), txid="manual_admin")
        if key:
            self._log(f"Fulfilled order {oid} — key: {key[:20]}...", "ok")
            self.clipboard_clear()
            self.clipboard_append(key)
            messagebox.showinfo("Order Fulfilled",
                                f"Key generated for {username}:\n{key}\n\n(Copied to clipboard)")
        else:
            self._log(f"Could not fulfill order {oid} (not pending?)", "err")
        self._refresh_orders()
        self._refresh_keys()

    def _cancel_order(self):
        sel = self.orders_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a pending order to cancel.")
            return
        item = self.orders_tree.item(sel[0])
        oid = item["values"][0]

        if not messagebox.askyesno("Cancel Order", f"Cancel order {oid}?"):
            return

        if cancel_order(str(oid)):
            self._log(f"Cancelled order {oid}", "err")
        else:
            self._log(f"Could not cancel order {oid} (not pending?)", "err")
        self._refresh_orders()

    # ── Update tab (push OTA to clients) ─────

    def _build_update_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(f, text="Push OTA Update to Clients",
                 font=("Consolas", 12, "bold"), fg=ACCENT2, bg=BG2).pack(anchor="w")
        tk.Label(f, text="Select the new LeakCheck.exe, set the version, and push.",
                 font=("Consolas", 9), fg=DIM, bg=BG2).pack(anchor="w", pady=(2, 10))

        # Current update info card
        info_frame = tk.Frame(f, bg=BG3, padx=14, pady=10)
        info_frame.pack(fill="x", pady=(0, 10))
        tk.Label(info_frame, text="Current Published Update", font=("Consolas", 9, "bold"),
                 fg=DIM, bg=BG3).pack(anchor="w")
        self._update_info_var = tk.StringVar(value="Loading...")
        tk.Label(info_frame, textvariable=self._update_info_var,
                 font=("Consolas", 10), fg=FG, bg=BG3, justify="left",
                 anchor="w").pack(fill="x", pady=(4, 0))
        self._refresh_update_info()

        # File selection
        file_row = tk.Frame(f, bg=BG2)
        file_row.pack(fill="x", pady=(4, 0))
        tk.Label(file_row, text="File:", font=("Consolas", 10),
                 fg=FG, bg=BG2).pack(side="left")
        self._update_file_var = tk.StringVar(value="No file selected")
        tk.Label(file_row, textvariable=self._update_file_var,
                 font=("Consolas", 9), fg=ACCENT2, bg=BG2, anchor="w").pack(
                     side="left", fill="x", expand=True, padx=(8, 8))
        tk.Button(file_row, text="📂  Browse", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._browse_update_file).pack(side="right")

        # Version input
        ver_row = tk.Frame(f, bg=BG2)
        ver_row.pack(fill="x", pady=(10, 0))
        tk.Label(ver_row, text="Version:", font=("Consolas", 10),
                 fg=FG, bg=BG2).pack(side="left")
        self._update_ver_var = tk.StringVar(value="")
        tk.Entry(ver_row, textvariable=self._update_ver_var, width=16,
                 font=("Consolas", 11), bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).pack(side="left", padx=(8, 0))
        tk.Label(ver_row, text="(e.g. 2.1.0)", font=("Consolas", 9),
                 fg=DIM, bg=BG2).pack(side="left", padx=(8, 0))

        # Changelog input
        tk.Label(f, text="Changelog (optional):", font=("Consolas", 10),
                 fg=FG, bg=BG2).pack(anchor="w", pady=(10, 2))
        self._update_changelog = tk.Text(f, height=4, bg=BG3, fg=FG,
                                          font=("Consolas", 9), relief="flat",
                                          bd=6, insertbackground=FG, wrap="word")
        self._update_changelog.pack(fill="x")

        # Push button + status
        push_row = tk.Frame(f, bg=BG2)
        push_row.pack(fill="x", pady=(12, 0))
        self._push_btn = tk.Button(push_row, text="🚀  Push Update",
                                    font=("Consolas", 11, "bold"),
                                    bg=GREEN, fg="#000", relief="flat",
                                    padx=16, pady=4,
                                    command=self._push_update)
        self._push_btn.pack(side="left")
        self._push_status = tk.Label(push_row, text="", font=("Consolas", 9),
                                     fg=ACCENT2, bg=BG2)
        self._push_status.pack(side="left", padx=(12, 0))

        self._update_file_path: str | None = None

    def _refresh_update_info(self):
        """Read update.json and display current published version."""
        try:
            if os.path.isfile(UPDATE_META):
                with open(UPDATE_META, "r") as f:
                    meta = json.load(f)
                ver = meta.get("version", "?")
                fname = meta.get("filename", "?")
                date = meta.get("date", "?")[:19]
                sha = meta.get("sha256", "?")[:16] + "..."
                self._update_info_var.set(
                    f"v{ver}  |  {fname}  |  {date}  |  SHA: {sha}")
            else:
                self._update_info_var.set("No update published yet.")
        except Exception as e:
            self._update_info_var.set(f"Error: {e}")

    def _browse_update_file(self):
        path = filedialog.askopenfilename(
            title="Select New Client .exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self._update_file_path = path
            fname = os.path.basename(path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self._update_file_var.set(f"{fname}  ({size_mb:.1f} MB)")

    def _push_update(self):
        if not self._update_file_path or not os.path.isfile(self._update_file_path):
            messagebox.showwarning("No File", "Select the new .exe file first.")
            return
        version = self._update_ver_var.get().strip()
        if not version:
            messagebox.showwarning("No Version", "Enter the version number.")
            return
        changelog = self._update_changelog.get("1.0", "end").strip()

        if not messagebox.askyesno(
                "Confirm Push",
                f"Push update v{version}?\n"
                f"File: {os.path.basename(self._update_file_path)}\n\n"
                f"All clients will download this on next launch."):
            return

        self._push_btn.configure(state="disabled", text="⏳  Pushing...")
        self._push_status.configure(text="Copying & hashing...", fg=ACCENT2)

        def _do():
            try:
                os.makedirs(UPDATES_DIR, exist_ok=True)
                filename = os.path.basename(self._update_file_path)
                dest = os.path.join(UPDATES_DIR, filename)
                shutil.copy2(self._update_file_path, dest)

                # SHA-256 hash
                sha = hashlib.sha256()
                with open(dest, "rb") as fh:
                    for chunk in iter(lambda: fh.read(8192), b""):
                        sha.update(chunk)

                meta = {
                    "version": version,
                    "filename": filename,
                    "sha256": sha.hexdigest(),
                    "changelog": changelog,
                    "date": datetime.now(timezone.utc).isoformat(),
                }
                with open(UPDATE_META, "w") as fh:
                    json.dump(meta, fh, indent=4)

                size_mb = os.path.getsize(dest) / (1024 * 1024)
                self._log(f"Update pushed: v{version} — {filename} ({size_mb:.1f} MB)", "ok")
                self._log(f"SHA-256: {sha.hexdigest()[:32]}...", "dim")

                def _done():
                    self._push_btn.configure(state="normal", text="🚀  Push Update")
                    self._push_status.configure(
                        text=f"v{version} published successfully!", fg=GREEN)
                    self._refresh_update_info()
                self.after(0, _done)

            except Exception as e:
                self._log(f"Push update error: {e}", "err")
                def _err():
                    self._push_btn.configure(state="normal", text="🚀  Push Update")
                    self._push_status.configure(text=f"Error: {e}", fg=ACCENT)
                self.after(0, _err)

        threading.Thread(target=_do, daemon=True).start()

    # ── Activity Log tab (advanced viewer) ───

    def _build_activity_log_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Toolbar ──────────────────────────
        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Action:", font=("Consolas", 9),
                 fg=FG, bg=BG2).pack(side="left")
        self._act_filter_var = tk.StringVar(value="ALL")
        act_menu = ttk.Combobox(toolbar, textvariable=self._act_filter_var,
                                values=["ALL", "check", "search", "status", "list_files",
                                        "download_file", "login", "genkey",
                                        "revokekey", "import"],
                                state="readonly", width=12, font=("Consolas", 9))
        act_menu.pack(side="left", padx=(4, 10))
        act_menu.bind("<<ComboboxSelected>>", lambda e: self._refresh_activity_log())

        tk.Label(toolbar, text="Search:", font=("Consolas", 9),
                 fg=FG, bg=BG2).pack(side="left")
        self._act_search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self._act_search_var, width=16,
                 font=("Consolas", 9), bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).pack(side="left", padx=(4, 10))

        tk.Label(toolbar, text="Limit:", font=("Consolas", 9),
                 fg=FG, bg=BG2).pack(side="left")
        self._act_limit_var = tk.StringVar(value="200")
        ttk.Combobox(toolbar, textvariable=self._act_limit_var,
                     values=["50", "100", "200", "500", "1000"],
                     state="readonly", width=6, font=("Consolas", 9)).pack(
                         side="left", padx=(4, 10))

        tk.Button(toolbar, text="🔄  Refresh", font=("Consolas", 9, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=8,
                  command=self._refresh_activity_log).pack(side="left", padx=(4, 0))

        tk.Button(toolbar, text="💾  Export", font=("Consolas", 9, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=8,
                  command=self._export_activity_log).pack(side="right")

        # ── Count label ──────────────────────
        count_row = tk.Frame(f, bg=BG2)
        count_row.pack(fill="x", pady=(4, 0))
        self._act_count_label = tk.Label(count_row, text="0 entries",
                                         font=("Consolas", 9), fg=DIM, bg=BG2)
        self._act_count_label.pack(side="left")

        # ── Treeview ─────────────────────────
        cols = ("time", "user", "action", "detail", "ip", "ms")
        self._act_tree = ttk.Treeview(f, columns=cols, show="headings", height=16)
        self._act_tree.heading("time", text="Time")
        self._act_tree.heading("user", text="User / Key")
        self._act_tree.heading("action", text="Action")
        self._act_tree.heading("detail", text="Detail")
        self._act_tree.heading("ip", text="IP")
        self._act_tree.heading("ms", text="ms")
        self._act_tree.column("time", width=140, anchor="center")
        self._act_tree.column("user", width=130)
        self._act_tree.column("action", width=90, anchor="center")
        self._act_tree.column("detail", width=290)
        self._act_tree.column("ip", width=110, anchor="center")
        self._act_tree.column("ms", width=60, anchor="e")

        self._act_tree.tag_configure("check", foreground=ACCENT2)
        self._act_tree.tag_configure("download_file", foreground=GREEN)
        self._act_tree.tag_configure("genkey", foreground=YELLOW)
        self._act_tree.tag_configure("revokekey", foreground=ACCENT)
        self._act_tree.tag_configure("import", foreground=GREEN)

        act_scroll = tk.Scrollbar(f, command=self._act_tree.yview)
        self._act_tree.configure(yscrollcommand=act_scroll.set)
        self._act_tree.pack(fill="both", expand=True, pady=(6, 0), side="left")
        act_scroll.pack(fill="y", side="right", pady=(6, 0))

        self._refresh_activity_log()

    def _refresh_activity_log(self):
        """Fetch activity logs from DB and display in treeview."""
        for item in self._act_tree.get_children():
            self._act_tree.delete(item)

        limit = int(self._act_limit_var.get())
        rows = get_recent_activity(limit)

        action_filter = self._act_filter_var.get()
        search = self._act_search_var.get().lower().strip()

        from auth import get_key_username as _get_username
        count = 0
        for r in rows:
            action = r.get("action", "")
            if action_filter != "ALL" and action != action_filter:
                continue
            detail = r.get("detail", "")
            ip = r.get("ip", "")
            user_key = r.get("user_key", "")

            # Resolve username
            if user_key == CONFIG.get("admin_key"):
                username = "ADMIN"
            else:
                try:
                    username = _get_username(user_key) or user_key[:16] + "..."
                except Exception:
                    username = user_key[:16] + "..."

            if search and search not in detail.lower() and search not in username.lower() \
                    and search not in action.lower() and search not in ip.lower():
                continue

            ts = r.get("timestamp", 0)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            ms = r.get("duration_ms", 0)
            ms_str = f"{ms:.0f}" if ms else ""

            tag = action if action in ("check", "download_file", "genkey", "revokekey", "import") else ""
            self._act_tree.insert("", "end",
                                  values=(time_str, username, action, detail, ip, ms_str),
                                  tags=(tag,))
            count += 1

        self._act_count_label.configure(text=f"{count} entries")

    def _export_activity_log(self):
        """Export activity log to file."""
        path = filedialog.asksaveasfilename(
            title="Export Activity Log", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")])
        if not path:
            return
        rows = []
        for item in self._act_tree.get_children():
            vals = self._act_tree.item(item)["values"]
            rows.append(vals)

        with open(path, "w", encoding="utf-8") as f:
            f.write("Time,User,Action,Detail,IP,Duration_ms\n")
            for v in rows:
                line = ",".join(str(x).replace(",", ";") for x in v)
                f.write(line + "\n")
        self._log(f"Activity log exported: {os.path.basename(path)} ({len(rows)} rows)", "ok")

    # ── Messages tab (send to clients) ───────

    def _build_messages_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(f, text="Server Messages — Broadcast to Clients",
                 font=("Consolas", 12, "bold"), fg=ACCENT2, bg=BG2).pack(anchor="w")
        tk.Label(f, text="Messages appear as banners in the client app on connect.",
                 font=("Consolas", 9), fg=DIM, bg=BG2).pack(anchor="w", pady=(2, 10))

        # ── Compose area ─────────────────────
        compose = tk.Frame(f, bg=BG3, padx=12, pady=10)
        compose.pack(fill="x")

        tk.Label(compose, text="New Message", font=("Consolas", 10, "bold"),
                 fg=ACCENT2, bg=BG3).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        tk.Label(compose, text="Text:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=1, column=0, sticky="w")
        self._msg_text_var = tk.StringVar()
        tk.Entry(compose, textvariable=self._msg_text_var, width=50,
                 font=("Consolas", 9), bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", bd=4).grid(
                     row=1, column=1, padx=(6, 10), sticky="ew")

        tk.Label(compose, text="Level:", font=("Consolas", 9),
                 fg=FG, bg=BG3).grid(row=1, column=2, sticky="w")
        self._msg_level_var = tk.StringVar(value="info")
        ttk.Combobox(compose, textvariable=self._msg_level_var,
                     values=["info", "warning", "urgent", "success"],
                     state="readonly", width=10, font=("Consolas", 9)).grid(
                         row=1, column=3, padx=(4, 0))

        compose.columnconfigure(1, weight=1)

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill="x", pady=(8, 0))

        tk.Button(btn_row, text="📢  Send Message", font=("Consolas", 10, "bold"),
                  bg=GREEN, fg="#000", relief="flat", padx=12, pady=3,
                  command=self._send_message).pack(side="left")
        tk.Button(btn_row, text="🗑  Delete Selected", font=("Consolas", 10, "bold"),
                  bg=ACCENT, fg="white", relief="flat", padx=12, pady=3,
                  command=self._delete_message).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text="🔄  Refresh", font=("Consolas", 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=3,
                  command=self._refresh_messages).pack(side="left", padx=(8, 0))

        # ── Messages list ────────────────────
        cols = ("id", "text", "level", "date", "active")
        self._msg_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        self._msg_tree.heading("id", text="#")
        self._msg_tree.heading("text", text="Message")
        self._msg_tree.heading("level", text="Level")
        self._msg_tree.heading("date", text="Date")
        self._msg_tree.heading("active", text="Active")
        self._msg_tree.column("id", width=40, anchor="center")
        self._msg_tree.column("text", width=420)
        self._msg_tree.column("level", width=80, anchor="center")
        self._msg_tree.column("date", width=140, anchor="center")
        self._msg_tree.column("active", width=60, anchor="center")

        self._msg_tree.tag_configure("info", foreground=ACCENT2)
        self._msg_tree.tag_configure("warning", foreground=YELLOW)
        self._msg_tree.tag_configure("urgent", foreground=ACCENT)
        self._msg_tree.tag_configure("success", foreground=GREEN)
        self._msg_tree.tag_configure("inactive", foreground=DIM)

        msg_scroll = tk.Scrollbar(f, command=self._msg_tree.yview)
        self._msg_tree.configure(yscrollcommand=msg_scroll.set)
        self._msg_tree.pack(fill="both", expand=True, pady=(8, 0), side="left")
        msg_scroll.pack(fill="y", side="right", pady=(8, 0))

        self._refresh_messages()

    def _load_messages(self) -> list[dict]:
        """Load messages from messages.json."""
        if not os.path.isfile(MESSAGES_FILE):
            return []
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_messages(self, msgs: list[dict]):
        """Save messages to messages.json."""
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(msgs, f, indent=2, ensure_ascii=False)

    def _refresh_messages(self):
        for item in self._msg_tree.get_children():
            self._msg_tree.delete(item)
        msgs = self._load_messages()
        for i, m in enumerate(msgs):
            active = "✅" if m.get("active", True) else "❌"
            level = m.get("level", "info")
            tag = level if m.get("active", True) else "inactive"
            self._msg_tree.insert("", "end",
                                  values=(i + 1, m.get("text", ""), level,
                                          m.get("date", ""), active),
                                  tags=(tag,))

    def _send_message(self):
        text = self._msg_text_var.get().strip()
        if not text:
            messagebox.showwarning("Empty", "Enter a message text.")
            return

        level = self._msg_level_var.get()
        msg = {
            "text": text,
            "level": level,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active": True,
        }
        msgs = self._load_messages()
        msgs.insert(0, msg)
        self._save_messages(msgs)
        self._msg_text_var.set("")
        self._refresh_messages()
        self._log(f"Message sent: [{level}] {text}", "ok")

    def _delete_message(self):
        sel = self._msg_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a message to delete.")
            return
        item = self._msg_tree.item(sel[0])
        idx = int(item["values"][0]) - 1  # 0-based
        msgs = self._load_messages()
        if 0 <= idx < len(msgs):
            removed = msgs.pop(idx)
            self._save_messages(msgs)
            self._log(f"Deleted message: {removed.get('text', '')[:40]}...", "err")
            self._refresh_messages()

    # ── Log tab (server internal log) ────────

    def _build_log_tab(self, parent):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="both", expand=True)

        self.log_text = tk.Text(f, bg=BG2, fg=FG, font=("Consolas", 9),
                                relief="flat", bd=8, state="disabled",
                                insertbackground=FG, selectbackground="#333355",
                                wrap="word")
        scroll = tk.Scrollbar(f, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_configure("info", foreground=ACCENT2)
        self.log_text.tag_configure("ok", foreground=GREEN)
        self.log_text.tag_configure("err", foreground=ACCENT)
        self.log_text.tag_configure("dim", foreground=DIM)

        self._log("LEAKCHECK Server Admin Panel loaded.", "info")
        self._log(f"Admin key: {CONFIG['admin_key'][:16]}...", "dim")
        self._log(f"Database: {CONFIG['db_path']}", "dim")

    # ── Server start / stop ──────────────────

    def _start_server(self):
        if self._server_running:
            return

        from server import create_app
        self._flask_app = create_app()

        def _run():
            # Route all Python logging messages to the GUI log panel
            gui_handler = _GUILogHandler(self)
            gui_handler.setLevel(logging.INFO)
            gui_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(gui_handler)

            # Suppress noisy Werkzeug default request logs (we have our own after_request)
            log = logging.getLogger("werkzeug")
            log.setLevel(logging.WARNING)
            try:
                self._flask_app.run(
                    host="0.0.0.0",
                    port=CONFIG.get("port", 5000),
                    debug=False,
                    use_reloader=False,
                )
            except Exception as e:
                self.after(0, lambda: self._log(f"Server error: {e}", "err"))
            finally:
                self.after(0, self._on_server_stopped)

        self._flask_thread = threading.Thread(target=_run, daemon=True)
        self._flask_thread.start()
        self._server_running = True

        # Start Binance deposit polling
        start_payment_monitor()

        self.status_dot.configure(fg=GREEN)
        self.status_label.configure(text="running", fg=GREEN)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log(f"Server started on 0.0.0.0:{CONFIG.get('port', 5000)}", "ok")

    def _stop_server(self):
        if not self._server_running:
            return
        self._log("Stopping server...", "info")
        # Send shutdown to Werkzeug (include admin key for auth)
        try:
            import requests as req
            req.post(f"http://127.0.0.1:{CONFIG.get('port', 5000)}/shutdown",
                     headers={"X-API-Key": CONFIG["admin_key"]},
                     timeout=2)
        except Exception:
            pass
        self._on_server_stopped()

    def _on_server_stopped(self):
        self._server_running = False
        stop_payment_monitor()
        try:
            from telegram_bot import stop_telegram_bot
            stop_telegram_bot()
        except Exception:
            pass
        self.status_dot.configure(fg=DIM)
        self.status_label.configure(text="stopped", fg=DIM)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("Server stopped.", "err")

    # ── Close ────────────────────────────────

    def _on_close(self):
        if self._server_running:
            if not messagebox.askyesno("Quit", "Server is running. Stop and quit?"):
                return
            self._stop_server()
        self.destroy()


# ── Entry point ──────────────────────────────
if __name__ == "__main__":
    app = ServerApp()
    app.mainloop()
