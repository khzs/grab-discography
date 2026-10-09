# grab-discography

Download an artist's full discography from YouTube Music as MP3s — with cover art and metadata baked in.

Runs in WSL (Debian). Browser and Python env stay local to the project; downloads land in your Windows Music folder.

## What it does

- Opens the artist's YouTube Music channel in a headless Edge browser (Playwright)
- Collects all album links from the channel page
- Downloads every album with `yt-dlp` as MP3 (best quality, thumbnail + metadata embedded)
- Saves everything to `/mnt/c/Users/<you>/Music/<artist>/<year> - <album>/NN - <title>.mp3`

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
uv run python main.py [channel_url]
```

| Parameter | Required | Description |
|---|---|---|
| `channel_url` | yes | YouTube Music artist channel URL; both `@Handle` and old-style `channel/UC...` forms work |

## Notes

- The artist name is read from the channel page itself (`og:title`) — no hardcoded name, no extra `yt-dlp` call.
- Invalid/stale channel URLs abort with an error instead of downloading into a wrong folder.
- Albums are downloaded oldest first.
- If a cookie consent dialog pops up, it's dismissed automatically ("Reject all").
- Aborting mid-run (Ctrl-C) leaves the current `yt-dlp` download running — kill it separately.
