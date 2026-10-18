"""제품 링크에서 정보 + 이미지 URL 스크래핑 (Playwright)."""
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


def _is_coupang(url: str) -> bool:
    return "coupang.com" in url


def _is_tiktok(url: str) -> bool:
    return "tiktok.com" in url


def scrape_product(url: str) -> dict:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        if _is_coupang(url):
            result = _scrape_coupang(page)
            result["source"] = "coupang"
        elif _is_tiktok(url):
            result = _scrape_tiktok(page)
            result["source"] = "tiktok"
        else:
            result = _scrape_generic(page)
            result["source"] = "unknown"

        browser.close()
        return result


def _scrape_coupang(page) -> dict:
    name = ""
    if page.locator("h1.prod-buy-header__title").count():
        name = page.locator("h1.prod-buy-header__title").first.inner_text(timeout=5000)
    price = ""
    if page.locator(".prod-price").count():
        price = page.locator(".prod-price").first.inner_text(timeout=5000)
    imgs = page.locator("img.prod-image__detail").all()
    image_urls = [img.get_attribute("src") for img in imgs if img.get_attribute("src")]
    reviews = []
    for el in page.locator(".sdp-review__article__content").all()[:5]:
        reviews.append(el.inner_text())
    desc = ""
    if page.locator(".prod-description-main").count():
        desc = page.locator(".prod-description-main").inner_text(timeout=3000)
    return {"name": name, "price": price, "description": desc[:500], "image_urls": image_urls[:5], "reviews": reviews}


def _scrape_tiktok(page) -> dict:
    name = ""
    if page.locator("[data-e2e='product-title']").count():
        name = page.locator("[data-e2e='product-title']").first.inner_text(timeout=5000)
    price = ""
    if page.locator("[data-e2e='product-price']").count():
        price = page.locator("[data-e2e='product-price']").first.inner_text(timeout=5000)
    imgs = page.locator("img[class*='product']").all()
    image_urls = [img.get_attribute("src") for img in imgs[:5] if img.get_attribute("src")]
    return {"name": name, "price": price, "description": "", "image_urls": image_urls, "reviews": []}


def _scrape_generic(page) -> dict:
    title = page.title()
    imgs = page.locator("img").all()
    image_urls = [
        img.get_attribute("src") for img in imgs[:5]
        if img.get_attribute("src") and img.get_attribute("src").startswith("http")
    ]
    return {"name": title, "price": "", "description": "", "image_urls": image_urls, "reviews": []}


def download_image(url: str, dest_path) -> bool:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=15, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return True
    except Exception:
        return False
