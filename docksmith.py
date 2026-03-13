import tkinter as tk
from tkinter import font as tkfont
import subprocess
import threading
import os
import sys
import shlex
from datetime import datetime

# ─── Color Palette ────────────────────────────────────────────────────────────
BG_DEEP     = "#0a0c0f"
BG_PANEL    = "#0f1318"
BG_INPUT    = "#13181f"
ACCENT      = "#00ff9d"
ACCENT_DIM  = "#00b36b"
ACCENT_GLOW = "#00ff9d22"
MUTED       = "#3a4450"
TEXT_MAIN   = "#c8d6e5"
TEXT_DIM    = "#5a6a7a"
TEXT_WARN   = "#ffa040"
TEXT_ERROR  = "#ff4f6a"
TEXT_INFO   = "#4fc3f7"
CURSOR_CLR  = "#00ff9d"

CWD = [os.path.expanduser("~")]

class TerminalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TERMINAL")
        self.root.configure(bg=BG_DEEP)
        self.root.geometry("900x620")
        self.root.minsize(600, 400)

        self.history = []
        self.hist_idx = -1
        self.current_input_snapshot = ""

        self._load_fonts()
        self._build_title_bar()
        self._build_output_area()
        self._build_input_bar()
        self._build_status_bar()

        self._print_banner()
        self.cmd_entry.focus_set()

        self.root.bind("<Configure>", lambda e: None)

    # ─── Font Loading ─────────────────────────────────────────────────────────
    def _load_fonts(self):
        self.mono_lg  = tkfont.Font(family="Courier New", size=13, weight="bold")
        self.mono_md  = tkfont.Font(family="Courier New", size=11)
        self.mono_sm  = tkfont.Font(family="Courier New", size=9)
        self.sans_sm  = tkfont.Font(family="Helvetica",   size=9)
        self.sans_md  = tkfont.Font(family="Helvetica",   size=10, weight="bold")

    # ─── Title Bar ────────────────────────────────────────────────────────────
    def _build_title_bar(self):
        bar = tk.Frame(self.root, bg=BG_PANEL, height=36)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # Traffic-light dots
        dot_frame = tk.Frame(bar, bg=BG_PANEL)
        dot_frame.pack(side="left", padx=14, pady=10)
        for color in ("#ff5f57", "#febc2e", "#28c840"):
            c = tk.Canvas(dot_frame, width=12, height=12, bg=BG_PANEL,
                          highlightthickness=0)
            c.pack(side="left", padx=3)
            c.create_oval(1, 1, 11, 11, fill=color, outline="")

        # Title
        tk.Label(bar, text="⬡  TERMINAL", font=self.sans_md,
                 bg=BG_PANEL, fg=ACCENT).pack(side="left", padx=8)

        # Clock
        self.clock_var = tk.StringVar()
        tk.Label(bar, textvariable=self.clock_var, font=self.mono_sm,
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="right", padx=16)
        self._tick_clock()

        # Separator line
        sep = tk.Frame(self.root, bg=MUTED, height=1)
        sep.pack(fill="x", side="top")

    def _tick_clock(self):
        self.clock_var.set(datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    # ─── Output Area ─────────────────────────────────────────────────────────
    def _build_output_area(self):
        frame = tk.Frame(self.root, bg=BG_DEEP)
        frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.output = tk.Text(
            frame,
            bg=BG_DEEP, fg=TEXT_MAIN,
            font=self.mono_md,
            insertbackground=CURSOR_CLR,
            selectbackground=MUTED,
            selectforeground=TEXT_MAIN,
            relief="flat", bd=0,
            padx=16, pady=12,
            wrap="word",
            state="disabled",
            cursor="arrow",
        )
        self.output.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(frame, orient="vertical",
                          command=self.output.yview,
                          bg=BG_PANEL, troughcolor=BG_DEEP,
                          activebackground=ACCENT_DIM, width=8,
                          relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=sb.set)

        # Tag styles
        self.output.tag_config("prompt",   foreground=ACCENT,      font=self.mono_md)
        self.output.tag_config("cmd",      foreground=TEXT_MAIN,   font=self.mono_md)
        self.output.tag_config("stdout",   foreground=TEXT_MAIN,   font=self.mono_md)
        self.output.tag_config("stderr",   foreground=TEXT_ERROR,  font=self.mono_md)
        self.output.tag_config("info",     foreground=TEXT_INFO,   font=self.mono_md)
        self.output.tag_config("warn",     foreground=TEXT_WARN,   font=self.mono_md)
        self.output.tag_config("accent",   foreground=ACCENT,      font=self.mono_md)
        self.output.tag_config("dim",      foreground=TEXT_DIM,    font=self.mono_sm)
        self.output.tag_config("banner",   foreground=ACCENT,      font=self.mono_lg)

    # ─── Input Bar ───────────────────────────────────────────────────────────
    def _build_input_bar(self):
        sep = tk.Frame(self.root, bg=MUTED, height=1)
        sep.pack(fill="x")

        self.input_frame = tk.Frame(self.root, bg=BG_INPUT, height=44)
        self.input_frame.pack(fill="x", side="bottom")
        self.input_frame.pack_propagate(False)

        # Prompt label (updates with cwd)
        self.prompt_var = tk.StringVar()
        self._refresh_prompt()
        self.prompt_lbl = tk.Label(
            self.input_frame, textvariable=self.prompt_var,
            font=self.mono_md, bg=BG_INPUT, fg=ACCENT,
            padx=12, pady=0
        )
        self.prompt_lbl.pack(side="left")

        # Caret symbol
        tk.Label(self.input_frame, text="❯", font=self.mono_md,
                 bg=BG_INPUT, fg=ACCENT_DIM).pack(side="left")

        self.cmd_entry = tk.Entry(
            self.input_frame,
            bg=BG_INPUT, fg=TEXT_MAIN,
            insertbackground=CURSOR_CLR,
            selectbackground=MUTED,
            font=self.mono_md,
            relief="flat", bd=0,
        )
        self.cmd_entry.pack(side="left", fill="both", expand=True, padx=8)
        self.cmd_entry.bind("<Return>",   self._on_enter)
        self.cmd_entry.bind("<Up>",       self._history_up)
        self.cmd_entry.bind("<Down>",     self._history_down)
        self.cmd_entry.bind("<Tab>",      self._tab_complete)
        self.cmd_entry.bind("<Control-l>",self._clear_screen)
        self.cmd_entry.bind("<Control-c>", self._ctrl_c)

    # ─── Status Bar ──────────────────────────────────────────────────────────
    def _build_status_bar(self):
        self.status_frame = tk.Frame(self.root, bg=ACCENT, height=20)
        self.status_frame.pack(fill="x", side="bottom")
        self.status_frame.pack_propagate(False)

        self.status_var = tk.StringVar(value=" READY")
        tk.Label(self.status_frame, textvariable=self.status_var,
                 font=self.sans_sm, bg=ACCENT, fg=BG_DEEP,
                 anchor="w").pack(side="left", padx=8)

        self.exit_var = tk.StringVar(value="EXIT 0")
        tk.Label(self.status_frame, textvariable=self.exit_var,
                 font=self.sans_sm, bg=ACCENT, fg=BG_DEEP,
                 anchor="e").pack(side="right", padx=8)

    # ─── Banner ──────────────────────────────────────────────────────────────
    def _print_banner(self):
        banner = (
            "╔══════════════════════════════════════════╗\n"
            "║          T E R M I N A L  v1.0           ║\n"
            "╚══════════════════════════════════════════╝"
        )
        self._append(banner + "\n", "banner")
        self._append(f"  Python {sys.version.split()[0]}  •  {sys.platform}\n", "dim")
        self._append(f"  {datetime.now().strftime('%A, %d %B %Y')}\n\n", "dim")
        self._append("  Type a command and press Enter. Ctrl+L to clear.\n\n", "info")

    # ─── Helpers ─────────────────────────────────────────────────────────────
    def _refresh_prompt(self):
        cwd = CWD[0]
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        short = cwd if len(cwd) < 36 else "…" + cwd[-33:]
        self.prompt_var.set(f" {short} ")

    def _append(self, text, tag="stdout"):
        self.output.configure(state="normal")
        self.output.insert("end", text, tag)
        self.output.configure(state="disabled")
        self.output.see("end")

    def _set_status(self, text, color=ACCENT):
        self.status_var.set(f" {text}")
        self.status_frame.configure(bg=color)
        for w in self.status_frame.winfo_children():
            w.configure(bg=color)

    # ─── Command Execution ───────────────────────────────────────────────────
    def _on_enter(self, event=None):
        raw = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, "end")
        if not raw:
            return

        self.history.append(raw)
        self.hist_idx = -1

        # Echo prompt + command
        self._append(self.prompt_var.get(), "prompt")
        self._append("❯ ", "accent")
        self._append(raw + "\n", "cmd")

        # Built-ins
        if self._handle_builtin(raw):
            return

        # External command
        self._set_status("RUNNING …", BG_PANEL)
        t = threading.Thread(target=self._run_external, args=(raw,), daemon=True)
        t.start()

    def _handle_builtin(self, raw):
        parts = shlex.split(raw) if raw else []
        cmd = parts[0].lower() if parts else ""

        if cmd in ("exit", "quit"):
            self.root.destroy()
            return True

        if cmd == "clear":
            self._clear_screen()
            return True

        if cmd == "cd":
            target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            target = os.path.expandvars(os.path.expanduser(target))
            if not os.path.isabs(target):
                target = os.path.join(CWD[0], target)
            target = os.path.normpath(target)
            if os.path.isdir(target):
                CWD[0] = target
                self._refresh_prompt()
                self._set_status("READY")
                self._set_exit(0)
            else:
                self._append(f"cd: no such directory: {target}\n", "stderr")
                self._set_status("ERROR", TEXT_ERROR)
                self._set_exit(1)
            self._append("\n")
            return True

        if cmd == "help":
            self._append(
                "  Built-ins: cd, clear, exit, quit, help\n"
                "  All other commands are passed to the system shell.\n"
                "  Keyboard shortcuts:\n"
                "    ↑ / ↓        history navigation\n"
                "    Tab          path completion\n"
                "    Ctrl+L       clear screen\n"
                "    Ctrl+C       interrupt\n\n",
                "info"
            )
            self._set_status("READY")
            return True

        return False

    def _run_external(self, raw):
        try:
            proc = subprocess.Popen(
                raw, shell=True,
                cwd=CWD[0],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=30)
            rc = proc.returncode

            if stdout:
                self.root.after(0, self._append, stdout, "stdout")
            if stderr:
                self.root.after(0, self._append, stderr, "stderr")
            self.root.after(0, self._append, "\n")
            self.root.after(0, self._set_exit, rc)
            color = ACCENT if rc == 0 else TEXT_ERROR
            label = "READY" if rc == 0 else f"EXITED {rc}"
            self.root.after(0, self._set_status, label, color if rc != 0 else ACCENT)

        except subprocess.TimeoutExpired:
            proc.kill()
            self.root.after(0, self._append, "  [process timed out after 30 s]\n", "warn")
            self.root.after(0, self._set_status, "TIMEOUT", TEXT_WARN)
        except Exception as e:
            self.root.after(0, self._append, f"  [error: {e}]\n", "stderr")
            self.root.after(0, self._set_status, "ERROR", TEXT_ERROR)

    def _set_exit(self, code):
        self.exit_var.set(f"EXIT {code}  ")

    # ─── Keyboard Features ───────────────────────────────────────────────────
    def _history_up(self, event=None):
        if not self.history:
            return "break"
        if self.hist_idx == -1:
            self.current_input_snapshot = self.cmd_entry.get()
            self.hist_idx = len(self.history) - 1
        elif self.hist_idx > 0:
            self.hist_idx -= 1
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.history[self.hist_idx])
        return "break"

    def _history_down(self, event=None):
        if self.hist_idx == -1:
            return "break"
        if self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, self.history[self.hist_idx])
        else:
            self.hist_idx = -1
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, self.current_input_snapshot)
        return "break"

    def _tab_complete(self, event=None):
        partial = self.cmd_entry.get()
        parts   = partial.split()
        if not parts:
            return "break"
        # Complete last token as path
        token = parts[-1] if partial.endswith(parts[-1]) else ""
        base  = os.path.join(CWD[0], token)
        parent, prefix = os.path.dirname(base), os.path.basename(base)
        if not parent:
            parent = CWD[0]
        try:
            matches = [n for n in os.listdir(parent) if n.startswith(prefix)]
        except Exception:
            return "break"
        if len(matches) == 1:
            completed = os.path.join(parent, matches[0])
            if os.path.isdir(completed):
                completed += os.sep
            # replace last token
            rest = partial[: len(partial) - len(token)]
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, rest + (os.path.join(token[: token.rfind(os.sep) + 1] if os.sep in token else "", matches[0]) + (os.sep if os.path.isdir(completed) else "")))
        elif len(matches) > 1:
            self._append("  " + "  ".join(matches) + "\n", "dim")
        return "break"

    def _clear_screen(self, event=None):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._set_status("READY")
        return "break"

    def _ctrl_c(self, event=None):
        self.cmd_entry.delete(0, "end")
        self._append("^C\n", "warn")
        return "break"


if __name__ == "__main__":
    root = tk.Tk()
    app  = TerminalApp(root)
    root.mainloop()
