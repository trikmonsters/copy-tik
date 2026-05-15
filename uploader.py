import json
import time
import argparse
import requests

from pathlib import Path
from playwright.sync_api import sync_playwright

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"

VIDEO_FILE = Path("video.mp4")


def log(msg):
    print(f"[TikTok] {msg}", flush=True)


def download_video(url):

    log("⬇️ Downloading video...")

    response = requests.get(
        url,
        stream=True,
        timeout=60
    )

    response.raise_for_status()

    with open(VIDEO_FILE, "wb") as f:
        for chunk in response.iter_content(8192):
            f.write(chunk)

    log("✅ Video downloaded")

    return VIDEO_FILE


def load_cookies(path):

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cookies = []

    for c in raw:

        cookies.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "expires": int(
                c.get("expirationDate")
                or c.get("expires")
                or -1
            ),
        })

    log(f"🍪 Cookies loaded ({len(cookies)})")

    return cookies


def close_popup(page):

    popup_buttons = [
        "button:has-text('Cancel')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
    ]

    for selector in popup_buttons:

        try:

            button = page.locator(selector).first

            if button.is_visible(timeout=2000):

                button.click(force=True)

                log(f"✅ Popup closed: {selector}")

                time.sleep(1)

                return

        except:
            pass


def fill_caption(page, text):

    selectors = [
        "div.public-DraftEditor-content",
        "[data-e2e='caption-input']",
        "div[contenteditable='true']",
    ]

    for selector in selectors:

        try:

            box = page.locator(selector).first

            if not box.is_visible(timeout=3000):
                continue

            box.click(force=True)

            time.sleep(1)

            # clear
            page.keyboard.press("Control+a")
            page.keyboard.press("Delete")

            words = text.split()

            for word in words:

                # HASHTAG
                if word.startswith("#"):

                    # ketik hashtag perlahan
                    box.press_sequentially(
                        word,
                        delay=120
                    )

                    time.sleep(2)

                    # pilih suggestion hashtag
                    page.keyboard.press("Enter")

                    time.sleep(1)

                else:

                    box.press_sequentially(
                        word + " ",
                        delay=80
                    )

            time.sleep(2)

            log("✅ Caption filled")

            return True

        except Exception as e:

            log(f"⚠️ Caption failed: {e}")

            continue

    return False

def click_post(page):

    selectors = [
        "[data-e2e='post_video_button']",
        "button:has-text('Post')",
    ]

    for selector in selectors:

        try:

            button = page.locator(selector).first

            if not button.is_visible(timeout=3000):
                continue

            disabled = button.get_attribute("disabled")

            if disabled is not None:
                continue

            button.click(force=True)

            log("✅ Post button clicked")

            return True

        except:
            pass

    return False


def upload_video(url, cookies_path, caption, headless=True):

    download_video(url)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = browser.new_context(
            viewport={
                "width": 1400,
                "height": 900
            }
        )

        context.add_cookies(
            load_cookies(cookies_path)
        )

        page = context.new_page()

        log("🌐 Opening TikTok upload page...")

        page.goto(
            TIKTOK_UPLOAD_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        time.sleep(5)

        if "login" in page.url.lower():
            raise Exception("❌ Login failed")

        log("✅ Login success")

        close_popup(page)

        log("📤 Uploading video...")

        page.locator(
            "input[type='file']"
        ).first.set_input_files(
            str(VIDEO_FILE.resolve())
        )

        log("⏳ Waiting upload process...")

        time.sleep(25)

        close_popup(page)

        fill_caption(page, caption)

        time.sleep(2)

        click_post(page)

        log("⏳ Waiting post process...")

        time.sleep(15)

        log("🎉 Upload success")

        browser.close()


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--url", required=True)

    parser.add_argument("--cookies", default="cookies.json")

    parser.add_argument(
        "--description",
        default="Video keren! #fyp #viral"
    )

    parser.add_argument(
        "--headless",
        action="store_true"
    )

    args = parser.parse_args()

    upload_video(
        args.url,
        args.cookies,
        args.description,
        args.headless
    )


if __name__ == "__main__":
    main()
