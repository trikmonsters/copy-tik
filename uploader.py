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
        log("🔑 sessionid dari env TIKTOK_SESSION_ID ditambahkan")

    return cookies


def goto_with_retry(page, url: str, retries: int = 3):
    """Buka URL dengan retry, pakai domcontentloaded agar tidak timeout."""
    for attempt in range(1, retries + 1):
        try:
            log(f"🌐 Membuka halaman (percobaan {attempt}/{retries})...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Tunggu sebentar agar JS halaman sempat jalan
            time.sleep(5)
            return
        except PlaywrightTimeout:
            log(f"⚠️  Timeout percobaan {attempt}, mencoba lagi...")
            time.sleep(3)
    raise Exception(f"❌ Gagal membuka {url} setelah {retries} percobaan")


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

        # Buka halaman upload dengan retry
        goto_with_retry(page, TIKTOK_UPLOAD_URL)
        screenshot(page, "01_halaman_upload")
        log(f"📍 URL saat ini: {page.url}")

        if "login" in page.url.lower():
            screenshot(page, "error_tidak_login")
            raise Exception("❌ Tidak terdeteksi login. Periksa cookies Anda!")

        log("✅ Login terdeteksi")

        # Tunggu halaman upload benar-benar siap
        try:
            page.wait_for_selector("input[type='file']", timeout=30000)
        except PlaywrightTimeout:
            screenshot(page, "error_input_file_tidak_ada")
            raise Exception("❌ Input file tidak ditemukan di halaman upload")

        log(f"📤 Mengupload file: {video_path}")
        page.locator("input[type='file']").set_input_files(str(video_path.resolve()))

        log("⏳ Menunggu video diproses...")
        time.sleep(10)
        screenshot(page, "02_video_diupload")

        try:
            page.wait_for_selector(".upload-progress", state="hidden", timeout=60000)
        except Exception:
            pass

        time.sleep(5)
        screenshot(page, "03_setelah_upload")

        if description:
            log(f"✏️  Mengisi caption: {description}")
            try:
                box = page.locator("div[contenteditable='true'], textarea").first
                box.click()
                time.sleep(1)
                box.fill(description)
                time.sleep(1)
                screenshot(page, "04_caption_diisi")
            except Exception as e:
                log(f"⚠️  Gagal isi caption: {e}")

        log("📮 Mencari tombol Post...")
        time.sleep(3)

        for selector in [
            "button:has-text('Post')",
            "button:has-text('Posting')",
            "[data-e2e='submit-button']",
            "button.upload-btn",
        ]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    screenshot(page, "05_sebelum_post")
                    btn.click()
                    log("✅ Tombol Post diklik")
                    time.sleep(8)
                    screenshot(page, "06_setelah_post")
                    log("🎉 Upload selesai!")
                    break
            except Exception:
                continue
        else:
            screenshot(page, "05_tombol_post_tidak_ditemukan")
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
