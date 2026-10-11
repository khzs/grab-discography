import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

PROJECT_DIR = Path(__file__).parent.resolve()
LOCAL_EDGE = PROJECT_DIR / ".venv" / "edge" / "opt" / "microsoft" / "msedge" / "msedge"
WSL_MUSIC_BASE = "/mnt/c/Users/khzso/Music"
MUSIC_BASE_URL = "https://music.youtube.com"

YTDLP_AUDIO_FLAGS = (
    "-f bestaudio   -x --audio-format mp3 --audio-quality 0   --embed-thumbnail   "
    '--embed-metadata   --parse-metadata "playlist_index:%(track_number)s"   '
    "--add-metadata  --windows-filenames"
)

USAGE = f"""usage: python main.py <url>

mode is auto-detected from the URL:
  channel discography:  {MUSIC_BASE_URL}/@handle  or  {MUSIC_BASE_URL}/channel/UC...
  single album:         {MUSIC_BASE_URL}/browse/MPREb_...
                        {MUSIC_BASE_URL}/playlist?list=OLAK5uy_...
                        {MUSIC_BASE_URL}/watch?v=...&list=OLAK5uy_...  (rewritten to playlist)
"""


def sanitize_for_windows(name: str) -> str:
    name = re.sub(r"[<>:\"/\\|?*]", "_", str(name))
    name = name.strip().rstrip(" .")  # Windows dislikes trailing dots/spaces too
    return name or "Unknown"


def classify_url(arg: str):
    if not re.match(r"^https?://", arg, re.IGNORECASE):
        # bare href, e.g. "browse/MPREb_..." as printed by discography mode
        arg = f"{MUSIC_BASE_URL}/{arg.lstrip('/')}"

    parsed = urlparse(arg)
    if parsed.netloc.lower() not in ("music.youtube.com", "youtube.com", "www.youtube.com", "m.youtube.com"):
        sys.exit(f"ERROR: not a YouTube Music URL: {arg}\n\n{USAGE}")

    path = parsed.path.rstrip("/")
    list_id = (parse_qs(parsed.query).get("list") or [""])[0]

    # --- single album ------------------------------------------------------
    # an album page, or a track watched inside its album (list= is then the album)
    m = re.fullmatch(r"/browse/(MP[\w-]+)", path)
    if m:
        return "album", f"{MUSIC_BASE_URL}/browse/{m.group(1)}"
    if path == "/playlist" and list_id.startswith("OLAK5uy"):
        return "album", f"{MUSIC_BASE_URL}/playlist?list={list_id}"
    if path == "/watch" and list_id.startswith("OLAK5uy"):
        return "album", f"{MUSIC_BASE_URL}/playlist?list={list_id}"

    # --- channel discography ----------------------------------------------
    if re.match(r"^/(@[\w.\-]+|channel/[\w\-]+)", path):
        return "channel", f"{MUSIC_BASE_URL}{path}"

    sys.exit(f"ERROR: unrecognized URL : {arg}\n\n{USAGE}")


def probe_album_metadata(url: str):
    """Return (artist, album, year) from an album's track metadata."""
    result = subprocess.run(
        f'yt-dlp --skip-download --playlist-items 1:5 --dump-single-json "{url}"',
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: could not read album metadata via yt-dlp:\n{result.stderr.strip()}")

    data = json.loads(result.stdout)
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        artist, album, year = entry.get("artist"), entry.get("album"), entry.get("release_year")
        if artist and album and year:
            return artist, album, int(year)

    sys.exit("ERROR: the tracks carry no artist/album/release-year metadata - is this URL really a YouTube Music album?")


def execute_cmd_get_last_line(command):
    # result = subprocess.run(command, shell=True, capture_output=True, text=True)
    # if result.stdout:
    #     last_line = result.stdout.strip().splitlines()[-1]
    #     print(last_line)
    #     return last_line
    # return None
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
    last_line = None
    for line in process.stdout:
        print(line, end="", flush=True)
        if line.strip():
            last_line = line.strip()
    process.wait()
    return process.returncode, last_line


def get_artist_name(page):
    # Wait for the page to settle: og:title is server-rendered for @handle urls, but on channel/UC... urls
    # it hydrates as 'undefined' first and only gets filled in when the SPA has resolved the channel.
    try:
        page.wait_for_function(
            """() => {
                const og = document.querySelector('meta[property="og:title"]')?.content;
                const t = document.title;
                return (og && og !== 'undefined' && og.trim())
                    || (t && t !== 'YouTube Music' && t.trim());
            }""",
            timeout=30000,
        )
    except Exception:
        pass  # fall through and check what we did get

    candidates = []

    try:
        candidates.append(
            page.locator('meta[property="og:title"]').first.get_attribute("content", timeout=5000)
        )
    except Exception:
        pass

    try:
        candidates.append(page.title())
    except Exception:
        pass

    for name in candidates:
        name = (name or "").strip()
        # document.title may come with a " - YouTube Music" suffix
        name = re.sub(r"\s*-\s*YouTube( Music)?\s*$", "", name)
        if name and name.lower() not in ("undefined", "youtube music"):
            return name
    sys.exit("ERROR: could not determine artist name - is the channel URL valid?")


def get_album_shelf(page):
    # Gate: some channels hydrate slowly - wait for any shelf to render first.
    page.wait_for_selector("ytmusic-carousel-shelf-renderer", timeout=45000)

    albums = page.locator(
        "ytmusic-carousel-shelf-renderer",
        has=page.locator("ytmusic-carousel-shelf-basic-header-renderer", has_text="Albums"),
    )
    try:
        albums.first.wait_for(timeout=10000)
        return albums.first
    except Exception:
        pass
    # fallback: any carousel shelf that has browse links
    any_shelf = page.locator(
        "ytmusic-carousel-shelf-renderer", has=page.locator("a[href^='browse/']")
    )
    any_shelf.first.wait_for(timeout=10000)
    return any_shelf.first


def scrape_channel(url: str):
    """Scrape a YT Music artist channel. Returns (artist_name, [album browse hrefs])."""
    hrefs = []
    with sync_playwright() as p:
        # Create an isolated temp profile
        user_data_dir = tempfile.mkdtemp()

        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=str(LOCAL_EDGE),
                headless=True,
                locale="en-US",
            )

            page = browser.new_page()
            page.goto(url)

            # Handle cookie consent "Reject all" if it appears
            try:
                page.get_by_role("button", name="Reject all").click(timeout=3000)
                page.wait_for_load_state("networkidle")
            except Exception:
                pass

            artist_name = get_artist_name(page)

            # 1. Select the Albums carousel shelf (heading-anchored, see get_album_shelf)
            shelf = get_album_shelf(page)

            # 2. Drill down until <ul id="items">
            ul_items = shelf.locator("ul#items")
            ul_items.wait_for()

            # 3. Direct children
            items = ul_items.locator(":scope > ytmusic-two-row-item-renderer")
            count = items.count()
            print(f"Found {count} items")

            # 4. Extract href from each item
            for i in range(count):
                item = items.nth(i)
                link = item.locator("a[href^='browse/']").first
                href = link.get_attribute("href")
                print(f"{i}: {href}")
                hrefs.append(href)

            browser.close()
        finally:
            shutil.rmtree(user_data_dir)
    return artist_name, hrefs


def download_album(url: str, output_dir: str) -> bool:
    command = (
        f'yt-dlp "{url}" {YTDLP_AUDIO_FLAGS} '
        f'--output "{output_dir}/%(playlist_index)02d - %(title)s.%(ext)s" '
    )
    for attempt in range(1, 4):
        rc, _ = execute_cmd_get_last_line(command)
        if rc == 0:
            return True
        if attempt < 3:
            print(f"\nERROR: yt-dlp exit {rc} - YouTube may be rate limiting; retrying in 60s\n")
            time.sleep(60)
    print(f"\nWARNING: {url} still failing after 3 attempts - re-run later to resume\n")
    return False


def grab_single_album(url: str):
    """Download one album to <Music>/<Artist> - <Year> - <Album>/<NN> - <Title>.mp3."""
    print("step 1  reading album metadata")
    artist, album, year = probe_album_metadata(url)
    print(f"        {artist} - {year} - {album}")

    print("step 2")
    album_dir = f"{WSL_MUSIC_BASE}/{sanitize_for_windows(artist)} - {year} - {sanitize_for_windows(album)}"
    execute_cmd_get_last_line(f'mkdir -p "{album_dir}"')

    print("step 3")
    if not download_album(url, album_dir):
        sys.exit(1)


def grab_discography(channel_url: str):
    """Download a channel's full discography to <Music>/<Artist>/<Year> - <Album>/<NN> - <Title>.mp3."""
    print("step 1")
    artist_name, hrefs = scrape_channel(channel_url)

    print("step 2")
    music_output_folder = f"{WSL_MUSIC_BASE}/{sanitize_for_windows(artist_name)}"
    execute_cmd_get_last_line(f'mkdir -p "{music_output_folder}"')

    print("step 3")
    failed = []
    for href in reversed(hrefs):
        print(href)
        if not download_album(f"{MUSIC_BASE_URL}/{href}", f"{music_output_folder}/%(release_year)s - %(album)s"):
            failed.append(href)

    if failed:
        print(f"\n{len(failed)} album(s) incomplete - re-run later to resume:")
        for href in failed:
            print(f"  {MUSIC_BASE_URL}/{href}")


def main():
    if len(sys.argv) != 2:
        sys.exit(USAGE)

    mode, url = classify_url(sys.argv[1])
    print(f"mode: {mode}\nurl:  {url}\n")

    if mode == "album":
        grab_single_album(url)
    else:
        grab_discography(url)


if __name__ == "__main__":
    main()
