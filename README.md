# Baixador de Músicas e Vídeos

Programa simples para Windows: cole um link, escolha **vídeo** ou **música** e a **qualidade**, e clique em **Baixar**.
Se o link for de uma **playlist**, ele baixa todos os itens para uma pasta com o nome da playlist, numerados na ordem.

Funciona com YouTube, YouTube Music, SoundCloud, Vimeo, Instagram, TikTok, X/Twitter e
[centenas de outros sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) (usa o [yt-dlp](https://github.com/yt-dlp/yt-dlp) por baixo).

## Como usar

1. Baixe o projeto: botão verde **Code → Download ZIP** aqui no GitHub e extraia
   (ou `git clone` este repositório).
2. Dê dois cliques em **`iniciar.bat`**.
   - Na primeira vez ele instala o que falta (Python, yt-dlp e FFmpeg) — demora um pouco.
   - Nas próximas, só atualiza o yt-dlp e abre o programa.
3. Cole o link, escolha formato e qualidade e clique em **Baixar**.

> Dica: extraia numa pasta com caminho curto (ex.: `Área de Trabalho\Baixador`). O Windows
> tem limite de tamanho de caminho e pastas muito profundas podem quebrar a instalação.

## Opções

| Formato | Qualidades |
|---|---|
| Vídeo (MP4) | Melhor disponível, 4K, 2K, 1080p, 720p, 480p, 360p |
| Música / Áudio | MP3 320 / 192 / 128 kbps, M4A original (sem perda por conversão) |

- Se o vídeo não tiver a qualidade escolhida, ele pega a maior disponível abaixo dela.
- MP3/M4A já saem com capa e título/artista embutidos.
- Arquivos vão por padrão para `Downloads\Baixador` (dá para trocar no programa; ele lembra a última escolha).
- Em playlists, se um item falhar (privado, removido), os outros continuam.
- Desmarque "baixar a playlist inteira" para baixar só o vídeo de um link do tipo `watch?v=...&list=...`.

## Problemas comuns

- **Parou de funcionar num site**: os sites mudam com frequência. Feche e abra pelo `iniciar.bat`,
  que atualiza o yt-dlp automaticamente.
- **"FFmpeg não encontrado"**: rode o `iniciar.bat` de novo, ou instale com `winget install Gyan.FFmpeg`.

## Uso responsável

Baixe apenas conteúdo que você tem direito de baixar (seu, de domínio público, licenciado
ou permitido pelo autor) e respeite os termos de uso de cada site.
