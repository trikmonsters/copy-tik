"""
TikTok Uploader - Simple Version
Upload video dari URL ke TikTok menggunakan Playwright
Support cookies format: JSON (Cookie Editor) atau Netscape (.txt)
"""

import os
import sys
import json
import time
import requests
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"
SCREENSHOT_DIR = Path("screenshots")
VIDEO_FILE = Path("video.mp4")


def log(msg: str):
    print(f"[TikTok Uploader] {msg}", flush=True)


def screenshot(page, name: str):
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    log(f"📸 Screenshot disimpan: {path}")


def download_video(url: str, output: Path):
    log(f"⬇️  Mendownload video dari: {url}")
    response = requests.get(url, stream=True, timeout=60, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    response.raise_for_status()
    with open(output, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = output.stat().st_size / (1024 * 1024)
    log(f"✅ Video berhasil didownload ({size_mb:.1f} MB) → {output}")


def parse_cookies(cookies_path: str) -> list:
    with open(cookies_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    cookies = []
    if content.startswith("["):
        raw = json.loads(content)
        for c in raw:
            expiry = c.get("expirationDate") or c.get("expires") or -1
            cookies.append({
                "name":     c["name"],
                "value":    c["value"],
                "domain":   c["domain"],
                "path":     c.get("path", "/"),
                "secure":   c.get("secure", False),
                "expires":  int(expiry),
                "httpOnly": c.get("httpOnly", False),
            })
        log(f"🍪 Format JSON — memuat {len(cookies)} cookies")
    else:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, path, secure, expiry, name, value = parts[:7]
            cookies.append({
                "name":   name,
                "value":  value,
                "domain": domain,
                "path":   path,
                "secure": secure.upper() == "TRUE",
                "expires": int(expiry) if expiry.isdigit() else -1,
            })
        log(f"🍪 Format Netscape — memuat {len(cookies)} cookies")

    session_id = os.environ.get("TIKTOK_SESSION_ID", "")
    if session_id:
        cookies = [c for c in cookies if c["name"] != "sessionid"]
        cookies.append({
            "name":    "sessionid",
            "value":   session_id,
            "domain":  ".tiktok.com",
            "path":    "/",
            "secure":  True,
            "expires": 2147483647,
            "httpOnly": True,
        })
        log("🔑 sessionid dari env ditambahkan")

    return cookies


def goto_with_retry(page, url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            log(f"🌐 Membuka halaman (percobaan {attempt}/{retries})...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            return
        except PlaywrightTimeout:
            log(f"⚠️  Timeout percobaan {attempt}, mencoba lagi...")
            time.sleep(3)
    raise Exception(f"❌ Gagal membuka {url} setelah {retries} percobaan")


def close_modal(page):
    """Tutup modal/popup yang menghalangi interaksi."""
    modal_closed = False

    # Coba klik tombol close modal (×)
    close_selectors = [
        "[data-e2e='modal-close-inner-button']",
        "button[aria-label='Close']",
        "button.TUXModal-closeButton",
        ".modal-close",
        "[class*='closeButton']",
        "[class*='close-button']",
        "button:has-text('Close')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "button:has-text('Mengerti')",
        "button:has-text('Oke')",
    ]

    for sel in close_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click()
                log(f"✅ Modal ditutup via: {sel}")
                time.sleep(1)
                modal_closed = True
                break
        except Exception:
            continue

    # Kalau tidak ada tombol close, coba tekan Escape
    if not modal_closed:
        try:
            overlay = page.locator(".TUXModal-overlay, [class*='modal-overlay'], [class*='modal-desc']").first
            if overlay.is_visible(timeout=1000):
                page.keyboard.press("Escape")
                log("✅ Modal ditutup via Escape")
                time.sleep(1)
                modal_closed = True
        except Exception:
            pass

    return modal_closed


def click_caption(page, description: str):
    """Isi caption dengan handle modal yang menghalangi."""

    # Tutup modal dulu jika ada
    close_modal(page)
    time.sleep(1)

    # Selector caption TikTok (Updated berdasarkan repo reference)
    caption_selectors = [
        "[data-e2e='caption-input']",           # Official TikTok attribute (paling reliable)
        "div.public-DraftEditor-content",       # Draft.js editor
        "div[contenteditable='true']",          # Generic contenteditable
        "div[class*='caption']",                # Class-based fallback
        "textarea",                             # Textarea fallback
    ]

    for sel in caption_selectors:
        try:
            box = page.locator(sel).first
            if not box.is_visible(timeout=3000):
                continue

            # Klik dengan force=True untuk bypass elemen yang menghalangi
            box.click(force=True)
            time.sleep(0.5)

            # Kosongkan dulu lalu isi
            box.select_all()
            page.keyboard.press("Control+a")
            page.keyboard.press("Delete")
            page.keyboard.type(description, delay=50)

            log(f"✅ Caption berhasil diisi via: {sel}")
            return True
        except Exception as e:
            log(f"⚠️  Selector {sel} gagal: {e}")
            continue

    log("⚠️  Semua selector caption gagal, lanjut tanpa caption")
    return False


def click_post_button(page):
    """Klik tombol Post dengan handle modal dan selector yang lebih robust."""

    # Tutup modal dulu jika masih ada
    close_modal(page)
    time.sleep(1)

    # Updated post button selectors berdasarkan repo reference
    post_selectors = [
        "[data-e2e='post_video_button']",       # Official TikTok attribute (paling reliable)
        "button[data-e2e='submit-button']",     # Alternative official attribute
        "button:has-text('Post')",              # Text-based fallback (EN)
        "button:has-text('Posting')",           # Alternative text (EN)
        "button:has-text('Đăng')",              # Vietnamese
        "button:has-text('发布')",              # Chinese
        "div[data-e2e='submit-button']",        # Div wrapper
        "button.upload-btn",                    # Class-based
        "button[class*='submit']",              # Class contains submit
        "button[class*='post']",                # Class contains post
    ]

    for sel in post_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=3000):
                # Scroll ke tombol dulu
                btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                # Klik dengan force jika perlu
                try:
                    btn.click(timeout=5000)
                except Exception:
                    btn.click(force=True)
                log(f"✅ Tombol Post diklik via: {sel}")
                return True
        except Exception:
            continue

    return False


def wait_for_upload_complete(page, timeout: int = 120):
    """Tunggu hingga upload selesai dengan monitoring progress indicators."""
    log("⏳ Memantau progress upload...")
    start_time = time.time()
    
    progress_selectors = [
        "[class*='progress']",
        "[class*='uploading']",
        "[class*='upload-card-progress']",
    ]

    while time.time() - start_time < timeout:
        progress_visible = False
        
        for sel in progress_selectors:
            try:
                if page.locator(sel).count() > 0:
                    progress_visible = True
                    break
            except Exception:
                pass
        
        if not progress_visible:
            log("✅ Progress indicator hilang, upload selesai")
            break
        
        time.sleep(2)

    time.sleep(3)  # Extra buffer untuk processing


def upload_to_tiktok(video_path, cookies_path, description="", headless=True):
    with sync_playwright() as p:
        log("🌐 Membuka browser Chrome...")
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        log(f"🍪 Memuat cookies dari: {cookies_path}")
        cookies = parse_cookies(cookies_path)
        context.add_cookies(cookies)

        page = context.new_page()

        # ── 1. Buka halaman upload ────────────────────────────────
        goto_with_retry(page, TIKTOK_UPLOAD_URL)
        screenshot(page, "01_halaman_upload")
        log(f"📍 URL: {page.url}")

        if "login" in page.url.lower():
            screenshot(page, "error_tidak_login")
            raise Exception("❌ Tidak terdeteksi login. Periksa cookies!")

        log("✅ Login terdeteksi")

        # ── 2. Tutup modal awal jika ada ──────────────────────────
        log("🔍 Memeriksa modal awal...")
        close_modal(page)
        screenshot(page, "02_setelah_tutup_modal_awal")

        # ── 3. Tunggu input file siap ─────────────────────────────
        try:
            page.wait_for_selector("input[type='file']", timeout=30000)
        except PlaywrightTimeout:
            screenshot(page, "error_input_file_tidak_ada")
            raise Exception("❌ Input file tidak ditemukan")

        # ── 4. Upload video ───────────────────────────────────────
        log(f"📤 Mengupload file: {video_path}")
        page.locator("input[type='file']").set_input_files(str(video_path.resolve()))

        log("⏳ Menunggu video diproses...")
        time.sleep(5)
        screenshot(page, "03_video_diupload")

        # ── 5. Tunggu upload complete dengan monitoring ───────────
        wait_for_upload_complete(page, timeout=120)
        
        # Tutup modal yang mungkin muncul setelah upload
        close_modal(page)
        time.sleep(3)
        screenshot(page, "04_setelah_upload_selesai")

        # ── 6. Isi caption ────────────────────────────────────────
        if description:
            log(f"✏️  Mengisi caption: {description}")
            click_caption(page, description)
            time.sleep(1)
            screenshot(page, "05_caption_diisi")

        # ── 7. Klik Post ──────────────────────────────────────────
        log("📮 Mencari dan klik tombol Post...")
        time.sleep(2)
        screenshot(page, "06_sebelum_post")

        posted = click_post_button(page)

        if posted:
            time.sleep(8)
            screenshot(page, "07_setelah_post")
            log("🎉 Upload selesai!")
        else:
            screenshot(page, "07_tombol_post_tidak_ditemukan")
            log("⚠️  Tombol Post tidak ditemukan, cek screenshot!")

        browser.close()


def main():
    parser = argparse.ArgumentParser(description="TikTok Uploader Simple")
    parser.add_argument("--url", default="https://v1.pinimg.com/videos/iht/expMp4/b7/b4/4b/b7b44b6222612c40a5b30fd7e991cb4f_720w.mp4")
    parser.add_argument("--cookies", default="cookies.json")
    parser.add_argument("--description", default="Video keren! #fyp #viral")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    if not Path(args.cookies).exists():
        log(f"❌ File cookies tidak ditemukan: {args.cookies}")
        sys.exit(1)

    download_video(args.url, VIDEO_FILE)
    upload_to_tiktok(VIDEO_FILE, args.cookies, args.description, args.headless)


if __name__ == "__main__":
    main()
