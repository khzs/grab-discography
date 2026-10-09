# grab-discography

Download an artist's full discography from YouTube Music as MP3s — with cover art and metadata baked in.

## What it does

- Opens the artist's YouTube Music channel in a headless Edge browser (Playwright)
- Collects all album links from the channel page
- Downloads every album with `yt-dlp` as MP3 (best quality, thumbnail + metadata embedded)
- Saves everything to `<Music>\<artist>\<year> - <album>\NN - <title>.mp3`

## Requirements

- [uv](https://docs.astral.sh/uv/) + Python 3.12+
- `yt-dlp` on the PATH (Windows: `scoop install yt-dlp` · WSL: `brew install yt-dlp`)

### Windows 11

- Microsoft Edge installed — Playwright launches it headless with a fresh throwaway profile each run (never your actual browser profile)

### Linux (WSL debian)

- system: `sudo apt install libasound2t64` — the only system package Edge needs on Debian
- local isolated Edge in `.venv/edge/` — extracted from the official .deb, no system install:

```bash
mkdir -p .venv/edge && cd .venv/edge
curl -sO https://packages.microsoft.com/repos/edge/pool/main/m/microsoft-edge-stable/microsoft-edge-stable_155.0.4283.45-1_amd64.deb
dpkg-deb -x microsoft-edge-stable_155.0.4283.45-1_amd64.deb . && rm *.deb
```

## Run environments

| | Windows 11 native | WSL |
|---|---|---|
| Browser | system Edge, headless (`channel="msedge"`), throwaway profile — never your real browser profile | local isolated Edge inside `.venv/` (see below) |
| Output folder | `%USERPROFILE%\Music\...` | `/mnt/c/Users/<you>/Music/...` — lands next to your Windows music |

## Usage

```bash
uv sync
uv run python main.py [channel_url]
```

| Parameter | Required | Description |
|---|---|---|
| `channel_url` | no | YouTube Music artist channel URL; defaults to Ours Samplus |

## Notes

- The artist name for the output folder is **hardcoded** in `main()` — change `artist_name` there when downloading a different artist.
- Albums are downloaded oldest first.
- If a cookie consent dialog pops up, it's dismissed automatically ("Reject all").
- Aborting mid-run (Ctrl-C) leaves the current `yt-dlp` download running — kill it separately.
