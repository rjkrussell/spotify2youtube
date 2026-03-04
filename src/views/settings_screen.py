"""Settings/Credentials screen with forms for Spotify and YouTube Music auth."""

from __future__ import annotations

import threading
import traceback
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import TYPE_CHECKING

from src.app import SPOTIFY_GREEN, YOUTUBE_RED, YT_LABEL, get_colors, GradientBar

if TYPE_CHECKING:
    from src.app import App


class SettingsScreen(tk.Frame):
    def __init__(self, parent: tk.Widget, app: App):
        super().__init__(parent)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        self._sp_cancel = threading.Event()
        self._yt_cancel = threading.Event()

        # Branded title
        title_frame = tk.Frame(self)
        title_frame.pack(pady=(20, 5))
        tk.Label(title_frame, text="\u266b", font=("TkDefaultFont", 18),
                 foreground=SPOTIFY_GREEN).pack(side="left")
        tk.Label(title_frame, text=" Spotify", font=("TkDefaultFont", 16, "bold"),
                 foreground=SPOTIFY_GREEN).pack(side="left")
        c = get_colors()
        tk.Label(title_frame, text=" \u2192 ", font=("TkDefaultFont", 16, "bold"),
                 foreground=c["separator"]).pack(side="left")
        tk.Label(title_frame, text=YT_LABEL, font=("TkDefaultFont", 16, "bold"),
                 foreground=YOUTUBE_RED).pack(side="left")
        tk.Label(title_frame, text="  \u2014  Settings", font=("TkDefaultFont", 14),
                 foreground=c["fg_muted"]).pack(side="left")

        GradientBar(self, height=4).pack(fill="x", padx=40, pady=(0, 5))

        form = tk.Frame(self)
        form.pack(fill="both", expand=True, padx=40, pady=10)

        # --- Spotify section ---
        sp_frame = ttk.LabelFrame(form, text="\u25cf Spotify", padding=10)
        sp_frame.pack(fill="x", pady=(0, 15))

        creds = self.app.credentials_manager.credentials

        # Step 1: Enter credentials
        sp_step1_label = ttk.Label(sp_frame, text="Step 1: Enter credentials",
                                   font=("TkDefaultFont", 0, "bold"))
        sp_step1_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Button(sp_frame, text="Guide", command=self._toggle_spotify_guide).grid(
            row=0, column=1, sticky="e", pady=(0, 4))

        ttk.Label(sp_frame, text="Client ID:").grid(row=1, column=0, sticky="w", pady=2)
        self.sp_client_id = ttk.Entry(sp_frame, width=50)
        self.sp_client_id.insert(0, creds.spotify_client_id)
        self.sp_client_id.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(sp_frame, text="Client Secret:").grid(row=2, column=0, sticky="w", pady=2)
        self.sp_client_secret = ttk.Entry(sp_frame, width=50, show="*")
        self.sp_client_secret.insert(0, creds.spotify_client_secret)
        self.sp_client_secret.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(sp_frame, text="Redirect URI:").grid(row=3, column=0, sticky="w", pady=2)
        self.sp_redirect_uri = ttk.Entry(sp_frame, width=50)
        self.sp_redirect_uri.insert(0, creds.spotify_redirect_uri)
        self.sp_redirect_uri.grid(row=3, column=1, padx=5, pady=2, sticky="ew")

        sp_frame.columnconfigure(1, weight=1)

        # Step 2: Test connection
        sp_step2_row = tk.Frame(sp_frame)
        sp_step2_row.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky="w")
        ttk.Label(sp_step2_row, text="Step 2:",
                  font=("TkDefaultFont", 0, "bold")).pack(side="left")
        self.sp_test_btn = ttk.Button(sp_step2_row, text="Test Connection", command=self._test_spotify)
        self.sp_test_btn.pack(side="left", padx=(5, 0))
        self.sp_cancel_btn = ttk.Button(sp_step2_row, text="Cancel", command=self._cancel_spotify)
        self.sp_cancel_btn.pack(side="left", padx=(5, 0))
        self.sp_cancel_btn.pack_forget()
        self.sp_status_var = tk.StringVar()
        self.sp_status = ttk.Entry(sp_step2_row, textvariable=self.sp_status_var,
                                   state="readonly", width=40)
        self.sp_status.pack(side="left", padx=10)

        self.sp_guide_frame = tk.Frame(sp_frame)
        self.sp_guide_frame.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.sp_guide_frame.grid_remove()
        self._build_guide(self.sp_guide_frame, [
            ("1. Go to ", None),
            ("developer.spotify.com/dashboard", "https://developer.spotify.com/dashboard"),
            (" and log in.\n", None),
            ('2. Click "Create App".\n', None),
            ("3. Give it any name/description. For Redirect URI enter:\n"
             "   http://127.0.0.1:8888/callback\n", None),
            ('4. Under "Which API/SDKs are you planning to use?" select\n'
             '   "Web API", then save.\n', None),
            ("5. Open the app's settings and copy the Client ID and\n"
             "   Client Secret into the fields above.\n", None),
            ("6. Set the Redirect URI above to the same value you used\n"
             "   in the dashboard (e.g. http://127.0.0.1:8888/callback).", None),
        ])

        # --- YouTube Music section ---
        yt_frame = ttk.LabelFrame(form, text=f"\u25b6 {YT_LABEL}", padding=10)
        yt_frame.pack(fill="x", pady=(0, 15))

        # Step 1: Enter credentials
        yt_step1_label = ttk.Label(yt_frame, text="Step 1: Enter credentials",
                                   font=("TkDefaultFont", 0, "bold"))
        yt_step1_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Button(yt_frame, text="Guide", command=self._toggle_youtube_guide).grid(
            row=0, column=1, sticky="e", pady=(0, 4))

        ttk.Label(yt_frame, text="Client ID:").grid(row=1, column=0, sticky="w", pady=2)
        self.yt_client_id = ttk.Entry(yt_frame, width=50)
        self.yt_client_id.insert(0, creds.youtube_client_id)
        self.yt_client_id.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(yt_frame, text="Client Secret:").grid(row=2, column=0, sticky="w", pady=2)
        self.yt_client_secret = ttk.Entry(yt_frame, width=50, show="*")
        self.yt_client_secret.insert(0, creds.youtube_client_secret)
        self.yt_client_secret.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        yt_frame.columnconfigure(1, weight=1)

        # Step 2: Authenticate (token acquisition + auto-test in one flow)
        yt_step2_row = tk.Frame(yt_frame)
        yt_step2_row.grid(row=3, column=0, columnspan=2, pady=(8, 0), sticky="w")
        ttk.Label(yt_step2_row, text="Step 2:",
                  font=("TkDefaultFont", 0, "bold")).pack(side="left")
        self.yt_auth_btn = ttk.Button(yt_step2_row, text="Authenticate via Browser", command=self._run_yt_oauth)
        self.yt_auth_btn.pack(side="left", padx=(5, 0))
        self.yt_cancel_btn = ttk.Button(yt_step2_row, text="Cancel", command=self._cancel_youtube)
        self.yt_cancel_btn.pack(side="left", padx=(5, 0))
        self.yt_cancel_btn.pack_forget()

        self.yt_status_var = tk.StringVar()
        self.yt_status = ttk.Entry(yt_step2_row, textvariable=self.yt_status_var,
                                   state="readonly", width=40)
        if creds.has_youtube():
            self._set_status(self.yt_status, self.yt_status_var, "Authenticated", "green")
        self.yt_status.pack(side="left", padx=10)

        self.yt_guide_frame = tk.Frame(yt_frame)
        self.yt_guide_frame.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.yt_guide_frame.grid_remove()
        self._build_guide(self.yt_guide_frame, [
            ("A Google Cloud project with OAuth credentials is required.\n\n", None),
            ("1. Go to ", None),
            ("console.cloud.google.com", "https://console.cloud.google.com"),
            (" and create a project.\n", None),
            ('2. Enable the "YouTube Data API v3".\n', None),
            ("3. Under Credentials, create an OAuth 2.0 Client ID\n"
             "   (type: TV / Limited Input).\n", None),
            ("4. Enter the Client ID and Client Secret in Step 1 above.\n", None),
            ('5. Click "Authenticate via Browser" in Step 2 \u2014 a Google\n'
             "   sign-in page will open. Sign in and grant access.\n", None),
            ('6. Click "I\'ve Signed In" when done. The connection will be\n'
             "   verified automatically.", None),
        ])

        # --- Save button ---
        btn_frame = tk.Frame(form)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Save & Continue", command=self._save_and_continue).pack()

    def _set_status(self, entry: ttk.Entry, var: tk.StringVar, text: str, color: str):
        var.set(text)
        entry.configure(foreground=color)

    def _build_guide(self, parent: tk.Frame, segments: list[tuple[str, str | None]]):
        """Build a read-only Text widget with clickable links.

        segments is a list of (text, url) tuples. If url is None the text
        is rendered as normal; otherwise it is blue, underlined, and opens
        the URL in the default browser on click.
        """
        text = tk.Text(parent, wrap="word", borderwidth=0, highlightthickness=0,
                       padx=0, pady=5, cursor="arrow")
        text.configure(background=parent.cget("background"),
                       font=("TkDefaultFont", 10))
        text.pack(fill="x")

        link_index = 0
        for content, url in segments:
            if url is None:
                text.insert("end", content)
            else:
                tag = f"link{link_index}"
                text.insert("end", content, tag)
                text.tag_configure(tag, foreground="blue", underline=True)
                text.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                text.tag_bind(tag, "<Enter>", lambda e: text.configure(cursor="hand2"))
                text.tag_bind(tag, "<Leave>", lambda e: text.configure(cursor="arrow"))
                link_index += 1

        text.configure(state="disabled")
        # Resize height to fit content
        text.update_idletasks()
        line_count = int(text.index("end-1c").split(".")[0])
        text.configure(height=line_count)

    def _toggle_spotify_guide(self):
        if self.sp_guide_frame.winfo_manager():
            self.sp_guide_frame.grid_remove()
        else:
            self.sp_guide_frame.grid()

    def _toggle_youtube_guide(self):
        if self.yt_guide_frame.winfo_manager():
            self.yt_guide_frame.grid_remove()
        else:
            self.yt_guide_frame.grid()

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    def _apply_fields_to_credentials(self):
        creds = self.app.credentials_manager.credentials
        creds.spotify_client_id = self.sp_client_id.get().strip()
        creds.spotify_client_secret = self.sp_client_secret.get().strip()
        creds.spotify_redirect_uri = self.sp_redirect_uri.get().strip()
        creds.youtube_client_id = self.yt_client_id.get().strip()
        creds.youtube_client_secret = self.yt_client_secret.get().strip()

    def _auto_save(self):
        """Persist current credentials to disk so nothing is lost."""
        self._apply_fields_to_credentials()
        self.app.credentials_manager.save()

    # ------------------------------------------------------------------
    # Spotify
    # ------------------------------------------------------------------

    def _test_spotify(self):
        self._apply_fields_to_credentials()
        creds = self.app.credentials_manager.credentials
        if not creds.spotify_client_id or not creds.spotify_client_secret:
            self._set_status(self.sp_status, self.sp_status_var, "Enter Client ID and Secret first", "red")
            return

        self._sp_cancel.clear()
        self.sp_test_btn.config(state="disabled")
        self.sp_cancel_btn.pack(side="left", padx=(5, 0))
        self._set_status(self.sp_status, self.sp_status_var, "Testing...", "blue")
        self.app.log("Testing Spotify connection...")

        def _run():
            try:
                from src.services.spotify_service import SpotifyService
                svc = SpotifyService(creds)
                msg = svc.test_credentials()
                if not self._sp_cancel.is_set():
                    self.after(0, lambda: self._sp_done(msg, "green", "success"))
            except Exception as e:
                err = str(e)
                if len(err) > 80:
                    err = err[:80] + "..."
                traceback.print_exc()
                if not self._sp_cancel.is_set():
                    self.after(0, lambda: self._sp_done(f"Failed: {err}", "red", "error"))

        threading.Thread(target=_run, daemon=True).start()

    def _cancel_spotify(self):
        self._sp_cancel.set()
        self._sp_done("Cancelled", "gray")

    def _sp_done(self, text, color, log_level=None):
        self.sp_test_btn.config(state="normal")
        self.sp_cancel_btn.pack_forget()
        self._set_status(self.sp_status, self.sp_status_var, text, color)
        self.app.log(f"Spotify: {text}", log_level or "info")
        if log_level == "success":
            self._auto_save()

    # ------------------------------------------------------------------
    # YouTube Music
    # ------------------------------------------------------------------

    def _run_yt_oauth(self):
        self._apply_fields_to_credentials()
        creds = self.app.credentials_manager.credentials
        if not creds.youtube_client_id or not creds.youtube_client_secret:
            self._set_status(self.yt_status, self.yt_status_var, "Enter Client ID and Secret first", "red")
            return
        self._yt_cancel.clear()
        self.yt_auth_btn.config(state="disabled")
        self.yt_cancel_btn.pack(side="left", padx=(5, 0))
        self._set_status(self.yt_status, self.yt_status_var, "Starting auth...", "blue")
        self.app.log("Starting YouTube Music OAuth flow...")

        def _start():
            try:
                from src.services.youtube_service import YouTubeService
                svc = YouTubeService(self.app.credentials_manager.credentials)
                oauth_creds, code, url = svc.start_oauth_flow()
                if self._yt_cancel.is_set():
                    return
                self.after(0, lambda: self._yt_show_code(svc, oauth_creds, code, url))
            except Exception as e:
                msg = f"OAuth failed: {e}"
                traceback.print_exc()
                if not self._yt_cancel.is_set():
                    self.after(0, lambda: self._yt_done(msg, "red", "error"))

        threading.Thread(target=_start, daemon=True).start()

    def _yt_show_code(self, svc, oauth_creds, code, url):
        """Show the device code and a button to confirm login."""
        user_code = code["user_code"]
        self._set_status(self.yt_status, self.yt_status_var,
                         f"Enter code: {user_code}", "blue")
        self.app.log(f"Browser opened. Enter code: {user_code}")
        self.app.log(f"URL: {url}")

        # Replace Cancel with "I've Signed In"
        self.yt_cancel_btn.pack_forget()
        self._yt_confirm_btn = ttk.Button(
            self.yt_cancel_btn.master, text="I've Signed In",
            command=lambda: self._yt_exchange_code(svc, oauth_creds, code),
        )
        self._yt_confirm_btn.pack(side="left", padx=(5, 0))
        self.yt_cancel_btn.pack(side="left", padx=(5, 0))

    def _yt_exchange_code(self, svc, oauth_creds, code):
        """Exchange the device code for a token after user confirms login."""
        self._yt_confirm_btn.pack_forget()
        self._set_status(self.yt_status, self.yt_status_var, "Exchanging code...", "blue")

        def _finish():
            try:
                token = svc.finish_oauth_flow(oauth_creds, code)
                if self._yt_cancel.is_set():
                    return
                # Store token and save to disk immediately
                self.app.credentials_manager.credentials.youtube_oauth_token = token
                self.after(0, self._auto_save)
                # Auto-verify the connection
                self.after(0, lambda: self._set_status(
                    self.yt_status, self.yt_status_var, "Verifying connection...", "blue"))
                self.after(0, lambda: self.app.log("Token acquired. Verifying connection..."))
                name = svc.test_connection()
                if not self._yt_cancel.is_set():
                    self.after(0, lambda: self._yt_done(f"Connected: {name}", "green", "success"))
            except Exception as e:
                msg = str(e)
                if len(msg) > 80:
                    msg = msg[:80] + "..."
                traceback.print_exc()
                if not self._yt_cancel.is_set():
                    # Token may have been acquired even if the test failed
                    has_token = bool(self.app.credentials_manager.credentials.youtube_oauth_token)
                    if has_token:
                        self.after(0, lambda: self._yt_done(
                            f"Authenticated (test failed: {msg})", "orange", "error"))
                    else:
                        self.after(0, lambda: self._yt_done(f"OAuth failed: {msg}", "red", "error"))

        threading.Thread(target=_finish, daemon=True).start()

    def _cancel_youtube(self):
        self._yt_cancel.set()
        if hasattr(self, "_yt_confirm_btn"):
            self._yt_confirm_btn.pack_forget()
        self._yt_done("Cancelled", "gray")

    def _yt_done(self, text, color, log_level=None):
        self.yt_auth_btn.config(state="normal")
        self.yt_cancel_btn.pack_forget()
        self._set_status(self.yt_status, self.yt_status_var, text, color)
        self.app.log(f"YouTube Music: {text}", log_level or "info")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _save_and_continue(self):
        self._auto_save()
        self.app.log("Credentials saved.", "success")
        self.app.show_screen("main")

    def on_show(self):
        """Called when screen is raised — refresh fields from credentials."""
        creds = self.app.credentials_manager.credentials
        for entry, val in [
            (self.sp_client_id, creds.spotify_client_id),
            (self.sp_client_secret, creds.spotify_client_secret),
            (self.sp_redirect_uri, creds.spotify_redirect_uri),
            (self.yt_client_id, creds.youtube_client_id),
            (self.yt_client_secret, creds.youtube_client_secret),
        ]:
            entry.delete(0, tk.END)
            entry.insert(0, val)
        # Refresh YouTube status based on current token state
        if creds.has_youtube():
            self._set_status(self.yt_status, self.yt_status_var, "Authenticated", "green")
        else:
            self._set_status(self.yt_status, self.yt_status_var, "", "black")
