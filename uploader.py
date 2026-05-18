"""
TikTok Uploader - Headless Humanized Version
Upload video ke TikTok dengan warmup browsing & human-like behavior
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
    print(f"[TikTok Uploader] {msg}", flush=True)


def human_delay(a=0.8, b=2.5):
    time.sleep(random.uniform(a, b))


def random_mouse_movements(page):
    try:
        for _ in range(random.randint(4, 8)):
            x = random.randint(100, 1200)
            y = random.randint(100, 700)

            page.mouse.move(
                x,
                y,
                steps=random.randint(10, 25)
            )

            human_delay(0.2, 0.7)

    except:
        pass


def warmup_session(page):
    try:
        log("🔥 Warmup session TikTok...")

        page.goto(
            "https://www.tiktok.com/foryou",
            wait_until="domcontentloaded",
            timeout=60000
        )

        human_delay(5, 8)

        random_mouse_movements(page)

        # scroll video seperti user normal
        for i in range(random.randint(5, 8)):
            log(f"📱 Menonton video {i+1}")

            page.mouse.wheel(
                0,
                random.randint(700, 1300)
            )

            random_mouse_movements(page)

            human_delay(3, 7)

        log("✅ Warmup selesai")

    except Exception as e:
        log(f"⚠️ Warmup gagal: {e}")


def post_upload_browsing(page):
    try:
        log("📱 Simulasi browsing setelah post...")

        page.goto(
            "https://www.tiktok.com/foryou",
            wait_until="domcontentloaded",
            timeout=60000
        )

        human_delay(4, 7)

        for i in range(random.randint(3, 6)):
            page.mouse.wheel(
                0,
                random.randint(700, 1300)
            )

            random_mouse_movements(page)

            human_delay(2, 5)

        log("✅ Browsing setelah post selesai")

    except Exception as e:
        log(f"⚠️ Post browsing gagal: {e}")


def download_video(url: str, output: Path):
    log(f"⬇️ Mendownload video dari: {url}")

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

    log(f"✅ Video berhasil didownload ({size_mb:.1f} MB)")


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

            human_delay(3, 6)

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
                random_mouse_movements(page)

                btn.click(force=True)

                log(f"✅ Modal ditutup via: {sel}")

                human_delay(1, 2)

                return True

        except:
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

        cancel_selectors = [
            "button:has-text('Cancel')",
            "button:has-text('Skip')",
            "button:has-text('Not now')",
        ]

        for sel in cancel_selectors:
            try:
                btn = page.locator(sel).first

                if btn.is_visible(timeout=3000):
                    random_mouse_movements(page)

                    btn.click(force=True)

                    log(f"✅ Popup ditutup via: {sel}")

                    human_delay(2, 3)

                    return True

            except:
                continue

        page.keyboard.press("Escape")

        log("✅ Popup ditutup via Escape")

        human_delay(1, 2)

        return True

    except Exception as e:
        log(f"⚠️ Error popup: {e}")

        return False


def find_upload_input(page):
    log("🔍 Mencari input upload...")

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

        human_delay(1, 3)

    human_delay(5, 8)


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

            random_mouse_movements(page)

            box.click(force=True)

            human_delay(1, 2)

            # clear existing
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
                        delay=random.randint(90, 160)
                    )

                    human_delay(1, 2)

                    page.keyboard.press("Enter")

                    human_delay(0.5, 1)

                else:
                    box.press_sequentially(
                        word + " ",
                        delay=random.randint(60, 130)
                    )

                    human_delay(0.1, 0.3)

            human_delay(2, 3)

            try:
                current_text = box.inner_text()

                log(f"📝 Caption result: {current_text}")

            except:
                pass

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

            if not btn.is_visible(timeout=5000):
                continue

            disabled = btn.get_attribute("disabled")

            if disabled is not None:
                log("⏳ Tombol Post masih disabled")
                continue

            btn.scroll_into_view_if_needed()

            random_mouse_movements(page)

            human_delay(1, 3)

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
            slow_mo=random.randint(50, 150),
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

        # warmup browsing
        warmup_session(page)

        # open upload page
        goto_with_retry(page, TIKTOK_UPLOAD_URL)

        if "login" in page.url.lower():
            raise Exception("❌ Login gagal, cookies invalid")

        log("✅ Login berhasil")

        close_modal(page)

        random_mouse_movements(page)

        file_input = find_upload_input(page)

        log(f"📤 Uploading: {video_path}")

        human_delay(2, 5)

        file_input.set_input_files(
            str(video_path.resolve())
        )

        human_delay(4, 7)

        wait_for_upload_complete(page)

        close_modal(page)

        handle_content_check_popup(page)

        if description:
            fill_caption(page, description)

            human_delay(2, 4)

        # post video
        posted = click_post_button(page)

        if posted:
            log("⏳ Menunggu redirect setelah post...")

            human_delay(10, 20)

            log("🎉 UPLOAD SUCCESS")

            # browsing setelah upload
            post_upload_browsing(page)

        else:
            log("❌ Tombol Post gagal ditemukan")

        human_delay(10, 20)

        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Upload video ke TikTok"
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

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Headless mode"
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
        args.description,
        args.headless
    )


if __name__ == "__main__":
    main()
