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
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yt_dlp
from yt_dlp.networking import Request

try:
    import qrcode
except ImportError:  # sem o pacote, a janela Apoiar mostra só os códigos em texto
    qrcode = None
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

# rótulo na tela -> (codec do FFmpeg, qualidade). Qualidade abaixo de 10 é escala VBR (0 = melhor).
AUDIO_QUALITIES = {
    "MP3 320 kbps": ("mp3", "320"),
    "MP3 256 kbps": ("mp3", "256"),
    "MP3 192 kbps": ("mp3", "192"),
    "MP3 128 kbps": ("mp3", "128"),
    "M4A / AAC (original, sem conversão)": ("m4a", None),
    "OPUS (original, arquivo menor)": ("opus", None),
    "OGG Vorbis (alta qualidade)": ("vorbis", "1"),
    "FLAC (sem perda, arquivo grande)": ("flac", None),
    "WAV (sem compressão, arquivo enorme)": ("wav", None),
}
AUDIO_EXT = {"vorbis": "ogg"}  # extensão do arquivo quando é diferente do nome do codec

# Tema escuro roxo/rosa com destaques coloridos.
THEME = {
    "bg": "#17142a",
    "card": "#221e3b",
    "field": "#2e2950",
    "border": "#433c72",
    "fg": "#f3f0ff",
    "muted": "#a59fd0",
    "primary": "#7c5cff",
    "primary_hover": "#9a80ff",
    "pink": "#ff4f8b",
    "pink_hover": "#ff75a5",
    "cyan": "#5ee0f5",
    "green": "#3ee0a1",
    "yellow": "#ffcb5c",
    "red": "#ff6b6b",
    "log_bg": "#100e1f",
}
GRADIENT = ("#6a4cff", "#b34cff", "#ff4f8b")  # faixa do topo, da esquerda para a direita
LOG_COLORS = {"ok": THEME["green"], "warn": THEME["yellow"], "error": THEME["red"],
              "info": THEME["cyan"], "cancel": THEME["pink"]}
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_BIG = ("Segoe UI", 11)
FONT_BIG_BOLD = ("Segoe UI Semibold", 12)
FONT_LABEL = ("Segoe UI Semibold", 8)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_MONO = ("Consolas", 9)
FONT_MONO_BOLD = ("Consolas", 9, "bold")

# Contribuições (janela "Apoiar"). A chave Pix é um celular, por isso o +55.
PIX_KEY = "+5538988235328"
PIX_NAME = "Francisley Campos"
PIX_CITY = "Brasil"
LIGHTNING_ADDRESS = ""  # ex.: "voce@walletofsatoshi.com"; vazio esconde a parte do Bitcoin

VIDEO_TMPL = "Vídeos/%(title).150B.%(ext)s"
VIDEO_PLAYLIST_TMPL = "Vídeos/%(playlist_title).80B/%(playlist_index)03d - %(title).150B.%(ext)s"
MP3_TMPL = "Músicas/%(pasta_artista).80B/%(musica).150B.%(ext)s"
OTHER_AUDIO_TMPL = "Outros formatos/%(pasta_artista).80B/%(musica).150B.%(ext)s"

UNKNOWN_ARTIST = "Artista desconhecido"
# "(Official Video)", "[Clipe Oficial]", "(Lyrics)", "(Áudio)"... saem do nome da música.
_NOISE = re.compile(
    r"\s*[\(\[][^\)\]]*\b(official|oficial|video|vídeo|clipe|videoclipe|lyrics?|letra|audio|áudio|"
    r"visuali[sz]er|hd|4k|mv|m/v|legendado|legenda|traduçã?o|traduzido)\b[^\)\]]*[\)\]]",
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
        if info.get("spotify_artist"):  # veio de um link do Spotify: confia nos dados de lá
            artists = [a.strip() for a in info["spotify_artist"].split(",") if a.strip()]
            artist, song = clean_artist(artists[0] if artists else ""), info["spotify_title"]
            info["artists"], info["artist"], info["track"] = artists, ", ".join(artists), song
        else:
            artist, song = guess_artist_song(info)
        info["pasta_artista"] = artist
        info["musica"] = clean_song(song)
        if not info.get("artists"):
            info["artists"] = [artist]
            info["artist"] = artist
        if not info.get("track"):
            info["track"] = song
        return [], info


SPOTIFY_LINK = re.compile(
    r"open\.spotify\.com/(?:intl-[\w-]+/)?(?:embed/)?(track|album|playlist)/([A-Za-z0-9]+)")
SPOTIFY_EMBED_LIMIT = 100  # a página pública do Spotify lista no máximo isso por link
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def read_spotify(url, ydl):
    """Lê artista e nome de cada música de um link do Spotify.

    O Spotify não deixa baixar o áudio (é protegido), mas a página pública de incorporação
    traz a lista de músicas; cada uma depois é procurada e baixada do YouTube.
    """
    kind, spotify_id = SPOTIFY_LINK.search(url).groups()
    request = Request(f"https://open.spotify.com/embed/{kind}/{spotify_id}",
                      headers={"User-Agent": BROWSER_UA})
    html = ydl.urlopen(request).read().decode("utf-8", "replace")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("Não consegui ler esse link do Spotify (ele é público?)")
    entity = json.loads(match.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    name = entity.get("name") or entity.get("title") or "Spotify"
    if kind == "track":
        tracks = [(", ".join(a["name"] for a in entity.get("artists") or []), name)]
    else:
        tracks = [(t.get("subtitle") or "", t.get("title") or "") for t in entity.get("trackList") or []]
    return kind, name, [(a.replace("\xa0", " ").strip(), t.strip()) for a, t in tracks if t]


# Mensagens do yt-dlp (em inglês) -> explicação curta para a lista de erros.
_ERROR_HINTS = [
    (r"Private video|video is private", "Vídeo privado"),
    (r"members?[- ]only|Join this channel", "Só para membros do canal"),
    (r"confirm your age|age[- ]restricted|inappropriate for some users",
     "Restrição de idade: o YouTube só libera para contas logadas"),
    (r"not a bot", "O YouTube pediu verificação anti-robô: tente de novo mais tarde"),
    (r"not available in your country|geo[- ]?restrict", "Bloqueado no seu país"),
    (r"Video unavailable|This video is unavailable|has been removed|terminated",
     "Vídeo indisponível ou removido"),
    (r"Requested format is not available", "A qualidade escolhida não existe para este item"),
    (r"HTTP Error 403", "O site recusou o acesso (erro 403)"),
    (r"HTTP Error 404", "Não encontrado no site (erro 404)"),
    (r"HTTP Error 429|Too Many Requests", "O site bloqueou por excesso de pedidos: tente mais tarde"),
    (r"Unsupported URL", "Site ou link não suportado"),
    (r"DRM", "Protegido contra cópia (DRM): não dá para baixar"),
    (r"timed out|Connection|getaddrinfo|unreachable", "Problema de conexão com a internet"),
    (r"ffmpeg|ffprobe|Postprocessing|Conversion failed", "Falha ao converter o arquivo (FFmpeg)"),
]


def explain_error(msg):
    msg = (msg or "").strip()
    for pattern, text in _ERROR_HINTS:
        if re.search(pattern, msg, re.IGNORECASE):
            return text
    msg = re.sub(r"^(ERROR:\s*)?(\[[^\]]+\]\s*)?([\w-]{6,}:\s*)?", "", msg)  # "ERROR: [site] id: "
    if not msg:
        return "Motivo desconhecido"
    return msg if len(msg) <= 150 else msg[:150] + "…"


def _emv(field_id, value):
    return f"{field_id}{len(value):02d}{value}"


def _crc16(data):
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1) & 0xFFFF
    return f"{crc:04X}"


def pix_copia_e_cola(key, name, city, description="Apoio Baixador"):
    """Código Pix "copia e cola" (BR Code do Banco Central), sem valor: quem paga escolhe."""
    def plain(text, limit):  # o padrão só aceita letras sem acento
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()[:limit]

    account = _emv("00", "br.gov.bcb.pix") + _emv("01", key) + _emv("02", description)
    payload = (_emv("00", "01") + _emv("26", account) + _emv("52", "0000") + _emv("53", "986")
               + _emv("58", "BR") + _emv("59", plain(name, 25)) + _emv("60", plain(city, 15))
               + _emv("62", _emv("05", "***")) + "6304")
    return payload + _crc16(payload)


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
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
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
        # Velocidade: o YouTube limita conexões longas; pedir o arquivo em pedaços de 10 MB
        # evita esse limite. Sites que entregam em fragmentos (HLS/DASH) baixam 4 por vez.
        "http_chunk_size": 10 * 1024 * 1024,
        "concurrent_fragment_downloads": 4,
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
        # final_ext faz o yt-dlp pular músicas que já estão na pasta, sem baixar de novo.
        opts["final_ext"] = AUDIO_EXT.get(codec, codec)
        opts["outtmpl"]["default"] = MP3_TMPL if codec == "mp3" else OTHER_AUDIO_TMPL
        # M4A e OPUS: pega o áudio que já vem nesse formato, assim não precisa converter.
        opts["format"] = {"m4a": "ba[ext=m4a]/ba/b", "opus": "ba[acodec=opus]/ba/b"}.get(codec, "ba/b")
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": kbps},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
        if codec != "wav":  # WAV não aceita capa embutida
            opts["writethumbnail"] = True
            opts["postprocessors"].append({"key": "EmbedThumbnail"})
    return opts


def path_key(path):
    """Mesmo arquivo = mesma chave, independente de maiúsculas e barras (Windows)."""
    return os.path.normcase(os.path.abspath(path))


class AlreadyInThisRun(DownloadCancelled):
    """Outro item da mesma lista já gerou este arquivo agora (música repetida na lista)."""


class ClaimTarget(PostProcessor):
    """Roda antes de baixar: reserva o arquivo final para este item.

    Se dois itens da lista dão no mesmo arquivo (a mesma música duas vezes, ou "Música
    (Clipe)" e "Música (Letra)"), o segundo é marcado como repetido em vez de "já existia".
    """

    def __init__(self, claimed, lock, final_ext):
        super().__init__()
        self.claimed, self.lock, self.final_ext = claimed, lock, final_ext

    def run(self, info):
        path = Path(info.get("_filename") or info.get("filepath") or "")
        if self.final_ext:
            path = path.with_suffix("." + self.final_ext)
        key = path_key(path)
        with self.lock:
            if key in self.claimed:
                raise AlreadyInThisRun(path.name)
            self.claimed.add(key)
        return [], info


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


def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"


def glob_escape(text):
    return re.sub(r"([\[\]\*\?])", r"[\1]", text)


class QueueLogger:
    def __init__(self, emit, quiet=False, on_skip=None, on_error=None):
        self.emit = emit
        self.quiet = quiet
        self.on_skip = on_skip
        self.on_error = on_error

    def debug(self, msg):
        # O yt-dlp manda mensagens normais por debug(); as de debug de verdade começam com [debug].
        if not self.quiet and not msg.startswith("[debug] "):
            self.info(msg)

    def info(self, msg):
        if msg.startswith(("[download] Destination", "[ExtractAudio] Destination", "[Merger]",
                           "[download] Downloading item")):
            self.emit("log", msg)
        elif msg.startswith("[download] ") and msg.endswith("has already been downloaded"):
            path = msg[len("[download] "):-len(" has already been downloaded")]
            self.emit("log", f"↷ Já existia na pasta, pulando: {Path(path).name}")
            if self.on_skip:
                self.on_skip(path_key(path))

    def warning(self, msg):
        self.emit("log", f"Aviso: {msg}")

    def error(self, msg):
        if self.on_error:
            self.on_error(msg)
        else:
            self.emit("log", msg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Baixador de Músicas e Vídeos")
        self.geometry("780x760")
        self.minsize(660, 640)

        self.events = queue.Queue()
        # Cada download tem seu próprio id e sinal de cancelamento; eventos de um download
        # cancelado são ignorados, então a tela libera na hora.
        self.run_id = 0
        self.cancel_event = threading.Event()
        self.worker = None
        self.running = False
        self.support_hint_shown = False
        self.config_data = load_config()
        self.ffmpeg_dir = find_ffmpeg()

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self.config_data.get("mode", "video"))
        self.quality_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=self.config_data.get("folder", str(DEFAULT_FOLDER)))
        self.playlist_var = tk.BooleanVar(value=True)
        self.workers_var = tk.IntVar(value=self.config_data.get("workers", 4))
        self.status_var = tk.StringVar(value="Cole um link e clique em Baixar.")
        self.hint_var = tk.StringVar()

        self._setup_style()
        self._build()
        self._dark_title_bar()
        self._on_mode_change(initial=True)
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self.ffmpeg_dir:
            self._log("FFmpeg não encontrado. Rode o iniciar.bat de novo para instalar, "
                      "senão MP3 e vídeos em alta qualidade não funcionam.")

    def _setup_style(self):
        self.configure(bg=THEME["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")  # o único tema do Windows que aceita trocar todas as cores
        field, fg, border = THEME["field"], THEME["fg"], THEME["border"]
        style.configure("TCombobox", fieldbackground=field, background=field, foreground=fg,
                        arrowcolor=fg, bordercolor=border, lightcolor=field, darkcolor=field,
                        padding=6)
        style.map("TCombobox",
                  fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
                  selectbackground=[("readonly", field)], selectforeground=[("readonly", fg)],
                  background=[("active", border), ("readonly", field)])
        self.option_add("*TCombobox*Listbox.background", field)
        self.option_add("*TCombobox*Listbox.foreground", fg)
        self.option_add("*TCombobox*Listbox.selectBackground", THEME["primary"])
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.option_add("*TCombobox*Listbox.font", FONT)
        style.configure("TSpinbox", fieldbackground=field, background=field, foreground=fg,
                        arrowcolor=fg, bordercolor=border, lightcolor=field, darkcolor=field,
                        padding=4)
        style.map("TSpinbox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
                  selectbackground=[("readonly", field)], selectforeground=[("readonly", fg)],
                  background=[("active", border), ("readonly", field)])
        for name, color in (("Accent", THEME["primary"]), ("Done", THEME["green"]),
                            ("Error", THEME["red"]), ("Cancel", THEME["pink"])):
            style.configure(f"{name}.Horizontal.TProgressbar", troughcolor=field, background=color,
                            lightcolor=color, darkcolor=color, bordercolor=THEME["bg"], thickness=14)
        for name in ("TScrollbar", "Vertical.TScrollbar"):
            style.configure(name, background=border, troughcolor=THEME["log_bg"],
                            arrowcolor=THEME["muted"], bordercolor=THEME["log_bg"],
                            lightcolor=border, darkcolor=border, gripcount=0, relief="flat")
            style.map(name, background=[("active", THEME["primary"]), ("!active", border)])

    def _dark_title_bar(self, window=None):
        """Windows 10/11: barra de título escura, combinando com a janela."""
        window = window or self
        if os.name != "nt":
            return
        try:
            import ctypes
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            dwm = ctypes.windll.dwmapi
            on = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
            r, g, b = (int(THEME["bg"][i:i + 2], 16) for i in (1, 3, 5))
            color = ctypes.c_int(r | g << 8 | b << 16)  # Windows 11: cor da barra
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
        except Exception:  # noqa: BLE001 — é só enfeite; versões antigas do Windows ignoram
            pass

    def _button(self, parent, text, command, color, hover, fg="white", **kw):
        btn = tk.Button(parent, text=text, command=command, bg=color, fg=fg, activebackground=hover,
                        activeforeground=fg, disabledforeground=THEME["muted"], relief="flat", bd=0,
                        highlightthickness=0, cursor="hand2", font=FONT_BOLD, padx=16, pady=7, **kw)
        btn.colors = (color, hover)
        btn.bind("<Enter>", lambda _e: str(btn["state"]) != "disabled" and btn.configure(bg=hover))
        btn.bind("<Leave>", lambda _e: str(btn["state"]) != "disabled" and btn.configure(bg=color))
        return btn

    @staticmethod
    def _set_enabled(btn, enabled):
        btn.configure(state="normal" if enabled else "disabled",
                      bg=btn.colors[0] if enabled else THEME["border"],
                      cursor="hand2" if enabled else "arrow")

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, bg=THEME["field"], fg=THEME["fg"],
                        insertbackground=THEME["fg"], relief="flat", font=FONT_BIG,
                        highlightthickness=2, highlightbackground=THEME["field"],
                        highlightcolor=THEME["primary"])

    def _section(self, parent, text):
        return tk.Label(parent, text=text, bg=THEME["card"], fg=THEME["muted"], font=FONT_LABEL)

    def _draw_header(self, event=None):
        canvas = self.header
        width = canvas.winfo_width()
        height = int(canvas["height"])
        canvas.delete("grad")
        stops = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in GRADIENT]
        step = 4
        for x in range(0, width, step):
            t = x / max(1, width - 1) * (len(stops) - 1)
            i = min(int(t), len(stops) - 2)
            frac = t - i
            rgb = [round(a + (b - a) * frac) for a, b in zip(stops[i], stops[i + 1])]
            color = "#%02x%02x%02x" % tuple(rgb)
            canvas.create_rectangle(x, 0, x + step, height, fill=color, outline=color, tags="grad")
        canvas.tag_lower("grad")

    def _build(self):
        self.header = tk.Canvas(self, height=84, highlightthickness=0, bd=0, bg=THEME["bg"])
        self.header.pack(fill="x")
        self.header.create_text(26, 30, anchor="w", text="♫  Baixador de Músicas e Vídeos",
                                fill="white", font=FONT_TITLE)
        self.header.create_text(28, 60, anchor="w", fill="#f5eaff", font=FONT,
                                text="YouTube, Spotify, SoundCloud, Instagram, TikTok… cole o link e pronto.")
        self.header.bind("<Configure>", self._draw_header)

        body = tk.Frame(self, bg=THEME["bg"], padx=18, pady=14)
        body.pack(fill="both", expand=True)

        card = tk.Frame(body, bg=THEME["card"], padx=18, pady=14)
        card.pack(fill="x")
        card.columnconfigure(0, weight=1)

        self._section(card, "LINK").grid(row=0, column=0, sticky="w")
        link_row = tk.Frame(card, bg=THEME["card"])
        link_row.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        url_entry = self._entry(link_row, self.url_var)
        url_entry.pack(side="left", fill="x", expand=True, ipady=6)
        url_entry.bind("<Return>", lambda _e: self._start())
        url_entry.focus_set()
        self._button(link_row, "Colar", self._paste, THEME["field"], THEME["border"],
                     fg=THEME["cyan"]).pack(side="left", padx=(8, 0))

        options_row = tk.Frame(card, bg=THEME["card"])
        options_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        format_col = tk.Frame(options_row, bg=THEME["card"])
        format_col.pack(side="left", padx=(0, 24))
        self._section(format_col, "FORMATO").pack(anchor="w")
        toggles = tk.Frame(format_col, bg=THEME["card"])
        toggles.pack(anchor="w", pady=(4, 0))
        self.mode_buttons = {}
        for value, text, color in (("video", "▶  Vídeo (MP4)", THEME["primary"]),
                                   ("audio", "♪  Música / Áudio", THEME["pink"])):
            btn = tk.Radiobutton(toggles, text=text, value=value, variable=self.mode_var,
                                 command=self._on_mode_change, indicatoron=0, selectcolor=color,
                                 bg=THEME["field"], fg=THEME["muted"], activebackground=THEME["border"],
                                 activeforeground="white", relief="flat", offrelief="flat", bd=0,
                                 highlightthickness=0, font=FONT_BOLD, padx=16, pady=7, cursor="hand2")
            btn.pack(side="left", padx=(0, 6))
            self.mode_buttons[value] = btn
        quality_col = tk.Frame(options_row, bg=THEME["card"])
        quality_col.pack(side="left", fill="x", expand=True)
        self._section(quality_col, "QUALIDADE").pack(anchor="w")
        self.quality_box = ttk.Combobox(quality_col, textvariable=self.quality_var, state="readonly",
                                        font=FONT, width=30)
        self.quality_box.pack(anchor="w", fill="x", pady=(4, 0))
        self.quality_box.bind("<<ComboboxSelected>>", lambda _e: self._update_hint())

        self._section(card, "SALVAR EM").grid(row=3, column=0, sticky="w")
        folder_row = tk.Frame(card, bg=THEME["card"])
        folder_row.grid(row=4, column=0, sticky="ew", pady=(4, 4))
        self._entry(folder_row, self.folder_var).pack(side="left", fill="x", expand=True, ipady=6)
        self._button(folder_row, "Escolher…", self._choose_folder, THEME["field"], THEME["border"],
                     fg=THEME["cyan"]).pack(side="left", padx=(8, 0))
        tk.Label(card, textvariable=self.hint_var, bg=THEME["card"], fg=THEME["cyan"],
                 font=FONT_SMALL).grid(row=5, column=0, sticky="w", pady=(0, 10))

        playlist_row = tk.Frame(card, bg=THEME["card"])
        playlist_row.grid(row=6, column=0, sticky="w")
        tk.Checkbutton(playlist_row, text="Baixar a playlist inteira", variable=self.playlist_var,
                       bg=THEME["card"], fg=THEME["fg"], selectcolor=THEME["field"],
                       activebackground=THEME["card"], activeforeground=THEME["fg"],
                       highlightthickness=0, bd=0, font=FONT, cursor="hand2").pack(side="left")
        tk.Label(playlist_row, text="     Itens ao mesmo tempo:", bg=THEME["card"], fg=THEME["muted"],
                 font=FONT).pack(side="left")
        ttk.Spinbox(playlist_row, from_=1, to=8, width=3, textvariable=self.workers_var,
                    state="readonly", font=FONT).pack(side="left", padx=6)

        actions = tk.Frame(body, bg=THEME["bg"])
        actions.pack(fill="x", pady=(14, 10))
        self.download_btn = self._button(actions, "⬇  Baixar", self._start, THEME["primary"],
                                         THEME["primary_hover"])
        self.download_btn.configure(font=FONT_BIG_BOLD, padx=28, pady=9)
        self.download_btn.pack(side="left")
        self.cancel_btn = self._button(actions, "✖  Cancelar", self._cancel, THEME["pink"],
                                       THEME["pink_hover"])
        self.cancel_btn.pack(side="left", padx=10, ipady=2)
        self._set_enabled(self.cancel_btn, False)
        self._button(actions, "Abrir pasta", self._open_folder, THEME["field"], THEME["border"],
                     fg=THEME["yellow"]).pack(side="right", ipady=2)
        self._button(actions, "♥  Apoiar", self._show_support, THEME["field"], THEME["border"],
                     fg=THEME["pink"]).pack(side="right", padx=(0, 8), ipady=2)

        self.progress = ttk.Progressbar(body, maximum=100, style="Accent.Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        tk.Label(body, textvariable=self.status_var, bg=THEME["bg"], fg=THEME["fg"], font=FONT_BOLD,
                 anchor="w").pack(fill="x", pady=(6, 8))

        log_card = tk.Frame(body, bg=THEME["log_bg"], padx=10, pady=8)
        log_card.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_card, height=10, wrap="word", state="disabled", bg=THEME["log_bg"],
                                fg=THEME["muted"], relief="flat", bd=0, highlightthickness=0,
                                font=FONT_MONO, insertbackground=THEME["fg"],
                                selectbackground=THEME["primary"])
        scroll = ttk.Scrollbar(log_card, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for tag, color in LOG_COLORS.items():
            self.log_text.tag_configure(tag, foreground=color)
        self.log_text.tag_configure("head", foreground=THEME["primary_hover"], font=FONT_MONO_BOLD)

    def _on_mode_change(self, initial=False):
        if self.mode_var.get() == "video":
            options = list(VIDEO_QUALITIES)
            saved = self.config_data.get("video_quality")
        else:
            options = list(AUDIO_QUALITIES)
            saved = self.config_data.get("audio_quality")
        for value, btn in self.mode_buttons.items():
            btn.configure(fg="white" if value == self.mode_var.get() else THEME["muted"])
        self.quality_box["values"] = options
        self.quality_var.set(saved if initial is True and saved in options else options[0])
        self._update_hint()

    def _update_hint(self):
        if self.mode_var.get() == "video":
            hint = "Vídeos vão para a pasta Vídeos (playlists numa subpasta com o nome delas)."
        elif self.quality_var.get().startswith("MP3"):
            hint = "MP3 vão para Músicas\\<Artista>\\<Música>.mp3 — cada artista na sua pasta."
        else:
            name = self.quality_var.get().split(" ")[0]
            hint = f"{name} vai para Outros formatos\\<Artista>\\ (separado dos MP3)."
            if name in ("FLAC", "WAV"):
                hint += " A qualidade é a mesma da fonte (o YouTube não tem áudio sem perda)."
        self.hint_var.set(hint)

    def _show_support(self):
        win = tk.Toplevel(self)
        win.title("Apoie o projeto")
        win.configure(bg=THEME["bg"])
        win.resizable(False, False)
        win.transient(self)
        tk.Label(win, text="♥  Apoie o Baixador", bg=THEME["bg"], fg=THEME["pink"],
                 font=FONT_TITLE).pack(padx=24, pady=(18, 4))
        tk.Label(win, text="Se o programa te ajudou, considere uma contribuição de qualquer valor.\n"
                           "Isso ajuda a manter e melhorar o projeto. Obrigado!",
                 bg=THEME["bg"], fg=THEME["fg"], font=FONT, justify="center").pack(padx=24)
        cards = tk.Frame(win, bg=THEME["bg"])
        cards.pack(padx=18, pady=(14, 6))
        feedback = tk.StringVar()
        pix = pix_copia_e_cola(PIX_KEY, PIX_NAME, PIX_CITY)
        self._support_card(cards, "Pix", pix, f"Chave (celular): {PIX_KEY}", THEME["green"], feedback,
                           [("Copiar Pix copia e cola", pix), ("Copiar chave", PIX_KEY)])
        if LIGHTNING_ADDRESS:
            self._support_card(cards, "⚡ Bitcoin Lightning", f"lightning:{LIGHTNING_ADDRESS}",
                               LIGHTNING_ADDRESS, THEME["yellow"], feedback,
                               [("Copiar endereço Lightning", LIGHTNING_ADDRESS)])
        tk.Label(win, textvariable=feedback, bg=THEME["bg"], fg=THEME["green"],
                 font=FONT_BOLD).pack(pady=(0, 14))
        if os.name == "nt":
            self.after(10, lambda: self._dark_title_bar(win))

    def _support_card(self, parent, title, qr_data, subtitle, color, feedback, copies):
        card = tk.Frame(parent, bg=THEME["card"], padx=16, pady=14)
        card.pack(side="left", padx=6, anchor="n")
        tk.Label(card, text=title, bg=THEME["card"], fg=color, font=FONT_BIG_BOLD).pack()
        self._qr_canvas(card, qr_data).pack(pady=10)
        tk.Label(card, text=subtitle, bg=THEME["card"], fg=THEME["muted"], font=FONT_SMALL).pack()
        for label, text in copies:
            self._button(card, label, lambda t=text, lb=label: self._copy(t, lb, feedback),
                         THEME["field"], THEME["border"], fg=color).pack(fill="x", pady=(6, 0))

    def _qr_canvas(self, parent, data, size=220):
        if qrcode is None:
            return tk.Label(parent, text="(QR Code indisponível:\nrode o iniciar.bat de novo)",
                            bg=THEME["card"], fg=THEME["muted"], font=FONT_SMALL)
        qr = qrcode.QRCode(border=3, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(data)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        cell = max(2, size // len(matrix))
        side = cell * len(matrix)
        canvas = tk.Canvas(parent, width=side, height=side, bg="white", highlightthickness=0)
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    canvas.create_rectangle(x * cell, y * cell, (x + 1) * cell, (y + 1) * cell,
                                            fill="black", outline="")
        return canvas

    def _copy(self, text, label, feedback):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        feedback.set(f"✔ Copiado: {label.replace('Copiar ', '')}")

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
        if msg.startswith(("\n===", "===")):
            tag = "head"
        elif msg.startswith(("✔", "Concluído")):
            tag = "ok"
        elif msg.startswith(("↷", "Aviso", "Esse arquivo")):
            tag = "warn"
        elif msg.startswith(("✖", "Erro", "ERROR", "Falhou", "FFmpeg não")):
            tag = "error"
        elif msg.startswith(("Playlist", "Baixando a lista", "Spotify")):
            tag = "info"
        elif msg.startswith(("Cancelado", "♥")):
            tag = "cancel"
        else:
            tag = ""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running(self, running):
        self.running = running
        self._set_enabled(self.download_btn, not running)
        self._set_enabled(self.cancel_btn, running)

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
        workers = max(1, min(8, self.workers_var.get()))
        self.config_data.update({"mode": mode, "folder": folder, f"{mode}_quality": quality,
                                 "workers": workers})
        save_config(self.config_data)

        opts = build_options(mode, quality, folder, self.playlist_var.get(), self.ffmpeg_dir)
        self.run_id += 1
        self.cancel_event = threading.Event()
        self._set_running(True)
        self.progress.configure(style="Accent.Horizontal.TProgressbar")
        self.progress["value"] = 0
        self.status_var.set("Buscando informações do link…")
        self._log(f"\n=== {url} ({quality}) ===")

        self.worker = threading.Thread(
            target=self._run, args=(self.run_id, self.cancel_event, url, mode, opts, workers), daemon=True)
        self.worker.start()

    def _cancel(self):
        # Libera a tela na hora; o download em segundo plano para no próximo ponto de checagem
        # (normalmente em menos de 1 segundo) e apaga os arquivos incompletos.
        self.cancel_event.set()
        self.run_id += 1
        self._set_running(False)
        self.progress.configure(style="Cancel.Horizontal.TProgressbar")
        self.progress["value"] = 100
        self.status_var.set("Cancelado. As músicas/vídeos que já terminaram continuam na pasta.")
        self._log("Cancelado pelo usuário.")

    def _run(self, run_id, cancel, url, mode, opts, workers):
        done, skipped, repeated = [], [], []
        finished = []  # itens que já terminaram, com sucesso ou não (para a barra de progresso)
        failures = []  # (posição, nome, motivo) — viram a lista de erros no final
        skipped_files = set()  # arquivos (caminho completo) que já estavam na pasta antes
        claimed, claim_lock = set(), threading.Lock()  # arquivos que algum item desta lista já pegou
        # Cada download paralelo guarda aqui o arquivo em que está mexendo, se terminou (ok)
        # e a última mensagem de erro do yt-dlp.
        local = threading.local()
        total = {"n": 1}
        started = time.time()

        def emit(kind, *data):
            self.events.put((run_id, kind, *data))

        def check_cancel():
            if cancel.is_set():
                raise DownloadCancelled("cancelado pelo usuário")

        def overall():
            """Em playlists a barra mostra quantos itens já ficaram prontos."""
            return len(finished) / total["n"] * 100, f"[{len(finished)}/{total['n']} prontos] "

        def progress_hook(d):
            check_cancel()
            info = d.get("info_dict", {})
            local.file = info.get("_filename") or d.get("filename")
            title = info.get("musica") or info.get("title", "")
            if d["status"] == "downloading":
                size = d.get("total_bytes") or d.get("total_bytes_estimate")
                pct = d["downloaded_bytes"] / size * 100 if size else 0
                speed = d.get("speed")
                speed_txt = f" — {speed / 1_048_576:.1f} MB/s" if speed else ""
                text = f"Baixando: {title} ({pct:.0f}%){speed_txt}"
            elif d["status"] == "finished":
                pct, text = 100, f"Convertendo: {title}"
            else:
                return
            if total["n"] > 1:
                pct, prefix = overall()
                text = prefix + text
            emit("progress", pct, text)

        def postprocessor_hook(d):
            check_cancel()
            # MoveFiles é o último passo de cada item: o arquivo final já está na pasta.
            if d["status"] == "finished" and d["postprocessor"] == "MoveFiles":
                info = d["info_dict"]
                local.file = None
                local.ok = True
                name = info.get("musica") or info.get("title", "?")
                if info.get("pasta_artista"):
                    name = f"{info['pasta_artista']} — {name}"
                if path_key(info.get("filepath") or "") in skipped_files:
                    skipped.append(name)
                    return
                done.append(name)
                emit("log", f"✔ {name}")

        def on_error(msg):
            local.error = msg

        def new_ydl():
            ydl = yt_dlp.YoutubeDL(dict(
                opts, logger=QueueLogger(emit, on_skip=skipped_files.add, on_error=on_error),
                progress_hooks=[progress_hook], postprocessor_hooks=[postprocessor_hook]))
            if mode == "audio":
                ydl.add_post_processor(ArtistOrganizer(), when="pre_process")
            ydl.add_post_processor(ClaimTarget(claimed, claim_lock, opts.get("final_ext")),
                                   when="before_dl")
            return ydl

        def fail(index, name, reason):
            failures.append((index, name, reason))
            emit("log", f"✖ {f'Item {index}: ' if index else ''}{name} — {reason}")

        def download_entry(index, entry, extra):
            local.file, local.ok, local.error = None, False, None
            cancelled, error = False, None
            try:
                check_cancel()
                with new_ydl() as ydl:
                    target = entry
                    if entry.get("search"):  # veio do Spotify: procura a música no YouTube
                        found = ydl.extract_info(entry["url"], download=False, process=False)
                        results = [r for r in (found or {}).get("entries") or [] if r]
                        if not results:
                            raise LookupError("Não encontrei essa música no YouTube")
                        target = results[0]
                    ydl.extract_info(target.get("url") or target.get("webpage_url"),
                                     ie_key=target.get("ie_key"), extra_info=extra)
            except AlreadyInThisRun as exc:
                local.ok = True
                repeated.append(str(exc))
                emit("log", f"↷ Repetida na lista (já baixada agora há pouco): {exc}")
            except DownloadCancelled:
                cancelled = True
            except Exception as exc:  # noqa: BLE001 — vira um item da lista de erros
                error = str(exc)
            finished.append(index)
            if not cancelled and not local.ok:
                fail(index, entry.get("title") or entry.get("url") or "?",
                     explain_error(local.error or error))
            if not cancelled and total["n"] > 1:
                pct, prefix = overall()
                emit("progress", pct, prefix.strip())
            # Fora do except: assim o yt-dlp já soltou o arquivo que estava escrevendo.
            if cancelled and local.file:
                remove_partial_files(local.file, started)

        try:
            main_ydl = new_ydl()
            entries, is_list, probe = None, True, None
            spotify = SPOTIFY_LINK.search(url)
            if spotify:
                emit("progress", 0, "Lendo a lista de músicas do Spotify…")
                kind, title, tracks = read_spotify(url, main_ydl)
                if not tracks:
                    raise ValueError("Esse link do Spotify não tem músicas visíveis (ele é público?)")
                suffix = " audio" if mode == "audio" else ""
                entries = [{"search": True, "title": f"{artist} - {song}",
                            "url": f"ytsearch1:{artist} - {song}{suffix}",
                            "extra": {"spotify_artist": artist, "spotify_title": song}}
                           for artist, song in tracks]
                is_list = kind != "track"
                emit("log", f"Spotify: {title} ({len(entries)} música(s)) — procurando cada uma no YouTube")
                if len(tracks) >= SPOTIFY_EMBED_LIMIT:
                    emit("log", f"Aviso: o Spotify só mostra as primeiras {SPOTIFY_EMBED_LIMIT} músicas "
                                "de um link. Para playlists maiores, divida em playlists menores.")
            else:
                # Busca as informações do link uma vez só (process=False: sem escolher formato
                # nem baixar). Se for um item, o mesmo ydl reaproveita essas informações no
                # download — tem que ser o mesmo, porque o YouTube recusa (403) links obtidos
                # por outra sessão.
                probe = main_ydl.extract_info(url, download=False, process=False)
                while probe and probe.get("_type") == "url":  # links curtos, redirecionamentos
                    probe = main_ydl.extract_info(probe["url"], download=False, process=False,
                                                  ie_key=probe.get("ie_key"))
                if probe and probe.get("_type") in ("playlist", "multi_video"):
                    entries = [e for e in probe.get("entries") or [] if e]
                    title = probe.get("title") or "Playlist"
                    # Itens em paralelo só quando a lista traz links (o normal no YouTube);
                    # se o site já entregou os itens prontos, baixa na ordem pelo próprio yt-dlp.
                    if all(e.get("_type") in ("url", "url_transparent") for e in entries):
                        emit("log", f"Playlist: {title} ({len(entries)} itens) — baixando {workers} por vez")
                    else:
                        entries = None
                        emit("log", "Baixando a lista em ordem, um item por vez.")
            check_cancel()

            if entries is not None:
                main_ydl.close()
                # A mesma música duas vezes na lista (comum nos "Mix" do YouTube): baixa uma vez só.
                list_size = len(entries)
                unique, seen = [], set()
                for entry in entries:
                    key = (entry.get("id") or entry.get("title") or entry.get("url") or "").lower()
                    if key and key in seen:
                        repeated.append(entry.get("title") or key)
                        continue
                    seen.add(key)
                    unique.append(entry)
                if len(unique) < len(entries):
                    emit("log", f"↷ {len(entries) - len(unique)} item(ns) repetido(s) na lista — "
                                "cada música é baixada uma vez só.")
                entries = unique
                total["n"] = max(1, len(entries))
                emit("progress", 0, f"[0/{len(entries)} prontos] Começando…")
                if mode == "video" and is_list:
                    opts = dict(opts, outtmpl={**opts["outtmpl"], "default": VIDEO_PLAYLIST_TMPL})
                list_info = {"playlist": title, "playlist_title": title,
                             "n_entries": len(entries), "playlist_count": len(entries)}
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for index, entry in enumerate(entries, 1):
                        extra = dict(entry.get("extra") or {})
                        if is_list:
                            extra.update(list_info, playlist_index=index)
                        pool.submit(download_entry, index, entry, extra)
                check_cancel()
                summary = f"Concluído: {len(done)} baixado(s)"
                if skipped:
                    summary += f", {len(skipped)} já existia(m) na pasta"
                if repeated:
                    summary += f", {len(repeated)} repetida(s) na lista"
                if failures:
                    summary += f", {len(failures)} com erro (lista abaixo)"
                summary += f" — de {list_size} itens em {format_duration(time.time() - started)}."
            else:
                local.file, local.ok, local.error = None, False, None
                cancelled, error = False, None
                try:
                    with main_ydl:
                        main_ydl.process_ie_result(probe, download=True)
                except DownloadCancelled:
                    cancelled = True
                except Exception as exc:  # noqa: BLE001 — vira a mensagem de erro abaixo
                    error = str(exc)
                if cancelled:
                    if local.file:
                        remove_partial_files(local.file, started)
                    return
                if done:
                    summary = f"Concluído em {format_duration(time.time() - started)}!"
                elif skipped:
                    summary = "Esse arquivo já estava na pasta."
                else:
                    reason = explain_error(local.error or error)
                    failures.append((None, probe.get("title") or url, reason))
                    summary = f"Falhou: {reason}"
            emit("done", summary)
            if failures and total["n"] > 1:
                emit("log", f"✖ Itens com erro ({len(failures)}):")
                for index, name, reason in sorted(failures, key=lambda f: f[0] or 0):
                    emit("log", f"✖    {index}. {name} — {reason}")
        except DownloadCancelled:
            pass
        except Exception as exc:  # noqa: BLE001 — qualquer erro do yt-dlp vai para a tela
            reason = explain_error(local.__dict__.get("error") or str(exc))
            emit("log", f"✖ {reason}")
            emit("done", f"Falhou: {reason}")

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
                    failed = data[0].startswith("Falhou")
                    self.progress.configure(
                        style=f"{'Error' if failed else 'Done'}.Horizontal.TProgressbar")
                    self.progress["value"] = 100
                    self.status_var.set(data[0])
                    self._log(data[0])
                    self._set_running(False)
                    if not failed and not self.support_hint_shown:  # uma vez por sessão
                        self.support_hint_shown = True
                        self._log("♥ O programa te ajudou? Apoie com um Pix de qualquer valor "
                                  "no botão Apoiar. Obrigado!")
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
