import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_DIR = Path(__file__).parent.resolve()
LOCAL_EDGE = PROJECT_DIR / ".venv" / "edge" / "opt" / "microsoft" / "msedge" / "msedge"
WSL_MUSIC_BASE = "/mnt/c/Users/khzso/Music"


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
    return last_line


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


def get_album_href_list(url: str):
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
    return hrefs


def main():
    url = ""
    if len(sys.argv) != 2:
        url = "https://music.youtube.com/channel/UCaREzwA3QTe95YCYx9jGqfQ"
    else:
        url = sys.argv[1]

    print("step 1")
    hrefs = get_album_href_list(url)

    print("step 2")
    # TODO : this is very inefficient like this
    # artist_name = execute_cmd_get_last_line(f'yt-dlp --print "%(artist)s" "https://music.youtube.com/{hrefs[0]}"')
    artist_name = "Ours Samplus"
    music_output_folder = f"{WSL_MUSIC_BASE}/{artist_name}"
    execute_cmd_get_last_line(f'mkdir -p "{music_output_folder}"')

    print("step 3")
    for href in reversed(hrefs):
        print(href)
        execute_cmd_get_last_line(f'yt-dlp "https://music.youtube.com/{href}"   -f bestaudio   -x --audio-format mp3 --audio-quality 0   --embed-thumbnail   --embed-metadata   --parse-metadata "playlist_index:%(track_number)s"   --add-metadata  --windows-filenames  --output "{music_output_folder}/%(release_year)s - %(album)s/%(playlist_index)02d - %(title)s.%(ext)s" ')


if __name__ == "__main__":
    main()
