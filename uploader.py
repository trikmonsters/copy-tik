"""
TikTok Uploader - Humanized Stable Version
Upload video ke TikTok dengan warmup session dan interaksi natural
"""

import sys
import time
import random
import argparse
import requests

from pathlib import Path
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeout
)

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"

VIDEO_FILE = Path("video.mp4")

PROFILE_DIR = "tiktok_profile"


def log(msg: str):
    print(f"***TikTok Uploader*** {msg}", flush=True)


def human_delay(a=0.8, b=2.5):
    time.sleep(random.uniform(a, b))


def random_mouse_movements(page):
    try:
        for _ in range(random.randint(5, 10)):
            x = random.randint(100, 1200)
            y = random.randint(100, 700)

            page.mouse.move(
                x,
                y,
                steps=random.randint(10, 30)
            )

            human_delay(0.2, 0.8)

    except:
        pass


def warmup_session(page):
    log("🔥 Warmup session browser...")

    try:
        page.goto(
            "https://www.tiktok.com/foryou",
            wait_until="domcontentloaded",
            timeout=60000
        )

        human_delay(5, 8)

        random_mouse_movements(page)

        for i in range(random.randint(5, 8)):
            log(f"📱 Scroll video {i+1}")

            page.mouse.wheel(
                0,
                random.randint(700, 1200)
            )

            human_delay(3, 7)

            random_mouse_movements(page)

        log("✅ Warmup selesai")

    except Exception as e:
        log(f"⚠️ Warmup gagal: {e}")


def download_video(url: str, output: Path):
    log(f"⬇️ Mendownload video dari: {url}")

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64)"
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


def goto_with_retry(page, url, retries=3):
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
    selectors = [
        "[data-e2e='modal-close-inner-button']",
        "button[aria-label='Close']",
        "button:has-text('Close')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "button:has-text('Cancel')",
    ]

    for sel in selectors:
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
                pass

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
                pass

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


def wait_for_upload_complete(page, timeout=300):
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
            break

        human_delay(1, 3)

    log("✅ Upload visual selesai")

    log("⏳ Menunggu processing internal TikTok...")
    human_delay(15, 25)


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
                        delay=random.randint(80, 160)
                    )

                    human_delay(1, 2)

                    page.keyboard.press("Enter")

                    human_delay(0.5, 1)

                else:
                    box.press_sequentially(
                        word + " ",
                        delay=random.randint(60, 140)
                    )

                    human_delay(0.1, 0.4)

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

            log(f"🖱 Klik Post via: {sel}")

            try:
                with page.expect_response(
                    lambda r: (
                        "post" in r.url.lower()
                        or "upload" in r.url.lower()
                    ),
                    timeout=30000
                ) as response_info:

                    btn.click(timeout=5000)

                response = response_info.value

                log(
                    f"📡 API Response: "
                    f"{response.status}"
                )

            except:
                btn.click(force=True)

            human_delay(5, 10)

            return True

        except Exception as e:
            log(f"⚠️ Post gagal: {e}")

    return False


def upload_to_tiktok(
    video_path,
    description=""
):
    with sync_playwright() as p:

        log("🌐 Membuka browser persistent...")

        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            slow_mo=random.randint(100, 400),
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
            args=[
                "--start-maximized",
                "--disable-dev-shm-usage",
            ]
        )

        page = context.pages[0]

        # debug manual
        # page.pause()

        # warmup browser
        warmup_session(page)

        goto_with_retry(
            page,
            TIKTOK_UPLOAD_URL
        )

        # login manual pertama kali
        if "login" in page.url.lower():

            log("🔐 Silakan login manual TikTok...")
            log("⌛ Menunggu login selesai...")

            while "login" in page.url.lower():
                time.sleep(3)

            log("✅ Login berhasil disimpan")

        human_delay(3, 6)

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

            human_delay(3, 6)

        posted = click_post_button(page)

        if posted:
            log("🎉 VIDEO BERHASIL DIPOST")

            human_delay(15, 30)

        else:
            log("❌ Gagal post video")

        log("⌛ Menunggu sebelum browser ditutup...")

        human_delay(20, 40)

        context.close()


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Humanized Uploader"
    )

    parser.add_argument(
        "--url",
        default=(
            "https://v1.pinimg.com/videos/iht/"
            "expMp4/b7/b4/4b/"
            "b7b44b6222612c40a5b30fd7e991cb4f_720w.mp4"
        ),
        help="URL video"
    )

    parser.add_argument(
        "--description",
        default="Video keren 🚀 #fyp #viralvideo",
        help="Caption"
    )

    args = parser.parse_args()

    download_video(
        args.url,
        VIDEO_FILE
    )

    upload_to_tiktok(
        VIDEO_FILE,
        args.description
    )


if __name__ == "__main__":
    main()
