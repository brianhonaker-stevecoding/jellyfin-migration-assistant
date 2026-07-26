from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path

from .windows_export import create_windows_export_package, default_windows_appdata_root, discover_windows_source


def main() -> int:
    import tkinter as tk

    root = tk.Tk()
    root.title("Jellyfin Migration Assistant")
    root.geometry("760x560")
    root.minsize(680, 500)

    app = WindowsMigrationApp(root)
    root.after(100, app.autodetect)
    root.mainloop()
    return 0


class WindowsMigrationApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.appdata_var = tk.StringVar(value=str(default_windows_appdata_root()))
        self.output_var = tk.StringVar(value=str(Path.home() / "Desktop" / "jellyfin-migration.zip"))
        self.version_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.media_roots: list[str] = []

        frame = ttk.Frame(root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        title = ttk.Label(frame, text="Create Jellyfin Migration Package", font=("", 16, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        ttk.Label(frame, text="Jellyfin server folder").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.appdata_var).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(frame, text="Browse", command=self.choose_appdata).grid(row=1, column=2, pady=4)

        ttk.Label(frame, text="Output package").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(frame, text="Save As", command=self.choose_output).grid(row=2, column=2, pady=4)

        ttk.Label(frame, text="Detected Jellyfin version").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.version_var).grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(frame, text="Detected media locations").grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 4))
        self.media_list = tk.Listbox(frame, height=8)
        self.media_list.grid(row=5, column=0, columnspan=3, sticky="nsew")

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        buttons.columnconfigure(3, weight=1)
        ttk.Button(buttons, text="Detect", command=self.autodetect).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Add Media Folder", command=self.add_media_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Remove Selected", command=self.remove_selected_media).grid(row=0, column=2, padx=(0, 8))
        self.create_button = ttk.Button(buttons, text="Create Package", command=self.create_package)
        self.create_button.grid(row=0, column=4)

        ttk.Label(frame, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def choose_appdata(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Choose Jellyfin Server folder")
        if selected:
            self.appdata_var.set(selected)

    def choose_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.asksaveasfilename(
            title="Save migration package",
            defaultextension=".zip",
            filetypes=(("Zip package", "*.zip"), ("All files", "*.*")),
        )
        if selected:
            self.output_var.set(selected)

    def add_media_folder(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Where are your media files?")
        if selected and selected not in self.media_roots:
            self.media_roots.append(selected)
            self._refresh_media_list()

    def remove_selected_media(self) -> None:
        selected = list(self.media_list.curselection())
        for index in reversed(selected):
            del self.media_roots[index]
        self._refresh_media_list()

    def autodetect(self) -> None:
        self._run_background("Detecting Jellyfin source...", self._detect_worker)

    def create_package(self) -> None:
        from tkinter import messagebox

        if not self.media_roots:
            messagebox.showinfo("Media location needed", "Choose the folder where your media files live.")
            self.add_media_folder()
            if not self.media_roots:
                self.status_var.set("Choose a media folder before creating the package.")
                return
        self._run_background("Creating migration package...", self._package_worker)

    def _detect_worker(self) -> tuple[str, object]:
        discovery = discover_windows_source(Path(self.appdata_var.get()))
        return ("detect", discovery)

    def _package_worker(self) -> tuple[str, object]:
        package = create_windows_export_package(
            output_package=Path(self.output_var.get()),
            appdata_root=Path(self.appdata_var.get()),
            target_version=self.version_var.get() or None,
            media_roots=tuple(self.media_roots),
        )
        return ("package", package)

    def _run_background(self, status: str, worker) -> None:
        self.status_var.set(status)
        self.create_button.state(["disabled"])

        def run() -> None:
            try:
                kind, value = worker()
                self.events.put((kind, value))
            except Exception:
                self.events.put(("error", traceback.format_exc()))

        threading.Thread(target=run, daemon=True).start()
        self.root.after(100, self._poll_events)

    def _poll_events(self) -> None:
        try:
            kind, value = self.events.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_events)
            return

        self.create_button.state(["!disabled"])
        if kind == "detect":
            self._handle_discovery(value)
        elif kind == "package":
            self._handle_package(value)
        elif kind == "error":
            self._show_error(str(value))

    def _handle_discovery(self, discovery) -> None:
        from tkinter import messagebox

        self.media_roots = list(discovery.media_roots)
        self.version_var.set(discovery.detected_version or "")
        self._refresh_media_list()

        blockers = [ticket for ticket in discovery.tickets if ticket.blocks_apply]
        if blockers:
            self.status_var.set(blockers[0].summary)
            messagebox.showerror("Jellyfin source needs attention", blockers[0].summary)
            return

        if not self.media_roots:
            self.status_var.set("Choose the folder where your media files live.")
            messagebox.showinfo("Media location needed", "I could not detect your media folder. Choose it with Add Media Folder.")
            return

        self.status_var.set("Ready to create migration package.")

    def _handle_package(self, package) -> None:
        from tkinter import messagebox

        blockers = [ticket for ticket in package.tickets if ticket.blocks_apply]
        if blockers:
            self.status_var.set(blockers[0].summary)
            messagebox.showerror("Package was not created", blockers[0].summary)
            return

        self.status_var.set(f"Created {package.package_path}")
        messagebox.showinfo("Package created", f"Migration package created:\n{package.package_path}")

    def _show_error(self, details: str) -> None:
        from tkinter import messagebox

        self.status_var.set("An unexpected error occurred.")
        messagebox.showerror("Unexpected error", details)

    def _refresh_media_list(self) -> None:
        self.media_list.delete(0, "end")
        for root in self.media_roots:
            self.media_list.insert("end", root)


if __name__ == "__main__":
    raise SystemExit(main())
