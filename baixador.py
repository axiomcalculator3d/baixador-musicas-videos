"""Baixador de músicas e vídeos.

Cole um link (vídeo, música ou playlist), escolha formato e qualidade e baixe.
Usa yt-dlp por baixo, então funciona com YouTube, YouTube Music, SoundCloud,
Vimeo, Instagram, TikTok e centenas de outros sites.

Organização na pasta escolhida:
    Músicas/<Artista>/<Música>.mp3      ← só MP3, agrupado por artista
    Outros formatos/<Artista>/<Música>.m4a
    Vídeos/<Título>.mp4                 (playlists numa subpasta com o nome dela)
"""

import gc
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp
from yt_dlp.postprocessor import PostProcessor
from yt_dlp.utils import DownloadCancelled

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

VIDEO_TMPL = "Vídeos/%(title).150B.%(ext)s"
VIDEO_PLAYLIST_TMPL = "Vídeos/%(playlist_title).80B/%(playlist_index)03d - %(title).150B.%(ext)s"
MP3_TMPL = "Músicas/%(pasta_artista).80B/%(musica).150B.%(ext)s"
OTHER_AUDIO_TMPL = "Outros formatos/%(pasta_artista).80B/%(musica).150B.%(ext)s"

UNKNOWN_ARTIST = "Artista desconhecido"
# "(Official Video)", "[Clipe Oficial]", "(Lyrics)", "(Áudio)"... saem do nome da música.
_NOISE = re.compile(
    r"\s*[\(\[][^\)\]]*\b(official|oficial|video|vídeo|clipe|videoclipe|lyrics?|letra|audio|áudio|"
    r"visuali[sz]er|hd|4k|mv|m/v)\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_FEAT = re.compile(r"\s+(feat\.?|ft\.?|featuring|part\.?|participação)\s+.*$", re.IGNORECASE)
_SEPARATOR = re.compile(r"^\s*(.+?)\s+[-–—|]\s+(.+)$")


def clean_song(text):
    text = _NOISE.sub("", text or "")
    return text.strip(" -–—|\"'") or "Sem título"


def clean_artist(text):
    text = _FEAT.sub("", text or "")
    text = re.sub(r"\s*-\s*Topic$", "", text)  # canais automáticos do YouTube: "Artista - Topic"
    text = re.sub(r"(?<=[a-z])VEVO$", "", text)  # "AdeleVEVO" -> "Adele"
    return text.strip(" -–—|\"'") or UNKNOWN_ARTIST


def guess_artist_song(info):
    """Descobre (artista principal, nome da música) a partir dos dados do vídeo."""
    artists = info.get("artists") or ([info["artist"]] if info.get("artist") else [])
    title = info.get("title") or ""
    if artists:
        # Metadados de verdade (YouTube Music, SoundCloud…): usa o primeiro artista.
        song = info.get("track") or title
        match = _SEPARATOR.match(song)
        if not info.get("track") and match:
            song = match.group(2)
        return clean_artist(artists[0].split(",")[0]), clean_song(song)
    match = _SEPARATOR.match(title)
    if match:  # Título no formato "Artista - Música"
        return clean_artist(match.group(1)), clean_song(match.group(2))
    return clean_artist(info.get("channel") or info.get("uploader")), clean_song(title)


class ArtistOrganizer(PostProcessor):
    """Roda antes do download: define a pasta do artista, o nome do arquivo e as tags."""

    def run(self, info):
        artist, song = guess_artist_song(info)
        info["pasta_artista"] = artist
        info["musica"] = song
        if not info.get("artists"):
            info["artists"] = [artist]
            info["artist"] = artist
        if not info.get("track"):
            info["track"] = song
        return [], info


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
        "outtmpl": {"default": VIDEO_TMPL, "pl_thumbnail": ""},
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
        # final_ext faz o yt-dlp pular músicas que já estão na pasta, sem baixar de novo.
        opts["final_ext"] = codec
        if codec == "mp3":
            opts["outtmpl"]["default"] = MP3_TMPL
            opts["format"] = "ba/b"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": kbps},
            ]
        else:
            opts["outtmpl"]["default"] = OTHER_AUDIO_TMPL
            opts["format"] = "ba[ext=m4a]/ba/b"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
            ]
        opts["postprocessors"] += [
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ]
    return opts


def remove_partial_files(final_path, since):
    """Apaga o que sobrou do item interrompido (.part, .ytdl, capa, áudio ainda não convertido)."""
    path = Path(final_path)
    stem = path.with_suffix("").name
    # No Windows o .part pode continuar aberto por um instante depois do cancelamento.
    for _attempt in range(10):
        gc.collect()
        locked = False
        for leftover in path.parent.glob(glob_escape(stem) + ".*"):
            try:
                if leftover.stat().st_mtime >= since:
                    leftover.unlink()
            except PermissionError:
                locked = True
            except OSError:
                pass
        if not locked:
            break
        time.sleep(0.3)
    try:
        path.parent.rmdir()  # só remove se ficou vazia (ex.: pasta de artista novo)
    except OSError:
        pass


def glob_escape(text):
    return re.sub(r"([\[\]\*\?])", r"[\1]", text)


class QueueLogger:
    def __init__(self, emit, quiet=False, on_skip=None):
        self.emit = emit
        self.quiet = quiet
        self.on_skip = on_skip

    def debug(self, msg):
        # O yt-dlp manda mensagens normais por debug(); as de debug de verdade começam com [debug].
        if not self.quiet and not msg.startswith("[debug] "):
            self.info(msg)

    def info(self, msg):
        if msg.startswith(("[download] Destination", "[ExtractAudio] Destination", "[Merger]",
                           "[download] Downloading item")):
            self.emit("log", msg)
        elif msg.startswith("[download] ") and msg.endswith("has already been downloaded"):
            name = Path(msg[len("[download] "):-len(" has already been downloaded")]).name
            self.emit("log", f"↷ Já existia, pulando: {name}")
            if self.on_skip:
                self.on_skip(name)

    def warning(self, msg):
        self.emit("log", f"Aviso: {msg}")

    def error(self, msg):
        self.emit("log", msg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Baixador de Músicas e Vídeos")
        self.geometry("720x580")
        self.minsize(600, 500)

        self.events = queue.Queue()
        # Cada download tem seu próprio id e sinal de cancelamento; eventos de um download
        # cancelado são ignorados, então a tela libera na hora.
        self.run_id = 0
        self.cancel_event = threading.Event()
        self.worker = None
        self.running = False
        self.config_data = load_config()
        self.ffmpeg_dir = find_ffmpeg()

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self.config_data.get("mode", "video"))
        self.quality_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=self.config_data.get("folder", str(DEFAULT_FOLDER)))
        self.playlist_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Cole um link e clique em Baixar.")
        self.hint_var = tk.StringVar()

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
        self.quality_box.bind("<<ComboboxSelected>>", lambda _e: self._update_hint())

        ttk.Label(frm, text="Salvar em:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.folder_var).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Escolher…", command=self._choose_folder).grid(row=3, column=2, **pad)
        ttk.Label(frm, textvariable=self.hint_var, foreground="#555").grid(
            row=4, column=1, columnspan=2, sticky="w", padx=10)

        ttk.Checkbutton(frm, text="Se o link for de uma playlist, baixar a playlist inteira",
                        variable=self.playlist_var).grid(row=5, column=1, columnspan=2, sticky="w", **pad)

        buttons = ttk.Frame(frm)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", **pad)
        self.download_btn = ttk.Button(buttons, text="Baixar", command=self._start)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(buttons, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=10)
        ttk.Button(buttons, text="Abrir pasta", command=self._open_folder).pack(side="right")

        self.progress = ttk.Progressbar(frm, maximum=100)
        self.progress.grid(row=7, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(frm, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, sticky="w", **pad)

        log_frame = ttk.Frame(frm)
        log_frame.grid(row=9, column=0, columnspan=3, sticky="nsew", **pad)
        frm.rowconfigure(9, weight=1)
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
        self._update_hint()

    def _update_hint(self):
        if self.mode_var.get() == "video":
            hint = "Vídeos vão para a pasta Vídeos (playlists numa subpasta com o nome delas)."
        elif self.quality_var.get().startswith("MP3"):
            hint = "MP3 vão para Músicas\\<Artista>\\<Música>.mp3 — cada artista na sua pasta."
        else:
            hint = "M4A vai para Outros formatos\\<Artista>\\ (separado dos MP3)."
        self.hint_var.set(hint)

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

    def _set_running(self, running):
        self.running = running
        self.download_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def _start(self):
        if self.running:
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
        self.run_id += 1
        self.cancel_event = threading.Event()
        self._set_running(True)
        self.progress["value"] = 0
        self.status_var.set("Buscando informações do link…")
        self._log(f"\n=== {url} ({quality}) ===")

        self.worker = threading.Thread(
            target=self._run, args=(self.run_id, self.cancel_event, url, mode, opts), daemon=True)
        self.worker.start()

    def _cancel(self):
        # Libera a tela na hora; o download em segundo plano para no próximo ponto de checagem
        # (normalmente em menos de 1 segundo) e apaga os arquivos incompletos.
        self.cancel_event.set()
        self.run_id += 1
        self._set_running(False)
        self.progress["value"] = 0
        self.status_var.set("Cancelado. As músicas/vídeos que já terminaram continuam na pasta.")
        self._log("Cancelado pelo usuário.")

    def _run(self, run_id, cancel, url, mode, opts):
        done, skipped = [], []
        skipped_files = set()  # nomes que o yt-dlp avisou que já estavam na pasta
        cancelled = False
        current = {"file": None}
        started = time.time()

        def emit(kind, *data):
            self.events.put((run_id, kind, *data))

        def check_cancel():
            if cancel.is_set():
                raise DownloadCancelled("cancelado pelo usuário")

        def progress_hook(d):
            check_cancel()
            info = d.get("info_dict", {})
            current["file"] = info.get("_filename") or d.get("filename")
            prefix = ""
            if info.get("playlist_index") and info.get("n_entries"):
                prefix = f"[{info['playlist_index']}/{info['n_entries']}] "
            title = info.get("musica") or info.get("title", "")
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                pct = d["downloaded_bytes"] / total * 100 if total else 0
                speed = d.get("speed")
                speed_txt = f" — {speed / 1_048_576:.1f} MB/s" if speed else ""
                emit("progress", pct, f"{prefix}Baixando: {title} ({pct:.0f}%){speed_txt}")
            elif d["status"] == "finished":
                emit("progress", 100, f"{prefix}Processando: {title}")

        def postprocessor_hook(d):
            check_cancel()
            # MoveFiles é o último passo de cada item: o arquivo final já está na pasta.
            if d["status"] == "finished" and d["postprocessor"] == "MoveFiles":
                info = d["info_dict"]
                current["file"] = None
                name = info.get("musica") or info.get("title", "?")
                if info.get("pasta_artista"):
                    name = f"{info['pasta_artista']} — {name}"
                if Path(info.get("filepath") or "").name in skipped_files:
                    skipped.append(name)
                    return
                done.append(name)
                emit("log", f"✔ {name}")

        def match_filter(info, *, incomplete=False):
            check_cancel()  # chamado antes de cada item da playlist
            return None

        try:
            # Consulta rápida (sem baixar) só para saber se o link é uma playlist.
            probe_opts = {"extract_flat": "in_playlist", "noplaylist": opts["noplaylist"],
                          "logger": QueueLogger(emit, quiet=True), "noprogress": True}
            with yt_dlp.YoutubeDL(probe_opts) as ydl:
                probe = ydl.extract_info(url, download=False)
            check_cancel()
            if probe and probe.get("_type") == "playlist":
                count = probe.get("playlist_count") or len(probe.get("entries") or [])
                emit("log", f"Playlist: {probe.get('title', '?')} ({count} itens)")
                if mode == "video":
                    opts = dict(opts, outtmpl={**opts["outtmpl"], "default": VIDEO_PLAYLIST_TMPL})

            opts = dict(opts, logger=QueueLogger(emit, on_skip=skipped_files.add), match_filter=match_filter,
                        progress_hooks=[progress_hook], postprocessor_hooks=[postprocessor_hook])
            with yt_dlp.YoutubeDL(opts) as ydl:
                if mode == "audio":
                    ydl.add_post_processor(ArtistOrganizer(), when="pre_process")
                info = ydl.extract_info(url, download=True)

            if info and info.get("_type") == "playlist":
                total = info.get("playlist_count") or len([e for e in info.get("entries") or [] if e])
                summary = f"Concluído: {len(done)} baixado(s)"
                if skipped:
                    summary += f", {len(skipped)} já existia(m)"
                failed = max(0, total - len(done) - len(skipped))
                if failed:
                    summary += f", {failed} falharam (veja o registro)"
                summary += f" — de {total} itens."
            elif done:
                summary = "Concluído!"
            elif skipped:
                summary = "Esse arquivo já estava na pasta."
            else:
                summary = "Nada foi baixado (veja o registro)."
            emit("done", summary)
        except DownloadCancelled:
            cancelled = True
        except Exception as exc:  # noqa: BLE001 — qualquer erro do yt-dlp vai para a tela
            emit("log", f"Erro: {exc}")
            emit("done", "Falhou. Veja o registro abaixo.")
        # Fora do except: assim o yt-dlp já soltou o arquivo que estava escrevendo.
        if cancelled and current["file"]:
            remove_partial_files(current["file"], started)

    def _poll_events(self):
        try:
            while True:
                run_id, kind, *data = self.events.get_nowait()
                if run_id != self.run_id:
                    continue  # evento de um download já cancelado
                if kind == "log":
                    self._log(data[0])
                elif kind == "progress":
                    self.progress["value"] = data[0]
                    self.status_var.set(data[1])
                elif kind == "done":
                    self.status_var.set(data[0])
                    self._log(data[0])
                    self._set_running(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno("Sair", "Há um download em andamento. Sair mesmo assim?"):
                return
            self.cancel_event.set()
        self.destroy()



if __name__ == "__main__":
    App().mainloop()
