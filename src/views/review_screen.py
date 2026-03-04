"""Review screen — post-transfer results, manual resolution, export log."""

from __future__ import annotations

import csv
import io
import tkinter as tk
from tkinter import ttk, filedialog
from typing import TYPE_CHECKING

from src.models.library import TransferStatus

if TYPE_CHECKING:
    from src.app import App
    from src.services.transfer import TransferProgress


class ReviewScreen(tk.Frame):
    def __init__(self, parent: tk.Widget, app: App, progress: TransferProgress, dry_run: bool = False):
        super().__init__(parent)
        self.app = app
        self.progress = progress
        self.dry_run = dry_run
        self._build_ui()

    def _build_ui(self):
        # Title
        dry_label = " (Dry Run)" if self.dry_run else ""
        title = tk.Label(self, text=f"Transfer Results{dry_label}", font=("TkDefaultFont", 16, "bold"))
        title.pack(pady=(15, 5))

        # Summary
        summary_frame = tk.Frame(self)
        summary_frame.pack(fill="x", padx=20, pady=10)

        results = self.progress.results
        success_count = sum(1 for r in results if r.status == TransferStatus.SUCCESS)
        failed_count = len(self.progress.failed_tracks)
        ambiguous_count = len(self.progress.ambiguous_tracks)
        skipped_count = sum(1 for r in results if r.status == TransferStatus.SKIPPED)

        summary_data = [
            ("Matched", success_count, "green"),
            ("Failed", failed_count, "red"),
            ("Ambiguous", ambiguous_count, "orange"),
            ("Skipped", skipped_count, "gray"),
        ]

        for i, (label, count, color) in enumerate(summary_data):
            tk.Label(summary_frame, text=f"{label}: {count}", foreground=color,
                     font=("TkDefaultFont", 12, "bold")).grid(row=0, column=i, padx=15)

        # Results treeview in a sunken frame
        outer_frame = tk.LabelFrame(self, text="Results (scroll to see error details)",
                                     relief="sunken", borderwidth=2)
        outer_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Use grid inside so scrollbars sit flush at edges
        outer_frame.rowconfigure(0, weight=1)
        outer_frame.columnconfigure(0, weight=1)

        columns = ("track", "artists", "status", "score", "error")
        self.results_tree = ttk.Treeview(outer_frame, columns=columns, show="headings", height=12)
        self.results_tree.heading("track", text="Track")
        self.results_tree.heading("artists", text="Artists")
        self.results_tree.heading("status", text="Status")
        self.results_tree.heading("score", text="Score")
        self.results_tree.heading("error", text="Error")
        self.results_tree.column("track", width=200, minwidth=120, stretch=False)
        self.results_tree.column("artists", width=150, minwidth=80, stretch=False)
        self.results_tree.column("status", width=80, minwidth=60, stretch=False)
        self.results_tree.column("score", width=50, minwidth=40, stretch=False)
        self.results_tree.column("error", width=500, minwidth=200, stretch=False)

        yscroll = ttk.Scrollbar(outer_frame, orient="vertical", command=self.results_tree.yview)
        xscroll = ttk.Scrollbar(outer_frame, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        # Enable trackpad/mousewheel scrolling (macOS sends <MouseWheel> for both axes)
        def _on_mousewheel(event):
            self.results_tree.yview_scroll(-event.delta, "units")
        def _on_shift_mousewheel(event):
            self.results_tree.xview_scroll(-event.delta, "units")
        self.results_tree.bind("<MouseWheel>", _on_mousewheel)
        self.results_tree.bind("<Shift-MouseWheel>", _on_shift_mousewheel)

        # Tag colors for status
        self.results_tree.tag_configure("success", foreground="green")
        self.results_tree.tag_configure("failed", foreground="red")
        self.results_tree.tag_configure("ambiguous", foreground="orange")
        self.results_tree.tag_configure("skipped", foreground="gray")

        # Populate results
        self._result_map: dict[str, object] = {}
        for result in results:
            tag = result.status.value
            item_id = self.results_tree.insert("", "end", values=(
                result.track.name,
                ", ".join(result.track.artists),
                result.status.value.title(),
                f"{result.score:.0f}" if result.score else "",
                result.error or "",
            ), tags=(tag,))
            self._result_map[item_id] = result

        self.results_tree.bind("<<TreeviewSelect>>", self._on_select_result)

        # Resolution panel (for ambiguous tracks)
        self.resolution_frame = ttk.LabelFrame(self, text="Manual Resolution", padding=10)
        self.resolution_frame.pack(fill="x", padx=20, pady=5)

        self.resolution_info = tk.Label(self.resolution_frame,
                                        text="Select an ambiguous track above to resolve manually.",
                                        foreground="gray")
        self.resolution_info.pack(anchor="w")

        self.candidates_frame = tk.Frame(self.resolution_frame)
        self.candidates_frame.pack(fill="x")

        # Search again
        search_frame = tk.Frame(self.resolution_frame)
        search_frame.pack(fill="x", pady=5)
        tk.Label(search_frame, text="Custom search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side="left", padx=5)
        ttk.Button(search_frame, text="Search Again", command=self._search_again).pack(side="left")
        ttk.Button(search_frame, text="Skip", command=self._skip_current).pack(side="left", padx=5)

        # Bottom buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)

        ttk.Button(btn_frame, text="Export Log", command=self._export_log).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Back to Library", command=self._go_back).pack(side="right", padx=5)

    def _on_select_result(self, event):
        """Show resolution options for selected ambiguous track."""
        selection = self.results_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        result = self._result_map.get(item_id)
        if not result or result.status != TransferStatus.AMBIGUOUS:
            self.resolution_info.config(text="This track is not ambiguous — no resolution needed.")
            for w in self.candidates_frame.winfo_children():
                w.destroy()
            return

        self._current_result = result
        self._current_tree_item = item_id

        self.resolution_info.config(
            text=f"Resolve: {result.track.name} — {', '.join(result.track.artists)}"
        )
        self.search_var.set(f"{result.track.name} {result.track.artists[0]}")
        self._show_candidates(result.candidates or [])

    def _show_candidates(self, candidates: list[dict]):
        """Display candidate matches with [Select] buttons."""
        for w in self.candidates_frame.winfo_children():
            w.destroy()

        if not candidates:
            tk.Label(self.candidates_frame, text="No candidates found.", foreground="gray").pack()
            return

        for i, candidate in enumerate(candidates):
            row = tk.Frame(self.candidates_frame)
            row.pack(fill="x", pady=1)

            title = candidate.get("title", "Unknown")
            artists = ", ".join(a.get("name", "") for a in candidate.get("artists", []))
            duration = candidate.get("duration", "")
            video_id = candidate.get("videoId", "")

            tk.Label(row, text=f"{i+1}. {title} — {artists}", anchor="w").pack(side="left", fill="x", expand=True)
            if duration:
                tk.Label(row, text=duration, foreground="gray").pack(side="left", padx=5)
            ttk.Button(row, text="Select", command=lambda vid=video_id, c=candidate: self._select_candidate(vid, c)).pack(side="right")

    def _select_candidate(self, video_id: str, candidate: dict):
        """Accept a candidate match."""
        if not hasattr(self, "_current_result"):
            return

        result = self._current_result
        result.track.yt_video_id = video_id
        result.track.transfer_status = TransferStatus.SUCCESS
        result.track.yt_candidates = []

        # Write to YT Music if not dry run
        if not self.dry_run:
            try:
                from src.services.youtube_service import YouTubeService
                yt_svc = YouTubeService(self.app.credentials_manager.credentials)
                yt_svc.rate_song(video_id, "LIKE")
            except Exception:
                pass

        self.app.state_manager.save()

        # Update tree item
        self.results_tree.item(self._current_tree_item, values=(
            result.track.name,
            ", ".join(result.track.artists),
            "Success",
            "",
        ), tags=("success",))

        self.resolution_info.config(text=f"Resolved: {result.track.name} -> {candidate.get('title', video_id)}")
        for w in self.candidates_frame.winfo_children():
            w.destroy()

    def _search_again(self):
        """Search YT Music with a custom query."""
        query = self.search_var.get().strip()
        if not query:
            return

        try:
            from src.services.youtube_service import YouTubeService
            yt_svc = YouTubeService(self.app.credentials_manager.credentials)
            candidates = yt_svc.search_tracks(query, limit=5)
            self._show_candidates(candidates)
        except Exception as e:
            self.resolution_info.config(text=f"Search error: {e}")

    def _skip_current(self):
        """Skip the currently selected ambiguous track."""
        if not hasattr(self, "_current_result"):
            return
        result = self._current_result
        result.track.transfer_status = TransferStatus.SKIPPED
        self.app.state_manager.save()

        self.results_tree.item(self._current_tree_item, values=(
            result.track.name,
            ", ".join(result.track.artists),
            "Skipped",
            "",
        ), tags=("skipped",))

        self.resolution_info.config(text=f"Skipped: {result.track.name}")
        for w in self.candidates_frame.winfo_children():
            w.destroy()

    def _export_log(self):
        """Export transfer results to a CSV file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Transfer Log",
        )
        if not path:
            return

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Track", "Artists", "Album", "Status", "Score", "YT Video ID", "Error"])
            for result in self.progress.results:
                writer.writerow([
                    result.track.name,
                    ", ".join(result.track.artists),
                    result.track.album,
                    result.status.value,
                    f"{result.score:.0f}" if result.score else "",
                    result.track.yt_video_id or "",
                    result.error or "",
                ])

    def _go_back(self):
        self.app.show_screen("main")
