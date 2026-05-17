"""
TikTok Uploader - Save Draft Version
Upload video dari URL ke TikTok dan simpan sebagai draft
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
VIDEO_FILE = Path("video.mp4")


def log(msg: str):
    print(f"[TikTok Uploader] {msg}", flush=True)


def download_video(url: str, output: Path):
    log(f"⬇️ Mendownload video dari: {url}")

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
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
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            return
        except PlaywrightTimeout:
            log(f"⚠️ Timeout percobaan {attempt}")
            time.sleep(3)

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
        file_input = page.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)

        log("✅ File input ditemukan")
        return file_input

    except Exception as e:
        raise Exception(f"❌ Input upload tidak ditemukan: {e}")


def wait_for_upload_complete(page, timeout=180):
    log("⏳ Menunggu upload selesai...")

    start = time.time()

    progress_selectors = [
        "[class*='progress']",
        "[class*='uploading']",
        "[class*='Progress']",
        "[class*='processing']",
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

            # Clear existing text
            page.keyboard.press("Control+a")
            time.sleep(0.5)

            page.keyboard.press("Backspace")
            time.sleep(1)

            words = text.split()

            for word in words:
                if word.startswith("#"):
                    page.keyboard.press("Space")
                    box.press_sequentially(word, delay=120)
                    time.sleep(2)
                    page.keyboard.press("Enter")
                    time.sleep(0.5)
                else:
                    box.press_sequentially(word + " ", delay=80)
                    time.sleep(0.2)

            time.sleep(2)

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


def click_draft_button(page):
    log("📂 Mencari tombol Draft...")

    selectors = [
        "button:has-text('Draft')",
        "button:has-text('Save draft')",
        "button:has-text('Save Draft')",
        "button[data-e2e='save-draft-button']",
        "[data-e2e='draft-button']",
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
            time.sleep(1)

            try:
                btn.click(timeout=5000)
            except:
                btn.click(force=True)

            log(f"✅ Tombol Draft diklik via: {sel}")
            time.sleep(3)

            # Confirm popup
            confirm_selectors = [
                "button:has-text('Save')",
                "button:has-text('Confirm')",
                "button:has-text('OK')",
            ]

            for csel in confirm_selectors:
                try:
                    confirm_btn = page.locator(csel).first

                    if confirm_btn.is_visible(timeout=2000):
                        confirm_btn.click(force=True)
                        log(f"✅ Confirm draft via: {csel}")
                        time.sleep(2)
                        break

                except:
                    pass

            return True

        except Exception as e:
            log(f"⚠️ Draft selector gagal: {e}")
            continue

    return False


def upload_to_tiktok(video_path, cookies_path, description="", headless=False):
    with sync_playwright() as p:
        log("🌐 Membuka browser...")

        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--start-maximized",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        log(f"🍪 Memuat cookies: {cookies_path}")

        cookies = parse_cookies(cookies_path)
        context.add_cookies(cookies)

        page = context.new_page()

        # Debug mode
        # page.pause()

        # Open upload page
        goto_with_retry(page, TIKTOK_UPLOAD_URL)

        if "login" in page.url.lower():
            raise Exception("❌ Login gagal, cookies invalid")

        log("✅ Login berhasil")

        # Close initial modal
        close_modal(page)

        # Find upload input
        file_input = find_upload_input(page)

        log(f"📤 Uploading: {video_path}")

        file_input.set_input_files(str(video_path.resolve()))

        time.sleep(5)

        # Wait processing
        wait_for_upload_complete(page)

        # Close popups
        close_modal(page)
        handle_content_check_popup(page)

        # Fill caption
        if description:
            fill_caption(page, description)
            time.sleep(2)

        # Save Draft
        time.sleep(5)

        drafted = click_draft_button(page)

        if drafted:
            log("⏳ Menunggu proses save draft...")
            time.sleep(10)

            log("🎉 VIDEO BERHASIL DISIMPAN KE DRAFT")
        else:
            log("❌ Tombol Draft gagal ditemukan")

            # Debug HTML
            try:
                html = page.content()

                with open("debug.html", "w", encoding="utf-8") as f:
                    f.write(html)

                log("🛠 Debug HTML disimpan ke debug.html")

            except:
                pass

        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Upload video ke TikTok sebagai draft"
    )

    parser.add_argument(
        "--url",
        default="https://v1.pinimg.com/videos/iht/expMp4/b7/b4/4b/b7b44b6222612c40a5b30fd7e991cb4f_720w.mp4",
        help="URL video yang akan diupload"
    )

    parser.add_argument(
        "--cookies",
        default="cookies.json",
        help="Path file cookies JSON"
    )

    parser.add_argument(
        "--description",
        default="Video keren 🚀 #fyp #viral",
        help="Caption/deskripsi video"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Jalankan browser headless"
    )

    args = parser.parse_args()

    if not Path(args.cookies).exists():
        log(f"❌ Cookies tidak ditemukan: {args.cookies}")
        sys.exit(1)

    # Download video
    download_video(args.url, VIDEO_FILE)

    # Upload as draft
    upload_to_tiktok(
        VIDEO_FILE,
        args.cookies,
        args.description,
        args.headless
    )


if __name__ == "__main__":
    main()
