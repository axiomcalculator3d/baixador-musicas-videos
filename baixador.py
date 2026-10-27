"""Baixador de músicas e vídeos.

Cole um link (vídeo, música ou playlist), escolha formato e qualidade e baixe.
Usa yt-dlp por baixo, então funciona com YouTube, YouTube Music, SoundCloud,
Vimeo, Instagram, TikTok e centenas de outros sites.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"
DEFAULT_FOLDER = Path.home() / "Downloads" / "Baixador"

# Ferramentas instaladas no venv (ex.: deno) precisam estar no PATH para o yt-dlp achar.
_scripts = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
os.environ["PATH"] = str(_scripts) + os.pathsep + os.environ.get("PATH", "")

VIDEO_QUALITIES = {
    "Melhor disponível": None,
    "2160p (4K)": 2160,
    "1440p (2K)": 1440,
    "1080p (Full HD)": 1080,
    "720p (HD)": 720,
    "480p": 480,
    "360p": 360,
}

AUDIO_QUALITIES = {
    "MP3 320 kbps": ("mp3", "320"),
    "MP3 192 kbps": ("mp3", "192"),
    "MP3 128 kbps": ("mp3", "128"),
    "M4A (melhor, sem conversão)": ("m4a", None),
}

SINGLE_TMPL = "%(title).150B.%(ext)s"
# Itens de playlist vão para uma subpasta com o nome da playlist, numerados.
PLAYLIST_TMPL = "%(playlist_title).80B/%(playlist_index)03d - %(title).150B.%(ext)s"


class Cancelled(Exception):
    pass


def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    # winget instala o FFmpeg aqui, mas o PATH só é atualizado em terminais novos.
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for exe in winget.glob("*FFmpeg*/**/bin/ffmpeg.exe"):
        return str(exe.parent)
    return None


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(data):
    try:
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def build_options(mode, quality, folder, whole_playlist, ffmpeg_dir):
    opts = {
        # pl_thumbnail vazio: não salva a capa da playlist como arquivo solto.
        "outtmpl": {"default": SINGLE_TMPL, "pl_thumbnail": ""},
        "paths": {"home": folder},
        "noplaylist": not whole_playlist,
        "ignoreerrors": "only_download",  # um item com erro não derruba a playlist
        "noprogress": True,
        "windowsfilenames": True,
        "overwrites": False,
        "continuedl": True,
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir

    if mode == "video":
        height = VIDEO_QUALITIES[quality]
        opts["format"] = "bv*+ba/b"
        # Prefere a maior resolução até o limite escolhido, e MP4/M4A para tocar em qualquer lugar.
        opts["format_sort"] = [f"res:{height}" if height else "res", "vcodec:h264", "ext:mp4:m4a"]
        opts["merge_output_format"] = "mp4"
    else:
        codec, kbps = AUDIO_QUALITIES[quality]
        opts["writethumbnail"] = True
        if codec == "mp3":
            opts["format"] = "ba/b"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": kbps},
            ]
        else:
            opts["format"] = "ba[ext=m4a]/ba/b"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
            ]
        opts["postprocessors"] += [
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ]
    return opts


class QueueLogger:
    def __init__(self, events, quiet=False):
        self.events = events
        self.quiet = quiet

    def debug(self, msg):
        # O yt-dlp manda mensagens normais por debug(); as de debug de verdade começam com [debug].
        if not self.quiet and not msg.startswith("[debug] "):
            self.info(msg)

    def info(self, msg):
        if msg.startswith(("[download] Destination", "[ExtractAudio] Destination", "[Merger]")):
            self.events.put(("log", msg))
        elif msg.startswith("[download] Downloading item"):
            self.events.put(("log", msg))

    def warning(self, msg):
        self.events.put(("log", f"Aviso: {msg}"))

    def error(self, msg):
        self.events.put(("log", msg))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Baixador de Músicas e Vídeos")
        self.geometry("720x560")
        self.minsize(600, 480)

        self.events = queue.Queue()
        self.cancel_flag = threading.Event()
        self.worker = None
        self.config_data = load_config()
        self.ffmpeg_dir = find_ffmpeg()

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self.config_data.get("mode", "video"))
        self.quality_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=self.config_data.get("folder", str(DEFAULT_FOLDER)))
        self.playlist_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Cole um link e clique em Baixar.")

        self._build()
        self._on_mode_change(initial=True)
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self.ffmpeg_dir:
            self._log("FFmpeg não encontrado. Rode o iniciar.bat de novo para instalar, "
                      "senão MP3 e vídeos em alta qualidade não funcionam.")

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Link:").grid(row=0, column=0, sticky="w", **pad)
        url_entry = ttk.Entry(frm, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, sticky="ew", **pad)
        url_entry.bind("<Return>", lambda _e: self._start())
        ttk.Button(frm, text="Colar", command=self._paste).grid(row=0, column=2, **pad)
        url_entry.focus_set()

        ttk.Label(frm, text="Formato:").grid(row=1, column=0, sticky="w", **pad)
        modes = ttk.Frame(frm)
        modes.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(modes, text="Vídeo (MP4)", value="video", variable=self.mode_var,
                        command=self._on_mode_change).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(modes, text="Música / Áudio", value="audio", variable=self.mode_var,
                        command=self._on_mode_change).pack(side="left")

        ttk.Label(frm, text="Qualidade:").grid(row=2, column=0, sticky="w", **pad)
        self.quality_box = ttk.Combobox(frm, textvariable=self.quality_var, state="readonly", width=32)
        self.quality_box.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Salvar em:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.folder_var).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Escolher…", command=self._choose_folder).grid(row=3, column=2, **pad)

        ttk.Checkbutton(frm, text="Se o link for de uma playlist, baixar a playlist inteira",
                        variable=self.playlist_var).grid(row=4, column=1, columnspan=2, sticky="w", **pad)

        buttons = ttk.Frame(frm)
        buttons.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)
        self.download_btn = ttk.Button(buttons, text="Baixar", command=self._start)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(buttons, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=10)
        ttk.Button(buttons, text="Abrir pasta", command=self._open_folder).pack(side="right")

        self.progress = ttk.Progressbar(frm, maximum=100)
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(frm, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, sticky="w", **pad)

        log_frame = ttk.Frame(frm)
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", **pad)
        frm.rowconfigure(8, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _on_mode_change(self, initial=False):
        if self.mode_var.get() == "video":
            options = list(VIDEO_QUALITIES)
            saved = self.config_data.get("video_quality")
        else:
            options = list(AUDIO_QUALITIES)
            saved = self.config_data.get("audio_quality")
        self.quality_box["values"] = options
        self.quality_var.set(saved if initial is True and saved in options else options[0])

    def _paste(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def _open_folder(self):
        folder = Path(self.folder_var.get())
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", str(folder)])

    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        url = self.url_var.get().strip()
        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Link inválido", "Cole um link que comece com http:// ou https://")
            return
        folder = self.folder_var.get().strip() or str(DEFAULT_FOLDER)
        Path(folder).mkdir(parents=True, exist_ok=True)

        mode, quality = self.mode_var.get(), self.quality_var.get()
        self.config_data.update({"mode": mode, "folder": folder, f"{mode}_quality": quality})
        save_config(self.config_data)

        opts = build_options(mode, quality, folder, self.playlist_var.get(), self.ffmpeg_dir)
        self.cancel_flag.clear()
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress["value"] = 0
        self.status_var.set("Buscando informações do link…")
        self._log(f"\n=== {url} ({quality}) ===")

        self.worker = threading.Thread(target=self._run, args=(url, opts), daemon=True)
        self.worker.start()

    def _cancel(self):
        self.cancel_flag.set()
        self.status_var.set("Cancelando…")

    def _run(self, url, opts):
        done = []

        def progress_hook(d):
            if self.cancel_flag.is_set():
                raise Cancelled()
            info = d.get("info_dict", {})
            prefix = ""
            if info.get("playlist_index") and info.get("n_entries"):
                prefix = f"[{info['playlist_index']}/{info['n_entries']}] "
            title = info.get("title", "")
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                pct = d["downloaded_bytes"] / total * 100 if total else 0
                speed = d.get("speed")
                speed_txt = f" — {speed / 1_048_576:.1f} MB/s" if speed else ""
                self.events.put(("progress", pct, f"{prefix}Baixando: {title} ({pct:.0f}%){speed_txt}"))
            elif d["status"] == "finished":
                self.events.put(("progress", 100, f"{prefix}Processando: {title}"))

        def postprocessor_hook(d):
            # MoveFiles é o último passo de cada item: o arquivo final já está na pasta.
            if d["status"] == "finished" and d["postprocessor"] == "MoveFiles":
                title = d["info_dict"].get("title", "?")
                done.append(title)
                self.events.put(("log", f"✔ {title}"))

        logger = QueueLogger(self.events)
        try:
            # Consulta rápida (sem baixar) só para saber se o link é uma playlist.
            probe_opts = {"extract_flat": "in_playlist", "noplaylist": opts["noplaylist"],
                          "logger": QueueLogger(self.events, quiet=True), "noprogress": True}
            with yt_dlp.YoutubeDL(probe_opts) as ydl:
                probe = ydl.extract_info(url, download=False)
            if probe and probe.get("_type") == "playlist":
                count = probe.get("playlist_count") or len(probe.get("entries") or [])
                self.events.put(("log", f"Playlist: {probe.get('title', '?')} ({count} itens)"))
                opts = dict(opts, outtmpl={**opts["outtmpl"], "default": PLAYLIST_TMPL})

            opts = dict(opts, logger=logger,
                        progress_hooks=[progress_hook], postprocessor_hooks=[postprocessor_hook])
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            if info and info.get("_type") == "playlist":
                total = len([e for e in info.get("entries") or [] if e is not None])
                failed_count = max(0, (info.get("playlist_count") or total) - len(done))
                summary = f"Concluído: {len(done)} de {info.get('playlist_count') or total} itens baixados."
                if failed_count:
                    summary += f" {failed_count} falharam (veja o registro)."
            elif done:
                summary = "Concluído!"
            else:
                summary = "Nada foi baixado (veja o registro)."
            self.events.put(("done", summary))
        except Cancelled:
            self.events.put(("done", f"Cancelado. {len(done)} item(ns) já baixado(s)."))
        except Exception as exc:  # noqa: BLE001 — qualquer erro do yt-dlp vai para a tela
            self.events.put(("log", f"Erro: {exc}"))
            self.events.put(("done", "Falhou. Veja o registro abaixo."))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self._log(event[1])
                elif event[0] == "progress":
                    self.progress["value"] = event[1]
                    self.status_var.set(event[2])
                elif event[0] == "done":
                    self.status_var.set(event[1])
                    self._log(event[1])
                    self.download_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Sair", "Há um download em andamento. Sair mesmo assim?"):
                return
            self.cancel_flag.set()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
