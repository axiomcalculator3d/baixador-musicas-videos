"""Textos da interface em vários idiomas.

Para adicionar um idioma: copie o bloco "en", traduza os textos e coloque o código e o nome
em LANGUAGES. Se faltar alguma chave, o texto em português é usado no lugar.
"""

import os

LANGUAGES = {"pt": "Português", "en": "English", "es": "Español"}

TEXTS = {
    "pt": {
        "app_title": "Baixador de Músicas e Vídeos",
        "subtitle": "YouTube, Spotify, SoundCloud, Instagram, TikTok… cole o link e pronto.",
        "sec_link": "LINK",
        "paste": "Colar",
        "sec_format": "FORMATO",
        "mode_video": "▶  Vídeo (MP4)",
        "mode_audio": "♪  Música / Áudio",
        "sec_quality": "QUALIDADE",
        "sec_folder": "SALVAR EM",
        "choose": "Escolher…",
        "whole_playlist": "Baixar a playlist inteira",
        "at_once": "     Itens ao mesmo tempo:",
        "download": "⬇  Baixar",
        "cancel": "✖  Cancelar",
        "open_folder": "Abrir pasta",
        "support": "♥  Apoiar",
        "status_ready": "Cole um link e clique em Baixar.",
        "status_fetching": "Buscando informações do link…",
        "status_cancelled": "Cancelado. As músicas/vídeos que já terminaram continuam na pasta.",
        "log_cancelled": "Cancelado pelo usuário.",
        "hint_video": "Vídeos vão para a pasta {videos} (playlists numa subpasta com o nome delas).",
        "hint_mp3": "MP3 vão para {music}\\<Artista>\\<Música>.mp3 — cada artista na sua pasta.",
        "hint_other": "{fmt} vai para {other}\\<Artista>\\ (separado dos MP3).",
        "hint_lossless": " A qualidade é a mesma da fonte (o YouTube não tem áudio sem perda).",
        "q_best": "Melhor disponível",
        "q_m4a": "M4A / AAC (original, sem conversão)",
        "q_opus": "OPUS (original, arquivo menor)",
        "q_ogg": "OGG Vorbis (alta qualidade)",
        "q_flac": "FLAC (sem perda, arquivo grande)",
        "q_wav": "WAV (sem compressão, arquivo enorme)",
        "folder_music": "Músicas",
        "folder_videos": "Vídeos",
        "folder_other": "Outros formatos",
        "unknown_artist": "Artista desconhecido",
        "untitled": "Sem título",
        "tools_title": "Componentes necessários",
        "tools_ask": "Para baixar do YouTube e converter os arquivos, o programa precisa de: "
                     "{tools}.\n\nInstalar agora pelo instalador oficial do Windows (winget)? "
                     "É feito uma vez só e pode levar alguns minutos.",
        "tools_installing": "Instalando {tools}… (pode levar alguns minutos)",
        "tools_done": "✔ Instalado: {tools}.",
        "tools_failed": "Não consegui instalar: {tools}. Abra o programa de novo para tentar outra vez.",
        "tools_skipped": "Sem {tools}, alguns downloads e conversões podem falhar. "
                         "Abra o programa de novo para instalar.",
        "tools_no_winget": "Faltam componentes ({tools}) e o instalador do Windows (winget) não foi "
                           "encontrado. Instale o FFmpeg e o Deno pelos sites oficiais.",
        "invalid_link_title": "Link inválido",
        "invalid_link": "Cole um link que comece com http:// ou https://",
        "quit_title": "Sair",
        "quit_running": "Há um download em andamento. Sair mesmo assim?",
        "already_existed": "↷ Já existia na pasta, pulando: {name}",
        "warning": "Aviso: {msg}",
        "downloading": "Baixando: {title} ({pct:.0f}%){speed}",
        "converting": "Convertendo: {title}",
        "ready_count": "[{done}/{total} prontos] ",
        "starting": "Começando…",
        "repeated_now": "↷ Repetida na lista (já baixada agora há pouco): {name}",
        "not_found_youtube": "Não encontrei essa música no YouTube",
        "reading_spotify": "Lendo a lista de músicas do Spotify…",
        "spotify_empty": "Esse link do Spotify não tem músicas visíveis (ele é público?)",
        "spotify_unreadable": "Não consegui ler esse link do Spotify (ele é público?)",
        "spotify_found": "Spotify: {title} ({n} música(s)) — procurando cada uma no YouTube",
        "spotify_limit": "Aviso: o Spotify só mostra as primeiras {n} músicas de um link. "
                         "Para playlists maiores, divida em playlists menores.",
        "playlist_found": "Playlist: {title} ({n} itens) — baixando {workers} por vez",
        "sequential": "Baixando a lista em ordem, um item por vez.",
        "repeated_skipped": "↷ {n} item(ns) repetido(s) na lista — cada música é baixada uma vez só.",
        "sum_done": "Concluído: {n} baixado(s)",
        "sum_skipped": ", {n} já existia(m) na pasta",
        "sum_repeated": ", {n} repetida(s) na lista",
        "sum_failed": ", {n} com erro (lista abaixo)",
        "sum_total": " — de {n} itens em {time}.",
        "done_single": "Concluído em {time}!",
        "already_single": "Esse arquivo já estava na pasta.",
        "failed": "Falhou: {reason}",
        "errors_header": "✖ Itens com erro ({n}):",
        "support_hint": "♥ O programa te ajudou? Apoie com Pix ou Bitcoin, de qualquer valor, "
                        "no botão Apoiar. Obrigado!",
        "support_window": "Apoie o projeto",
        "support_title": "♥  Apoie o Baixador",
        "support_text": "Se o programa te ajudou, considere uma contribuição de qualquer valor.\n"
                        "Isso ajuda a manter e melhorar o projeto. Obrigado!",
        "pix_scan": "Escaneie com o app do seu banco",
        "copy_pix": "Copiar Pix copia e cola",
        "copy_ln_address": "Copiar endereço Lightning",
        "copy_lnurl": "Copiar LNURL",
        "copied": "✔ Copiado!",
        "qr_missing": "(QR Code indisponível:\nrode o iniciar.bat de novo)",
        "err_private": "Vídeo privado",
        "err_members": "Só para membros do canal",
        "err_age": "Restrição de idade: o YouTube só libera para contas logadas",
        "err_bot": "O YouTube pediu verificação anti-robô: tente de novo mais tarde",
        "err_geo": "Bloqueado no seu país",
        "err_unavailable": "Vídeo indisponível ou removido",
        "err_format": "A qualidade escolhida não existe para este item",
        "err_403": "O site recusou o acesso (erro 403)",
        "err_404": "Não encontrado no site (erro 404)",
        "err_429": "O site bloqueou por excesso de pedidos: tente mais tarde",
        "err_unsupported": "Site ou link não suportado",
        "err_drm": "Protegido contra cópia (DRM): não dá para baixar",
        "err_network": "Problema de conexão com a internet",
        "err_ffmpeg": "Falha ao converter o arquivo (FFmpeg)",
        "err_unknown": "Motivo desconhecido",
        "err_ratelimit": "O YouTube limitou este computador por excesso de downloads (até 1 hora)",
        "pacing_option": "Evitar o bloqueio do YouTube (pausa sozinho perto do limite por hora)",
        "pacing_wait": "⏳ Pausa para o YouTube não bloquear: continua em {time} "
                       "(limite de ~300 vídeos por hora)",
        "pacing_big_list": "Essa lista passa do limite do YouTube por hora: quando chegar perto, "
                           "o programa pausa e continua sozinho.",
        "sum_postponed": ", {n} não tentado(s) por causa do limite do YouTube",
        "ratelimit_help": "⏸ Sem login, o YouTube aceita cerca de 300 vídeos por hora por computador. "
                          "Espere de 30 a 60 minutos e baixe a mesma lista de novo: o que já foi "
                          "baixado é pulado e só o que faltou é baixado.",
    },
    "en": {
        "app_title": "Music & Video Downloader",
        "subtitle": "YouTube, Spotify, SoundCloud, Instagram, TikTok… just paste the link.",
        "sec_link": "LINK",
        "paste": "Paste",
        "sec_format": "FORMAT",
        "mode_video": "▶  Video (MP4)",
        "mode_audio": "♪  Music / Audio",
        "sec_quality": "QUALITY",
        "sec_folder": "SAVE TO",
        "choose": "Browse…",
        "whole_playlist": "Download the whole playlist",
        "at_once": "     Items at the same time:",
        "download": "⬇  Download",
        "cancel": "✖  Cancel",
        "open_folder": "Open folder",
        "support": "♥  Support",
        "status_ready": "Paste a link and click Download.",
        "status_fetching": "Getting link information…",
        "status_cancelled": "Cancelled. Songs/videos that already finished stay in the folder.",
        "log_cancelled": "Cancelled by the user.",
        "hint_video": "Videos go to the {videos} folder (playlists in a subfolder with their name).",
        "hint_mp3": "MP3s go to {music}\\<Artist>\\<Song>.mp3 — each artist in their own folder.",
        "hint_other": "{fmt} goes to {other}\\<Artist>\\ (separate from MP3s).",
        "hint_lossless": " Quality is the same as the source (YouTube has no lossless audio).",
        "q_best": "Best available",
        "q_m4a": "M4A / AAC (original, no conversion)",
        "q_opus": "OPUS (original, smaller file)",
        "q_ogg": "OGG Vorbis (high quality)",
        "q_flac": "FLAC (lossless, large file)",
        "q_wav": "WAV (uncompressed, huge file)",
        "folder_music": "Music",
        "folder_videos": "Videos",
        "folder_other": "Other formats",
        "unknown_artist": "Unknown artist",
        "untitled": "Untitled",
        "tools_title": "Required components",
        "tools_ask": "To download from YouTube and convert files, the program needs: {tools}.\n\n"
                     "Install them now with the official Windows installer (winget)? "
                     "It only happens once and may take a few minutes.",
        "tools_installing": "Installing {tools}… (this may take a few minutes)",
        "tools_done": "✔ Installed: {tools}.",
        "tools_failed": "Couldn't install: {tools}. Open the program again to retry.",
        "tools_skipped": "Without {tools}, some downloads and conversions may fail. "
                         "Open the program again to install.",
        "tools_no_winget": "Components are missing ({tools}) and the Windows installer (winget) "
                           "wasn't found. Install FFmpeg and Deno from their official websites.",
        "invalid_link_title": "Invalid link",
        "invalid_link": "Paste a link that starts with http:// or https://",
        "quit_title": "Quit",
        "quit_running": "A download is in progress. Quit anyway?",
        "already_existed": "↷ Already in the folder, skipping: {name}",
        "warning": "Warning: {msg}",
        "downloading": "Downloading: {title} ({pct:.0f}%){speed}",
        "converting": "Converting: {title}",
        "ready_count": "[{done}/{total} done] ",
        "starting": "Starting…",
        "repeated_now": "↷ Repeated in the list (just downloaded): {name}",
        "not_found_youtube": "Couldn't find this song on YouTube",
        "reading_spotify": "Reading the Spotify track list…",
        "spotify_empty": "This Spotify link has no visible songs (is it public?)",
        "spotify_unreadable": "Couldn't read this Spotify link (is it public?)",
        "spotify_found": "Spotify: {title} ({n} song(s)) — searching each one on YouTube",
        "spotify_limit": "Warning: Spotify only shows the first {n} songs of a link. "
                         "For bigger playlists, split them into smaller ones.",
        "playlist_found": "Playlist: {title} ({n} items) — downloading {workers} at a time",
        "sequential": "Downloading the list in order, one item at a time.",
        "repeated_skipped": "↷ {n} repeated item(s) in the list — each song is downloaded only once.",
        "sum_done": "Done: {n} downloaded",
        "sum_skipped": ", {n} already in the folder",
        "sum_repeated": ", {n} repeated in the list",
        "sum_failed": ", {n} with errors (list below)",
        "sum_total": " — out of {n} items in {time}.",
        "done_single": "Done in {time}!",
        "already_single": "This file was already in the folder.",
        "failed": "Failed: {reason}",
        "errors_header": "✖ Items with errors ({n}):",
        "support_hint": "♥ Did this program help you? Support it with Pix or Bitcoin, any amount, "
                        "using the Support button. Thank you!",
        "support_window": "Support the project",
        "support_title": "♥  Support the Downloader",
        "support_text": "If this program helped you, consider a contribution of any amount.\n"
                        "It helps keep the project going and improving. Thank you!",
        "pix_scan": "Scan it with your bank app (Brazil)",
        "copy_pix": "Copy Pix code",
        "copy_ln_address": "Copy Lightning address",
        "copy_lnurl": "Copy LNURL",
        "copied": "✔ Copied!",
        "qr_missing": "(QR code unavailable:\nrun iniciar.bat again)",
        "err_private": "Private video",
        "err_members": "Channel members only",
        "err_age": "Age-restricted: YouTube only allows signed-in accounts",
        "err_bot": "YouTube asked for a bot check: try again later",
        "err_geo": "Blocked in your country",
        "err_unavailable": "Video unavailable or removed",
        "err_format": "The chosen quality isn't available for this item",
        "err_403": "The site refused access (error 403)",
        "err_404": "Not found on the site (error 404)",
        "err_429": "The site blocked too many requests: try again later",
        "err_unsupported": "Site or link not supported",
        "err_drm": "Copy-protected (DRM): can't be downloaded",
        "err_network": "Internet connection problem",
        "err_ffmpeg": "Failed to convert the file (FFmpeg)",
        "err_unknown": "Unknown reason",
        "err_ratelimit": "YouTube rate-limited this computer for too many downloads (up to 1 hour)",
        "pacing_option": "Avoid YouTube blocking (pauses by itself near the hourly limit)",
        "pacing_wait": "⏳ Pausing so YouTube won't block: resumes in {time} "
                       "(limit of ~300 videos per hour)",
        "pacing_big_list": "This list goes over YouTube's hourly limit: when it gets close, "
                           "the program pauses and resumes by itself.",
        "sum_postponed": ", {n} not tried because of YouTube's limit",
        "ratelimit_help": "⏸ Without signing in, YouTube allows about 300 videos per hour per computer. "
                          "Wait 30 to 60 minutes and download the same list again: what was already "
                          "downloaded is skipped and only what's missing is downloaded.",
    },
    "es": {
        "app_title": "Descargador de Música y Videos",
        "subtitle": "YouTube, Spotify, SoundCloud, Instagram, TikTok… pega el enlace y listo.",
        "sec_link": "ENLACE",
        "paste": "Pegar",
        "sec_format": "FORMATO",
        "mode_video": "▶  Video (MP4)",
        "mode_audio": "♪  Música / Audio",
        "sec_quality": "CALIDAD",
        "sec_folder": "GUARDAR EN",
        "choose": "Elegir…",
        "whole_playlist": "Descargar toda la lista",
        "at_once": "     Elementos a la vez:",
        "download": "⬇  Descargar",
        "cancel": "✖  Cancelar",
        "open_folder": "Abrir carpeta",
        "support": "♥  Apoyar",
        "status_ready": "Pega un enlace y haz clic en Descargar.",
        "status_fetching": "Obteniendo información del enlace…",
        "status_cancelled": "Cancelado. Las canciones/videos ya terminados se quedan en la carpeta.",
        "log_cancelled": "Cancelado por el usuario.",
        "hint_video": "Los videos van a la carpeta {videos} (las listas en una subcarpeta con su nombre).",
        "hint_mp3": "Los MP3 van a {music}\\<Artista>\\<Canción>.mp3 — cada artista en su carpeta.",
        "hint_other": "{fmt} va a {other}\\<Artista>\\ (separado de los MP3).",
        "hint_lossless": " La calidad es la misma de la fuente (YouTube no tiene audio sin pérdida).",
        "q_best": "Mejor disponible",
        "q_m4a": "M4A / AAC (original, sin conversión)",
        "q_opus": "OPUS (original, archivo más pequeño)",
        "q_ogg": "OGG Vorbis (alta calidad)",
        "q_flac": "FLAC (sin pérdida, archivo grande)",
        "q_wav": "WAV (sin compresión, archivo enorme)",
        "folder_music": "Música",
        "folder_videos": "Videos",
        "folder_other": "Otros formatos",
        "unknown_artist": "Artista desconocido",
        "untitled": "Sin título",
        "tools_title": "Componentes necesarios",
        "tools_ask": "Para descargar de YouTube y convertir los archivos, el programa necesita: "
                     "{tools}.\n\n¿Instalarlos ahora con el instalador oficial de Windows (winget)? "
                     "Se hace una sola vez y puede tardar unos minutos.",
        "tools_installing": "Instalando {tools}… (puede tardar unos minutos)",
        "tools_done": "✔ Instalado: {tools}.",
        "tools_failed": "No pude instalar: {tools}. Abre el programa de nuevo para reintentar.",
        "tools_skipped": "Sin {tools}, algunas descargas y conversiones pueden fallar. "
                         "Abre el programa de nuevo para instalar.",
        "tools_no_winget": "Faltan componentes ({tools}) y no se encontró el instalador de Windows "
                           "(winget). Instala FFmpeg y Deno desde sus sitios oficiales.",
        "invalid_link_title": "Enlace no válido",
        "invalid_link": "Pega un enlace que empiece con http:// o https://",
        "quit_title": "Salir",
        "quit_running": "Hay una descarga en curso. ¿Salir de todos modos?",
        "already_existed": "↷ Ya estaba en la carpeta, omitiendo: {name}",
        "warning": "Aviso: {msg}",
        "downloading": "Descargando: {title} ({pct:.0f}%){speed}",
        "converting": "Convirtiendo: {title}",
        "ready_count": "[{done}/{total} listos] ",
        "starting": "Comenzando…",
        "repeated_now": "↷ Repetida en la lista (recién descargada): {name}",
        "not_found_youtube": "No encontré esta canción en YouTube",
        "reading_spotify": "Leyendo la lista de canciones de Spotify…",
        "spotify_empty": "Este enlace de Spotify no tiene canciones visibles (¿es público?)",
        "spotify_unreadable": "No pude leer este enlace de Spotify (¿es público?)",
        "spotify_found": "Spotify: {title} ({n} canción(es)) — buscando cada una en YouTube",
        "spotify_limit": "Aviso: Spotify solo muestra las primeras {n} canciones de un enlace. "
                         "Para listas más grandes, divídelas en listas más pequeñas.",
        "playlist_found": "Lista: {title} ({n} elementos) — descargando {workers} a la vez",
        "sequential": "Descargando la lista en orden, un elemento a la vez.",
        "repeated_skipped": "↷ {n} elemento(s) repetido(s) en la lista — cada canción se descarga "
                            "una sola vez.",
        "sum_done": "Listo: {n} descargado(s)",
        "sum_skipped": ", {n} ya estaba(n) en la carpeta",
        "sum_repeated": ", {n} repetida(s) en la lista",
        "sum_failed": ", {n} con error (lista abajo)",
        "sum_total": " — de {n} elementos en {time}.",
        "done_single": "¡Listo en {time}!",
        "already_single": "Este archivo ya estaba en la carpeta.",
        "failed": "Falló: {reason}",
        "errors_header": "✖ Elementos con error ({n}):",
        "support_hint": "♥ ¿Te ayudó el programa? Apóyalo con Pix o Bitcoin, cualquier monto, "
                        "en el botón Apoyar. ¡Gracias!",
        "support_window": "Apoya el proyecto",
        "support_title": "♥  Apoya el Descargador",
        "support_text": "Si el programa te ayudó, considera una contribución de cualquier monto.\n"
                        "Ayuda a mantener y mejorar el proyecto. ¡Gracias!",
        "pix_scan": "Escanéalo con la app de tu banco (Brasil)",
        "copy_pix": "Copiar código Pix",
        "copy_ln_address": "Copiar dirección Lightning",
        "copy_lnurl": "Copiar LNURL",
        "copied": "✔ ¡Copiado!",
        "qr_missing": "(Código QR no disponible:\nejecuta iniciar.bat de nuevo)",
        "err_private": "Video privado",
        "err_members": "Solo para miembros del canal",
        "err_age": "Restricción de edad: YouTube solo lo permite con una cuenta iniciada",
        "err_bot": "YouTube pidió verificación anti-bot: inténtalo más tarde",
        "err_geo": "Bloqueado en tu país",
        "err_unavailable": "Video no disponible o eliminado",
        "err_format": "La calidad elegida no existe para este elemento",
        "err_403": "El sitio rechazó el acceso (error 403)",
        "err_404": "No encontrado en el sitio (error 404)",
        "err_429": "El sitio bloqueó por exceso de solicitudes: inténtalo más tarde",
        "err_unsupported": "Sitio o enlace no compatible",
        "err_drm": "Protegido contra copia (DRM): no se puede descargar",
        "err_network": "Problema de conexión a internet",
        "err_ffmpeg": "Error al convertir el archivo (FFmpeg)",
        "err_unknown": "Motivo desconocido",
        "err_ratelimit": "YouTube limitó este equipo por exceso de descargas (hasta 1 hora)",
        "pacing_option": "Evitar el bloqueo de YouTube (pausa solo cerca del límite por hora)",
        "pacing_wait": "⏳ Pausa para que YouTube no bloquee: continúa en {time} "
                       "(límite de ~300 videos por hora)",
        "pacing_big_list": "Esta lista supera el límite de YouTube por hora: cuando se acerque, "
                           "el programa pausa y continúa solo.",
        "sum_postponed": ", {n} sin intentar por el límite de YouTube",
        "ratelimit_help": "⏸ Sin iniciar sesión, YouTube permite unos 300 videos por hora por equipo. "
                          "Espera de 30 a 60 minutos y descarga la misma lista de nuevo: lo que ya se "
                          "descargó se omite y solo se descarga lo que faltó.",
    },
}

_current = "pt"


def set_language(code):
    global _current
    _current = code if code in TEXTS else "pt"


def current_language():
    return _current


def tr(key, **values):
    text = TEXTS[_current].get(key) or TEXTS["pt"][key]
    return text.format(**values) if values else text


def system_language():
    """Idioma do Windows (ou do sistema), se for um dos disponíveis; senão inglês."""
    try:
        if os.name == "nt":
            import ctypes
            import locale
            name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        else:
            name = os.environ.get("LANG", "")
    except Exception:  # noqa: BLE001 — na dúvida, inglês
        name = ""
    return name[:2] if name[:2] in TEXTS else "en"
