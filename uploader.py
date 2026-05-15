"""
TikTok Uploader - Simple Version
Upload video dari URL ke TikTok menggunakan Playwright
"""

import os
import sys
import time
import requests
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

# ─── Konfigurasi ─────────────────────────────────────────────────
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"
SCREENSHOT_DIR = Path("screenshots")
VIDEO_FILE = Path("video.mp4")


def log(msg: str):
    print(f"[TikTok Uploader] {msg}", flush=True)


def screenshot(page, name: str):
    """Simpan screenshot ke folder screenshots/"""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    log(f"📸 Screenshot disimpan: {path}")


def download_video(url: str, output: Path):
    """Download video dari URL"""
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


def upload_to_tiktok(
    video_path: Path,
    cookies_path: str,
    description: str = "",
    headless: bool = True,
):
    """Upload video ke TikTok menggunakan Playwright"""

    with sync_playwright() as p:
        # ── 1. Buka Browser ──────────────────────────────────────
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

        # ── 2. Load Cookies ───────────────────────────────────────
        log(f"🍪 Memuat cookies dari: {cookies_path}")
        cookies = parse_cookies(cookies_path)
        context.add_cookies(cookies)

        page = context.new_page()

        # ── 3. Buka Halaman Upload TikTok ────────────────────────
        log("🔗 Membuka halaman upload TikTok...")
        page.goto(TIKTOK_UPLOAD_URL, wait_until="networkidle", timeout=60000)
        time.sleep(3)
        screenshot(page, "01_halaman_upload")
        log("✅ Halaman upload terbuka")

        # ── 4. Cek Login ─────────────────────────────────────────
        if "login" in page.url.lower():
            screenshot(page, "error_tidak_login")
            raise Exception("❌ Tidak terdeteksi login. Periksa cookies Anda!")

        log("✅ Login terdeteksi")

        # ── 5. Upload File Video ──────────────────────────────────
        log(f"📤 Mengupload file video: {video_path}")

        # Klik area upload / input file
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(video_path.resolve()))
        log("📁 File video dipilih")

        # Tunggu video selesai diproses
        log("⏳ Menunggu video diproses TikTok...")
        time.sleep(10)
        screenshot(page, "02_video_diupload")

        # Tunggu progress bar selesai (jika ada)
        try:
            page.wait_for_selector(".upload-progress", state="hidden", timeout=60000)
        except Exception:
            pass

        time.sleep(5)
        screenshot(page, "03_setelah_upload")

        # ── 6. Isi Caption/Deskripsi ─────────────────────────────
        if description:
            log(f"✏️  Mengisi caption: {description}")
            try:
                caption_box = page.locator(
                    "div[contenteditable='true'], textarea"
                ).first
                caption_box.click()
                time.sleep(1)
                caption_box.fill(description)
                time.sleep(1)
                screenshot(page, "04_caption_diisi")
            except Exception as e:
                log(f"⚠️  Gagal mengisi caption: {e}")

        # ── 7. Klik Tombol Post ───────────────────────────────────
        log("📮 Mencari tombol Post...")
        time.sleep(3)

        # Coba berbagai selector tombol post
        post_selectors = [
            "button:has-text('Post')",
            "button:has-text('Posting')",
            "[data-e2e='submit-button']",
            "button.upload-btn",
        ]

        posted = False
        for selector in post_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    screenshot(page, "05_sebelum_post")
                    btn.click()
                    posted = True
                    log(f"✅ Tombol Post diklik: {selector}")
                    break
            except Exception:
                continue

        if not posted:
            screenshot(page, "05_tombol_post_tidak_ditemukan")
            log("⚠️  Tombol Post tidak ditemukan, cek screenshot!")
        else:
            # Tunggu selesai
            time.sleep(8)
            screenshot(page, "06_setelah_post")
            log("🎉 Proses upload selesai!")

        browser.close()


def parse_cookies(cookies_path: str) -> list:
    """Parse cookies dari file format Netscape (.txt)"""
    cookies = []
    with open(cookies_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, path, secure, expiry, name, value = parts[:7]
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "secure": secure.upper() == "TRUE",
                "expires": int(expiry) if expiry.isdigit() else -1,
            })
    log(f"🍪 Berhasil memuat {len(cookies)} cookies")
    return cookies


def main():
    parser = argparse.ArgumentParser(description="TikTok Uploader Simple")
    parser.add_argument(
        "--url",
        default="https://v1.pinimg.com/videos/iht/expMp4/b7/b4/4b/b7b44b6222612c40a5b30fd7e991cb4f_720w.mp4",
        help="URL video untuk diupload",
    )
    parser.add_argument(
        "--cookies",
        default="cookies.txt",
        help="Path ke file cookies TikTok (format Netscape)",
    )
    parser.add_argument(
        "--description",
        default="Video keren! #fyp #viral",
        help="Caption/deskripsi video",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Jalankan browser dalam mode headless",
    )
    args = parser.parse_args()

    # Validasi cookies
    if not Path(args.cookies).exists():
        log(f"❌ File cookies tidak ditemukan: {args.cookies}")
        log("💡 Cara mendapatkan cookies:")
        log("   1. Login ke tiktok.com di browser")
        log("   2. Buka DevTools (F12) → Console")
        log("   3. Jalankan script JS dari README untuk export cookies.txt")
        sys.exit(1)

    # Download video
    download_video(args.url, VIDEO_FILE)

    # Upload ke TikTok
    upload_to_tiktok(
        video_path=VIDEO_FILE,
        cookies_path=args.cookies,
        description=args.description,
        headless=args.headless,
    )


if __name__ == "__main__":
    main()
