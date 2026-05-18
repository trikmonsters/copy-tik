"""
TikTok Draft Uploader
Upload video -> isi caption -> save draft -> close browser
"""

import sys
import json
import time
import random
import requests
import argparse

from pathlib import Path
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeout
)

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"

VIDEO_FILE = Path("video.mp4")


def log(msg: str):
    print(f"[TikTok Draft Uploader] {msg}", flush=True)


def human_delay(a=0.8, b=2.5):
    time.sleep(random.uniform(a, b))


def download_video(url: str, output: Path):
    log(f"⬇️ Download video: {url}")

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )

    response.raise_for_status()

    with open(output, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    size_mb = output.stat().st_size / (1024 * 1024)

    log(f"✅ Download selesai ({size_mb:.1f} MB)")


def parse_cookies(cookies_path: str) -> list:
    with open(cookies_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    cookies = []

    if content.startswith("["):
        raw = json.loads(content)

        for c in raw:
            expiry = c.get("expirationDate") or c.get("expires") or -1

            cookies.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
                "expires": int(expiry),
                "httpOnly": c.get("httpOnly", False),
            })

        log(f"🍪 Cookies dimuat ({len(cookies)})")

    else:
        raise Exception("❌ Gunakan cookies format JSON")

    return cookies


def goto_with_retry(page, url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            log(f"🌐 Membuka halaman ({attempt}/{retries})")

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            human_delay(3, 5)

            return

        except PlaywrightTimeout:
            log(f"⚠️ Timeout percobaan {attempt}")

            human_delay(2, 4)

    raise Exception("❌ Gagal membuka halaman")


def close_modal(page):
    close_selectors = [
        "[data-e2e='modal-close-inner-button']",
        "button[aria-label='Close']",
        "button:has-text('Close')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "button:has-text('Cancel')",
    ]

    for sel in close_selectors:
        try:
            btn = page.locator(sel).first

            if btn.is_visible(timeout=1500):
                btn.click(force=True)

                log(f"✅ Modal ditutup via: {sel}")

                human_delay(1, 2)

                return True

        except:
            continue

    return False


def handle_content_check_popup(page):
    try:
        popup_selectors = [
            "text=Turn on automatic content checks",
            "text=Music copyright check",
            "text=Content check lite",
        ]

        popup_found = False

        for sel in popup_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=3000):
                    popup_found = True
                    break
            except:
                continue

        if not popup_found:
            return False

        cancel_selectors = [
            "button:has-text('Cancel')",
            "button:has-text('Skip')",
            "button:has-text('Not now')",
        ]

        for sel in cancel_selectors:
            try:
                btn = page.locator(sel).first

                if btn.is_visible(timeout=3000):
                    btn.click(force=True)

                    log(f"✅ Popup ditutup via: {sel}")

                    human_delay(1, 2)

                    return True

            except:
                continue

        page.keyboard.press("Escape")

        return True

    except:
        return False


def find_upload_input(page):
    log("🔍 Mencari file input...")

    file_input = page.locator(
        "input[type='file']"
    ).first

    file_input.wait_for(
        state="attached",
        timeout=15000
    )

    log("✅ File input ditemukan")

    return file_input


def wait_for_upload_complete(page, timeout=180):
    log("⏳ Menunggu upload selesai...")

    start = time.time()

    progress_selectors = [
        "[class*='progress']",
        "[class*='uploading']",
        "[class*='Progress']",
    ]

    while time.time() - start < timeout:
        uploading = False

        for sel in progress_selectors:
            try:
                if page.locator(sel).count() > 0:
                    uploading = True
                    break
            except:
                pass

        if not uploading:
            log("✅ Upload selesai")
            break

        human_delay(1, 2)

    human_delay(4, 6)


def fill_caption(page, text):
    selectors = [
        "div.public-DraftEditor-content",
        "[data-e2e='caption-input']",
        "div[contenteditable='true']",
    ]

    for selector in selectors:
        try:
            box = page.locator(selector).first

            if not box.is_visible(timeout=5000):
                continue

            box.click(force=True)

            human_delay(1, 2)

            page.keyboard.press("Control+a")

            human_delay(0.5, 1)

            page.keyboard.press("Backspace")

            human_delay(1, 2)

            words = text.split()

            for word in words:
                if word.startswith("#"):
                    page.keyboard.press("Space")

                    box.press_sequentially(
                        word,
                        delay=random.randint(70, 130)
                    )

                    human_delay(0.5, 1)

                    page.keyboard.press("Enter")

                else:
                    box.press_sequentially(
                        word + " ",
                        delay=random.randint(50, 110)
                    )

            log("✅ Caption berhasil diisi")

            return True

        except Exception as e:
            log(f"⚠️ Caption gagal: {e}")

            continue

    return False


def click_draft_button(page):
    log("📂 Mencari tombol Draft...")

    selectors = [
        "button:has-text('Draft')",
        "button:has-text('Save draft')",
        "[data-e2e='save-draft-button']",
    ]

    for sel in selectors:
        try:
            btn = page.locator(sel).first

            if not btn.is_visible(timeout=5000):
                continue

            disabled = btn.get_attribute("disabled")

            if disabled is not None:
                log("⏳ Tombol Draft masih disabled")
                continue

            btn.scroll_into_view_if_needed()

            human_delay(1, 2)

            try:
                btn.click(timeout=5000)
            except:
                btn.click(force=True)

            log(f"✅ Draft diklik via: {sel}")

            return True

        except:
            continue

    return False


def upload_to_tiktok(
    video_path,
    cookies_path,
    description=""
):
    with sync_playwright() as p:

        log("🌐 Membuka browser...")

        browser = p.chromium.launch(
            headless=False,
            slow_mo=random.randint(50, 120),
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ]
        )

        context = browser.new_context(
            viewport={
                "width": 1366,
                "height": 768
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Jakarta",
            color_scheme="light",
        )

        log(f"🍪 Memuat cookies: {cookies_path}")

        cookies = parse_cookies(cookies_path)

        context.add_cookies(cookies)

        page = context.new_page()

        # langsung ke upload
        goto_with_retry(page, TIKTOK_UPLOAD_URL)

        if "login" in page.url.lower():
            raise Exception("❌ Login gagal, cookies invalid")

        log("✅ Login berhasil")

        close_modal(page)

        file_input = find_upload_input(page)

        log(f"📤 Uploading: {video_path}")

        file_input.set_input_files(
            str(video_path.resolve())
        )

        human_delay(3, 5)

        wait_for_upload_complete(page)

        close_modal(page)

        handle_content_check_popup(page)

        if description:
            fill_caption(page, description)

            human_delay(2, 3)

        # save draft
        drafted = click_draft_button(page)

        if drafted:
            log("⏳ Menunggu save draft...")

            human_delay(8, 15)

            log("✅ VIDEO BERHASIL MASUK DRAFT")

        else:
            log("❌ Tombol Draft gagal ditemukan")

        human_delay(3, 5)

        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Draft Uploader"
    )

    parser.add_argument(
        "--url",
        required=True,
        help="URL video"
    )

    parser.add_argument(
        "--cookies",
        default="cookies.json",
        help="Path cookies JSON"
    )

    parser.add_argument(
        "--description",
        default="Video keren 🚀 #fyp #viral",
        help="Caption video"
    )

    args = parser.parse_args()

    if not Path(args.cookies).exists():
        log(f"❌ Cookies tidak ditemukan: {args.cookies}")
        sys.exit(1)

    download_video(
        args.url,
        VIDEO_FILE
    )

    upload_to_tiktok(
        VIDEO_FILE,
        args.cookies,
        args.description
    )


if __name__ == "__main__":
    main()
