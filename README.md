# grab-discography

Download an artist's full discography from YouTube Music as MP3s — with cover art and metadata baked in.

## What it does

- Opens the artist's YouTube Music channel in a headless Edge browser (Playwright)
- Collects all album links from the channel page
- Downloads every album with `yt-dlp` as MP3 (best quality, thumbnail + metadata embedded)
- Saves everything to `%USERPROFILE%\Music\<artist>\<year> - <album>\NN - <title>.mp3`

## Requirements

**Windows 11 native** — the script is Windows-only as written (`%USERPROFILE%` paths, `--windows-filenames`).

- [uv](https://docs.astral.sh/uv/) + Python 3.12+
- `yt-dlp` on the PATH
- Microsoft Edge installed — Playwright launches it headless with a fresh throwaway profile each run (never your actual browser profile)

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
