# grab-discography

Download an artist's full discography from YouTube Music as MP3s — with cover art and metadata baked in.

Runs in WSL (Debian). Browser and Python env stay local to the project; downloads land in your Windows Music folder.

## What it does

Two modes, **auto-detected from the shape of the URL** — no flags needed.

**Discography** — scrapes the artist's channel and grabs every album:

- Opens the artist's YouTube Music channel in a headless Edge browser (Playwright)
- Collects all album links from the channel page
- Downloads every album with `yt-dlp` as MP3 (best quality, thumbnail + metadata embedded)
- Saves everything to `/mnt/c/Users/<you>/Music/<artist>/<year> - <album>/NN - <title>.mp3`

**Single album** — grabs just one album (no browser involved):

- Reads artist / album / year from the tracks' metadata via `yt-dlp`
- Saves everything to `/mnt/c/Users/<you>/Music/<artist> - <year> - <album>/NN - <title>.mp3`

## Requirements

- [uv](https://docs.astral.sh/uv/) + Python 3.12+
- `yt-dlp` on the PATH (`brew install yt-dlp`)
- system: `sudo apt install libasound2t64` — the only system package Edge needs on Debian
- local isolated Edge in `.venv/edge/` — extracted from the official .deb, no system install:

```bash
mkdir -p .venv/edge && cd .venv/edge
curl -sO https://packages.microsoft.com/repos/edge/pool/main/m/microsoft-edge-stable/microsoft-edge-stable_155.0.4283.45-1_amd64.deb
dpkg-deb -x microsoft-edge-stable_155.0.4283.45-1_amd64.deb . && rm *.deb
```

## Usage

```bash
uv sync
uv run python main.py [url]
```

The mode is picked from the URL:

| URL shape | Mode | Output |
|---|---|---|
| `music.youtube.com/@artist` or `.../channel/UC...` | discography | `Music/<Artist>/<Year> - <Album>/NN - <Title>.mp3` |
| `music.youtube.com/browse/MPREb_...` | single album | `Music/<Artist> - <Year> - <Album>/NN - <Title>.mp3` |
| `music.youtube.com/playlist?list=OLAK5uy_...` (shared album link) | single album | same |
| `music.youtube.com/watch?v=...&list=OLAK5uy_...` (track inside album view) | single album | same |

Anything else — plain `youtube.com`/`m.youtube.com` hosts get rewritten to `music.youtube.com`, and the raw `browse/MPREb_...` hrefs that discography mode prints can be passed as-is (grab one album from a channel without re-scraping). Regular playlists (`list=PL...`), single tracks and non-YouTube URLs abort with a usage message.

## Notes

- The artist name is read from the channel page itself (`og:title`) — no hardcoded name, no extra `yt-dlp` call. In single-album mode it comes from the tracks' embedded metadata instead.
- Invalid/stale URLs abort with an error instead of downloading into a wrong folder.
- Folder names are sanitized for Windows (an `AC/DC` won't nest two folders).
- Track numbers are the zero-padded positions in the album (`NN - Title.mp3`).
- Albums are downloaded oldest first.
- If a cookie consent dialog pops up, it's dismissed automatically ("Reject all").
- YouTube sometimes rate-limits a download mid-album (`HTTP 403` on individual tracks). Each album is retried up to 3 times with a minute's pause — a re-run skips already-downloaded tracks, so only the missing ones are picked up. Albums that still fail are listed at the end (discography mode) / flagged with a non-zero exit (single-album mode); re-run the same URL later to resume.
- Aborting mid-run (Ctrl-C) leaves the current `yt-dlp` download running — kill it separately.
