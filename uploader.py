"""
TikTok Uploader - Stable Version
Upload video dari URL ke TikTok menggunakan Playwright
Support cookies JSON + handle content check popup
"""

import os
import sys
import json
import time
import requests
import argparse

from pathlib import Path
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeout
)

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"

SCREENSHOT_DIR = Path("screenshots")
VIDEO_FILE = Path("video.mp4")


def log(msg: str):
    print(f"[TikTok Uploader] {msg}", flush=True)


def screenshot(page, name: str):
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    path = SCREENSHOT_DIR / f"{name}.png"

    page.screenshot(
        path=str(path),
        full_page=False
    )

    log(f"📸 Screenshot disimpan: {path}")


def download_video(url: str, output: Path):

    log(f"⬇️ Mendownload video dari: {url}")

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )

    response.raise_for_status()

    with open(output, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = output.stat().st_size / (1024 * 1024)

    log(f"✅ Video berhasil didownload ({size_mb:.1f} MB)")


def parse_cookies(cookies_path: str) -> list:

    with open(cookies_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    cookies = []

    # JSON FORMAT
    if content.startswith("["):

        raw = json.loads(content)

        for c in raw:

            expiry = (
                c.get("expirationDate")
                or c.get("expires")
                or -1
            )

            cookies.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
                "expires": int(expiry),
                "httpOnly": c.get("httpOnly", False),
            })

        log(f"🍪 JSON cookies dimuat ({len(cookies)})")

    else:
        raise Exception("❌ Gunakan format cookies JSON")

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

            time.sleep(5)

            return

        except PlaywrightTimeout:

            log(f"⚠️ Timeout percobaan {attempt}")

            time.sleep(3)

    raise Exception(f"❌ Gagal membuka halaman")


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

                time.sleep(1)

                return True

        except Exception:
            continue

    return False


def handle_content_check_popup(page):

    try:

        log("🔍 Memeriksa popup content check...")

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

            log("✅ Tidak ada popup content check")

            return False

        screenshot(page, "popup_content_check")

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

                    time.sleep(2)

                    screenshot(page, "popup_closed")

                    return True

            except:
                continue

        page.keyboard.press("Escape")

        log("✅ Popup ditutup via Escape")

        time.sleep(2)

        return True

    except Exception as e:

        log(f"⚠️ Error popup: {e}")

        return False


def find_upload_input(page):

    log("🔍 Mencari input upload...")

    try:

        file_input = page.locator(
            "input[type='file']"
        ).first

        file_input.wait_for(
            state="attached",
            timeout=15000
        )

        log("✅ File input ditemukan")

        return file_input

    except Exception as e:

        raise Exception(
            f"❌ Input upload tidak ditemukan: {e}"
        )


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

        time.sleep(2)

    time.sleep(5)


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

            time.sleep(1)

            # CLEAR ALL EXISTING TEXT
            page.keyboard.press("Control+a")

            time.sleep(0.5)

            page.keyboard.press("Backspace")

            time.sleep(1)

            words = text.split()

            for word in words:

                # ─────────────────────────────
                # HASHTAG
                # ─────────────────────────────
                if word.startswith("#"):

                    # important spacing
                    page.keyboard.press("Space")

                    box.press_sequentially(
                        word,
                        delay=120
                    )

                    time.sleep(2)

                    # activate hashtag
                    page.keyboard.press("Enter")

                    time.sleep(1)

                    # IMPORTANT:
                    # add space after hashtag
                    page.keyboard.press("Space")

                    time.sleep(0.5)

                # ─────────────────────────────
                # NORMAL TEXT
                # ─────────────────────────────
                else:

                    box.press_sequentially(
                        word + " ",
                        delay=80
                    )

                    time.sleep(0.2)

            time.sleep(2)

            current_text = box.inner_text()

            log(f"📝 Caption result: {current_text}")

            log("✅ Caption filled")

            return True

        except Exception as e:

            log(f"⚠️ Caption failed: {e}")

            continue

    return False




def click_post_button(page):

    log("📮 Mencari tombol Post...")

    selectors = [
        "[data-e2e='post_video_button']",
        "button[data-e2e='submit-button']",
        "button:has-text('Post')",
        "button:has-text('Posting')",
    ]

    for sel in selectors:

        try:

            btn = page.locator(sel).first

            if not btn.is_visible(timeout=3000):
                continue

            disabled = btn.get_attribute("disabled")

            if disabled is not None:

                log("⏳ Tombol Post masih disabled")

                continue

            btn.scroll_into_view_if_needed()

            time.sleep(1)

            try:
                btn.click(timeout=5000)
            except:
                btn.click(force=True)

            log(f"✅ Tombol Post diklik via: {sel}")

            return True

        except Exception:
            continue

    return False


def upload_to_tiktok(
    video_path,
    cookies_path,
    description="",
    headless=True
):

    with sync_playwright() as p:

        log("🌐 Membuka browser...")

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
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        log(f"🍪 Memuat cookies: {cookies_path}")

        cookies = parse_cookies(cookies_path)

        context.add_cookies(cookies)

        page = context.new_page()

        # OPEN PAGE
        goto_with_retry(
            page,
            TIKTOK_UPLOAD_URL
        )

        screenshot(page, "01_upload_page")

        if "login" in page.url.lower():

            screenshot(page, "error_login")

            raise Exception(
                "❌ Login gagal, cookies invalid"
            )

        log("✅ Login berhasil")

        # CLOSE INITIAL MODAL
        close_modal(page)

        screenshot(page, "02_after_modal")

        # FIND INPUT
        file_input = find_upload_input(page)

        screenshot(page, "03_input_found")

        # UPLOAD VIDEO
        log(f"📤 Uploading: {video_path}")

        file_input.set_input_files(
            str(video_path.resolve())
        )

        time.sleep(5)

        screenshot(page, "04_video_uploaded")

        # WAIT PROCESSING
        wait_for_upload_complete(page)

        screenshot(page, "05_upload_complete")

        # CLOSE POPUPS
        close_modal(page)

        handle_content_check_popup(page)

        screenshot(page, "06_after_popup")

        # FILL CAPTION
        if description:

            fill_caption(page, description)

            time.sleep(2)

            screenshot(page, "07_caption")

        # POST
        time.sleep(3)

        screenshot(page, "08_before_post")

        posted = click_post_button(page)

        if posted:

            log("⏳ Menunggu redirect setelah post...")

            time.sleep(15)

            screenshot(page, "09_post_success")

            log("🎉 UPLOAD SUCCESS")

        else:

            screenshot(page, "09_post_failed")

            log("❌ Tombol Post gagal ditemukan")

        browser.close()


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="https://v1.pinimg.com/videos/iht/expMp4/b7/b4/4b/b7b44b6222612c40a5b30fd7e991cb4f_720w.mp4"
    )

    parser.add_argument(
        "--cookies",
        default="cookies.json"
    )

    parser.add_argument(
        "--description",
        default="Video keren 🚀 #fyp #viral"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True
    )

    args = parser.parse_args()

    if not Path(args.cookies).exists():

        log(f"❌ Cookies tidak ditemukan")

        sys.exit(1)

    download_video(
        args.url,
        VIDEO_FILE
    )

    upload_to_tiktok(
        VIDEO_FILE,
        args.cookies,
        args.description,
        args.headless
    )


if __name__ == "__main__":
    main()
