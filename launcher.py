"""
Game Launcher
- Logins: Firebase Authentication (email + password)
- Game list + downloads: games.json and zip files hosted on GitHub

Setup: fill in the three settings below, then run:  python launcher.py
Needs only standard Python (tkinter is included with Python).
"""

import json
import os
import sys
import shutil
import zipfile
import threading
import subprocess
import webbrowser
import pathlib
import urllib.request
import urllib.parse
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

# ===================== SETTINGS - EDIT THESE =====================
FIREBASE_API_KEY = "AIzaSyCI-Nq4YE-NNUUaV3PtsSzqlZYyG_7Nl9U"
GAMES_LIST_URL = "https://raw.githubusercontent.com/joseschmoe/bomboclart/workspaces/bomboclart/games.json"
LAUNCHER_NAME = "hi"
# =================================================================

BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
GAMES_DIR = os.path.join(BASE_DIR, "games")
INSTALLED_FILE = os.path.join(BASE_DIR, "installed.json")
SESSION_FILE = os.path.join(BASE_DIR, "session.json")

BG = "#1e1f26"
PANEL = "#2a2c36"
TEXT = "#f0f0f0"
MUTED = "#9a9cab"
ACCENT = "#4f8cff"

ERROR_MESSAGES = {
    "EMAIL_EXISTS": "An account with that email already exists.",
    "INVALID_EMAIL": "That email address isn't valid.",
    "EMAIL_NOT_FOUND": "Wrong email or password.",
    "INVALID_PASSWORD": "Wrong email or password.",
    "INVALID_LOGIN_CREDENTIALS": "Wrong email or password.",
    "USER_DISABLED": "This account has been disabled.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Try again later.",
    "MISSING_PASSWORD": "Please enter a password.",
}


# ----------------------------- helpers -----------------------------

def friendly_error(code):
    for key, text in ERROR_MESSAGES.items():
        if code.startswith(key):
            return text
    if code.startswith("WEAK_PASSWORD"):
        return "Password must be at least 6 characters."
    return code


def http_post(url, body, form=False):
    if form:
        data = urllib.parse.urlencode(body).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            code = json.load(e)["error"]["message"]
        except Exception:
            code = f"Server error ({e.code})"
        raise Exception(friendly_error(code))
    except urllib.error.URLError:
        raise Exception("Can't connect. Check your internet connection.")


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "GameLauncher", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ----------------------------- Firebase auth -----------------------------

def firebase_sign_up(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    return http_post(url, {"email": email, "password": password, "returnSecureToken": True})


def firebase_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    return http_post(url, {"email": email, "password": password, "returnSecureToken": True})


def firebase_refresh(refresh_token):
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    return http_post(url, {"grant_type": "refresh_token", "refresh_token": refresh_token}, form=True)


def firebase_reset_password(email):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
    return http_post(url, {"requestType": "PASSWORD_RESET", "email": email})


# ----------------------------- App -----------------------------

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(LAUNCHER_NAME)
        self.geometry("720x520")
        self.minsize(560, 420)
        self.configure(bg=BG)

        os.makedirs(GAMES_DIR, exist_ok=True)
        self.installed = load_json(INSTALLED_FILE, {})
        self.games = []
        self.user_email = None
        self.busy = False

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=PANEL)

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)

        self.try_auto_login()

    # ---------- screen switching ----------
    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def button(self, parent, text, command, color=ACCENT, width=None):
        b = tk.Button(parent, text=text, command=command, bg=color, fg="white",
                      activebackground=color, activeforeground="white",
                      relief="flat", font=("Segoe UI", 10, "bold"), padx=12, pady=5,
                      cursor="hand2", bd=0)
        if width:
            b.config(width=width)
        return b

    # ---------- login ----------
    def try_auto_login(self):
        session = load_json(SESSION_FILE, None)
        if not session or "refresh_token" not in session:
            self.show_login()
            return

        def work():
            try:
                data = firebase_refresh(session["refresh_token"])
                session["refresh_token"] = data["refresh_token"]
                save_json(SESSION_FILE, session)
                self.after(0, lambda: self.login_success(session.get("email", "Player")))
            except Exception:
                self.after(0, self.show_login)

        self.clear()
        tk.Label(self.container, text="Signing in...", bg=BG, fg=MUTED,
                 font=("Segoe UI", 12)).pack(expand=True)
        threading.Thread(target=work, daemon=True).start()

    def show_login(self):
        self.clear()
        box = tk.Frame(self.container, bg=PANEL, padx=30, pady=25)
        box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(box, text=LAUNCHER_NAME, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(pady=(0, 15))

        tk.Label(box, text="Email", bg=PANEL, fg=MUTED, anchor="w").pack(fill="x")
        email = tk.Entry(box, width=32, font=("Segoe UI", 11), bg=BG, fg=TEXT,
                         insertbackground=TEXT, relief="flat")
        email.pack(pady=(0, 10), ipady=4)

        tk.Label(box, text="Password", bg=PANEL, fg=MUTED, anchor="w").pack(fill="x")
        password = tk.Entry(box, width=32, show="*", font=("Segoe UI", 11), bg=BG, fg=TEXT,
                            insertbackground=TEXT, relief="flat")
        password.pack(pady=(0, 10), ipady=4)

        remember = tk.BooleanVar(value=True)
        tk.Checkbutton(box, text="Remember me", variable=remember, bg=PANEL, fg=MUTED,
                       selectcolor=BG, activebackground=PANEL, activeforeground=TEXT).pack(anchor="w")

        status = tk.Label(box, text="", bg=PANEL, fg="#ff6b6b", wraplength=260)
        status.pack(pady=5)

        def do_auth(mode):
            e, p = email.get().strip(), password.get()
            if not e or not p:
                status.config(text="Enter your email and password.")
                return
            status.config(text="Please wait...", fg=MUTED)

            def work():
                try:
                    data = firebase_sign_up(e, p) if mode == "signup" else firebase_sign_in(e, p)
                    if remember.get():
                        save_json(SESSION_FILE, {"email": e, "refresh_token": data["refreshToken"]})
                    self.after(0, lambda: self.login_success(e))
                except Exception as ex:
                    msg = str(ex)
                    self.after(0, lambda: status.config(text=msg, fg="#ff6b6b"))

            threading.Thread(target=work, daemon=True).start()

        def do_reset():
            e = email.get().strip()
            if not e:
                status.config(text="Type your email first, then click Forgot password.", fg="#ff6b6b")
                return

            def work():
                try:
                    firebase_reset_password(e)
                    self.after(0, lambda: status.config(text="Password reset email sent.", fg="#6bff9a"))
                except Exception as ex:
                    msg = str(ex)
                    self.after(0, lambda: status.config(text=msg, fg="#ff6b6b"))

            threading.Thread(target=work, daemon=True).start()

        row = tk.Frame(box, bg=PANEL)
        row.pack(pady=(5, 5))
        self.button(row, "Log in", lambda: do_auth("login"), width=10).pack(side="left", padx=4)
        self.button(row, "Sign up", lambda: do_auth("signup"), color="#555a6e", width=10).pack(side="left", padx=4)

        tk.Button(box, text="Forgot password?", command=do_reset, bg=PANEL, fg=MUTED,
                  relief="flat", activebackground=PANEL, cursor="hand2", bd=0).pack()

        password.bind("<Return>", lambda _: do_auth("login"))
        email.focus()

    def login_success(self, email):
        self.user_email = email
        self.show_library()

    def logout(self):
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        self.user_email = None
        self.show_login()

    # ---------- library ----------
    def show_library(self):
        self.clear()

        top = tk.Frame(self.container, bg=PANEL, padx=15, pady=10)
        top.pack(fill="x")
        tk.Label(top, text=LAUNCHER_NAME, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.button(top, "Log out", self.logout, color="#555a6e").pack(side="right")
        self.button(top, "Refresh", self.load_games, color="#555a6e").pack(side="right", padx=6)
        tk.Label(top, text=self.user_email, bg=PANEL, fg=MUTED).pack(side="right", padx=10)

        # scrollable game list
        outer = tk.Frame(self.container, bg=BG)
        outer.pack(fill="both", expand=True, padx=15, pady=10)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=BG)
        self.list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        bottom = tk.Frame(self.container, bg=BG, padx=15, pady=10)
        bottom.pack(fill="x")
        self.status = tk.Label(bottom, text="", bg=BG, fg=MUTED, anchor="w")
        self.status.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(4, 0))

        self.load_games()

    def load_games(self):
        self.status.config(text="Loading games...")

        def work():
            try:
                data = http_get_json(GAMES_LIST_URL)
                games = data.get("games", [])
                self.after(0, lambda: self.set_games(games, None))
            except Exception as ex:
                msg = str(ex)
                self.after(0, lambda: self.set_games([], msg))

        threading.Thread(target=work, daemon=True).start()

    def set_games(self, games, error):
        self.games = games
        if error:
            self.status.config(text=f"Couldn't load the game list: {error}. Showing installed games.")
            # fall back to whatever is installed locally so you can still play offline
            self.games = [dict(info, id=gid) for gid, info in self.installed.items()]
        else:
            self.status.config(text=f"{len(games)} game(s) available.")
        self.render_games()

    def render_games(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        if not self.games:
            tk.Label(self.list_frame, text="No games yet.", bg=BG, fg=MUTED,
                     font=("Segoe UI", 11)).pack(pady=20)
            return

        for game in self.games:
            gid = game["id"]
            card = tk.Frame(self.list_frame, bg=PANEL, padx=15, pady=12)
            card.pack(fill="x", pady=5)

            info = tk.Frame(card, bg=PANEL)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=game.get("name", gid), bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
            if game.get("description"):
                tk.Label(info, text=game["description"], bg=PANEL, fg=MUTED, anchor="w",
                         wraplength=380, justify="left").pack(fill="x")

            local = self.installed.get(gid)
            latest = game.get("version", "?")
            if local:
                ver_text = f"Installed v{local['version']}"
                if game.get("url") and local["version"] != latest:
                    ver_text += f"  -  update available (v{latest})"
            else:
                ver_text = f"v{latest}  -  not installed"
            tk.Label(info, text=ver_text, bg=PANEL, fg=MUTED, anchor="w",
                     font=("Segoe UI", 9)).pack(fill="x")

            btns = tk.Frame(card, bg=PANEL)
            btns.pack(side="right")
            if local:
                if game.get("url") and local["version"] != latest:
                    self.button(btns, "Update", lambda g=game: self.install(g), color="#e0a030").pack(side="left", padx=3)
                self.button(btns, "Play", lambda g=game: self.play(g), color="#2fa84f").pack(side="left", padx=3)
                self.button(btns, "Uninstall", lambda g=game: self.uninstall(g), color="#555a6e").pack(side="left", padx=3)
            else:
                self.button(btns, "Install", lambda g=game: self.install(g)).pack(side="left", padx=3)

    # ---------- install / play / uninstall ----------
    def install(self, game):
        if self.busy:
            messagebox.showinfo(LAUNCHER_NAME, "Wait for the current download to finish.")
            return
        self.busy = True
        gid = game["id"]
        name = game.get("name", gid)
        target = os.path.join(GAMES_DIR, gid)
        zip_path = os.path.join(GAMES_DIR, gid + ".download.zip")
        temp_dir = os.path.join(GAMES_DIR, gid + ".extracting")

        def set_progress(pct, text):
            self.progress["value"] = pct
            self.status.config(text=text)

        def work():
            try:
                req = urllib.request.Request(game["url"], headers={"User-Agent": "GameLauncher"})
                with urllib.request.urlopen(req, timeout=30) as r, open(zip_path, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        chunk = r.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        mb = done / 1048576
                        if total:
                            pct = done * 100 / total
                            self.after(0, lambda p=pct, m=mb: set_progress(p, f"Downloading {name}... {m:.1f} MB ({p:.0f}%)"))
                        else:
                            self.after(0, lambda m=mb: set_progress(0, f"Downloading {name}... {m:.1f} MB"))

                self.after(0, lambda: set_progress(100, f"Installing {name}..."))

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(temp_dir)

                # if the zip contains a single folder, use the inside of that folder
                entries = os.listdir(temp_dir)
                source = temp_dir
                if len(entries) == 1 and os.path.isdir(os.path.join(temp_dir, entries[0])):
                    source = os.path.join(temp_dir, entries[0])

                if os.path.exists(target):
                    shutil.rmtree(target)
                shutil.move(source, target)

                self.installed[gid] = {
                    "name": name,
                    "version": game.get("version", "?"),
                    "run": game.get("run", ""),
                    "description": game.get("description", ""),
                }
                save_json(INSTALLED_FILE, self.installed)
                self.after(0, lambda: set_progress(0, f"{name} installed."))
            except Exception as ex:
                msg = str(ex)
                self.after(0, lambda: set_progress(0, f"Install failed: {msg}"))
            finally:
                for p in (zip_path,):
                    if os.path.exists(p):
                        os.remove(p)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                self.busy = False
                self.after(0, self.render_games)

        threading.Thread(target=work, daemon=True).start()

    def play(self, game):
        gid = game["id"]
        local = self.installed.get(gid, {})
        run = game.get("run") or local.get("run")
        folder = os.path.join(GAMES_DIR, gid)
        path = os.path.join(folder, run) if run else ""

        if not run or not os.path.exists(path):
            messagebox.showerror(LAUNCHER_NAME, f"Can't find the file to run:\n{path or '(no run file set)'}\n\nCheck the \"run\" value in games.json.")
            return

        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".html", ".htm"):
                webbrowser.open(pathlib.Path(path).as_uri())
            elif ext == ".py":
                subprocess.Popen([sys.executable, path], cwd=os.path.dirname(path))
            elif ext == ".jar":
                subprocess.Popen(["java", "-jar", path], cwd=os.path.dirname(path))
            elif sys.platform.startswith("win"):
                os.startfile(path)
            else:
                subprocess.Popen([path], cwd=os.path.dirname(path))
            self.status.config(text=f"Launched {game.get('name', gid)}.")
        except Exception as ex:
            messagebox.showerror(LAUNCHER_NAME, f"Couldn't start the game:\n{ex}")

    def uninstall(self, game):
        gid = game["id"]
        name = game.get("name", gid)
        if not messagebox.askyesno(LAUNCHER_NAME, f"Uninstall {name}?"):
            return
        shutil.rmtree(os.path.join(GAMES_DIR, gid), ignore_errors=True)
        self.installed.pop(gid, None)
        save_json(INSTALLED_FILE, self.installed)
        self.status.config(text=f"{name} uninstalled.")
        self.render_games()


if __name__ == "__main__":
    Launcher().mainloop()
