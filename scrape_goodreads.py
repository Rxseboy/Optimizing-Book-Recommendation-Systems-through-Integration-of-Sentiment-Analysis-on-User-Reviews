"""
Goodreads Metadata Scraper
===========================
Scrapes book metadata (cover image, title, rating, genres, description,
series info, page count, publication date) from Goodreads for all books
in the dataset.

Author : Rizqi Fajar
Usage  : python scrape_goodreads.py
"""

import json
import os
import re
import time
import logging
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "Dataset_Goodreads_Book_of_Carissa_Broadbent_Fix.xlsx"
OUTPUT_JSON = BASE_DIR / "data" / "books_metadata.json"
COVERS_DIR = BASE_DIR / "data" / "covers"
WEB_DATA_DIR = BASE_DIR / "web" / "data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_DELAY = 2  # seconds between requests to be polite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Known Goodreads URLs for Carissa Broadbent Books
# (pre-mapped for reliability — Goodreads search can be unreliable for scraping)
# ──────────────────────────────────────────────────────────────────────────────
BOOK_URLS = {
    "The Serpent and the Wings of Night": "https://www.goodreads.com/book/show/60714999-the-serpent-and-the-wings-of-night",
    "The Ashes & the Star-Cursed King": "https://www.goodreads.com/book/show/63826498-the-ashes-the-star-cursed-king",
    "The Songbird & the Heart of Stone": "https://www.goodreads.com/book/show/145624673-the-songbird-the-heart-of-stone",
    "Six Scorched Roses": "https://www.goodreads.com/book/show/63826439-six-scorched-roses",
    "Daughter of No Worlds": "https://www.goodreads.com/book/show/52780668-daughter-of-no-worlds",
    "Children of Fallen Gods": "https://www.goodreads.com/book/show/55316037-children-of-fallen-gods",
    "Mother of Death & Dawn": "https://www.goodreads.com/book/show/60522468-mother-of-death-dawn",
    "Slaying the Vampire Conqueror": "https://www.goodreads.com/book/show/199798553-slaying-the-vampire-conqueror",
    "Realm of Darkness": "https://www.goodreads.com/book/show/214127012-realm-of-darkness",
    "Fierce Hearts": "https://www.goodreads.com/book/show/53483506-fierce-hearts",
    "A Palace Fractured": "https://www.goodreads.com/book/show/53483507-a-palace-fractured",
    "Ashen Son": "https://www.goodreads.com/book/show/53483508-ashen-son",
    "Flirting with Darkness": "https://www.goodreads.com/book/show/55222888-flirting-with-darkness",
}


def get_book_names_from_dataset() -> list[str]:
    """Extract unique book names from the dataset, excluding 'No title'."""
    log.info("Loading dataset from %s", DATA_PATH)
    df = pd.read_excel(DATA_PATH)
    names = df["book_names"].unique().tolist()
    # Filter out placeholder titles
    names = [n for n in names if n.lower() not in ("no title", "no tittle")]
    log.info("Found %d unique books: %s", len(names), names)
    return names


def search_goodreads(book_title: str, author: str = "Carissa Broadbent") -> str | None:
    """Search Goodreads for a book and return the first result URL."""
    query = quote_plus(f"{book_title} {author}")
    search_url = f"https://www.goodreads.com/search?q={query}"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the first book link in search results
        book_link = soup.select_one("a.bookTitle")
        if book_link and book_link.get("href"):
            url = "https://www.goodreads.com" + book_link["href"]
            log.info("  Found search result: %s", url)
            return url
    except Exception as e:
        log.warning("  Search failed for '%s': %s", book_title, e)

    return None


def scrape_book_page(url: str) -> dict:
    """Scrape metadata from a Goodreads book page."""
    metadata = {
        "goodreads_url": url,
        "cover_url": None,
        "rating": None,
        "ratings_count": None,
        "genres": [],
        "pages": None,
        "publication_date": None,
        "series": None,
        "description": None,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ── Cover Image ──
        # Try Open Graph image first (most reliable)
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            metadata["cover_url"] = og_img["content"]

        # Fallback: look for the book cover img
        if not metadata["cover_url"]:
            cover_img = soup.select_one("img.BookCover__image, img.ResponsiveImage")
            if cover_img and cover_img.get("src"):
                metadata["cover_url"] = cover_img["src"]

        # ── Description ──
        # Try OG description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            metadata["description"] = og_desc["content"]

        # Try page description spans
        if not metadata["description"]:
            desc_el = soup.select_one(
                "[data-testid='description'] .Formatted, "
                ".BookPageMetadataSection__description .Formatted"
            )
            if desc_el:
                metadata["description"] = desc_el.get_text(strip=True)

        # ── Rating ──
        rating_el = soup.select_one(
            "[data-testid='averageRating'], "
            ".RatingStatistics__rating"
        )
        if rating_el:
            try:
                metadata["rating"] = float(rating_el.get_text(strip=True))
            except ValueError:
                pass

        # Try from JSON-LD structured data
        if not metadata["rating"]:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and "aggregateRating" in data:
                        metadata["rating"] = float(
                            data["aggregateRating"].get("ratingValue", 0)
                        )
                        metadata["ratings_count"] = int(
                            data["aggregateRating"].get("ratingCount", 0)
                        )
                        break
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

        # ── Genres ──
        genre_links = soup.select(
            "[data-testid='genresList'] a span.Button__labelItem, "
            "a[href*='/genres/'] .Button__labelItem"
        )
        if genre_links:
            metadata["genres"] = list(
                dict.fromkeys(g.get_text(strip=True) for g in genre_links)
            )

        # ── Pages ──
        pages_el = soup.select_one(
            "[data-testid='pagesFormat'], "
            "p[data-testid='pagesFormat']"
        )
        if pages_el:
            text = pages_el.get_text(strip=True)
            match = re.search(r"(\d+)\s*pages?", text, re.IGNORECASE)
            if match:
                metadata["pages"] = int(match.group(1))

        # ── Publication Date ──
        pub_el = soup.select_one(
            "[data-testid='publicationInfo'], "
            "p[data-testid='publicationInfo']"
        )
        if pub_el:
            metadata["publication_date"] = pub_el.get_text(strip=True)

        # ── Series ──
        series_el = soup.select_one(
            "h3[class*='BookPageTitleSection__title'] a, "
            "[data-testid='seriesTitle'] a"
        )
        if series_el:
            metadata["series"] = series_el.get_text(strip=True)

        # Also try from the page text
        if not metadata["series"]:
            title_section = soup.select_one("h3.Text__title3")
            if title_section:
                series_link = title_section.find("a")
                if series_link:
                    metadata["series"] = series_link.get_text(strip=True)

    except Exception as e:
        log.error("  Failed to scrape %s: %s", url, e)

    return metadata


def download_cover(cover_url: str, filename: str) -> str | None:
    """Download a cover image and return the local path."""
    if not cover_url:
        return None

    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    # Clean filename
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    ext = ".jpg"
    filepath = COVERS_DIR / f"{safe_name}{ext}"

    try:
        resp = requests.get(cover_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        filepath.write_bytes(resp.content)
        log.info("  Downloaded cover to %s", filepath)
        return str(filepath.relative_to(BASE_DIR))
    except Exception as e:
        log.warning("  Failed to download cover: %s", e)
        return None


def main():
    """Main scraping pipeline."""
    log.info("=" * 60)
    log.info("  Goodreads Metadata Scraper")
    log.info("=" * 60)

    # Get book names from dataset
    book_names = get_book_names_from_dataset()

    # Also get review counts and average ratings from dataset
    df = pd.read_excel(DATA_PATH)
    dataset_stats = {}
    for name in book_names:
        book_df = df[df["book_names"] == name]
        dataset_stats[name] = {
            "review_count": len(book_df),
            "unique_reviewers": book_df["usernames"].nunique(),
        }

    all_metadata = []

    for i, book_name in enumerate(book_names, 1):
        log.info("[%d/%d] Processing: %s", i, len(book_names), book_name)

        # Try pre-mapped URL first, then search
        url = BOOK_URLS.get(book_name)
        if not url:
            log.info("  No pre-mapped URL, searching Goodreads...")
            url = search_goodreads(book_name)
            time.sleep(REQUEST_DELAY)

        if not url:
            log.warning("  Could not find Goodreads page for '%s'", book_name)
            # Create minimal entry
            all_metadata.append({
                "title": book_name,
                "author": "Carissa Broadbent",
                "goodreads_url": None,
                "cover_url": None,
                "cover_local": None,
                "rating": None,
                "ratings_count": None,
                "genres": [],
                "pages": None,
                "publication_date": None,
                "series": None,
                "description": None,
                "dataset_review_count": dataset_stats.get(book_name, {}).get("review_count", 0),
                "dataset_unique_reviewers": dataset_stats.get(book_name, {}).get("unique_reviewers", 0),
            })
            continue

        # Scrape the book page
        scraped = scrape_book_page(url)
        time.sleep(REQUEST_DELAY)

        # Download cover image
        cover_local = download_cover(scraped["cover_url"], book_name)

        entry = {
            "title": book_name,
            "author": "Carissa Broadbent",
            **scraped,
            "cover_local": cover_local,
            "dataset_review_count": dataset_stats.get(book_name, {}).get("review_count", 0),
            "dataset_unique_reviewers": dataset_stats.get(book_name, {}).get("unique_reviewers", 0),
        }
        all_metadata.append(entry)

        log.info("  ✓ Rating: %s | Genres: %s | Cover: %s",
                 scraped["rating"],
                 scraped["genres"][:3] if scraped["genres"] else "N/A",
                 "Yes" if cover_local else "No")

    # Save metadata
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)
    log.info("Saved metadata to %s", OUTPUT_JSON)

    # Copy to web/data/ for the web app
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    web_json = WEB_DATA_DIR / "books_metadata.json"
    with open(web_json, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)
    log.info("Copied metadata to %s", web_json)

    # Summary
    log.info("=" * 60)
    log.info("  Scraping complete!")
    log.info("  Total books: %d", len(all_metadata))
    log.info("  With covers: %d", sum(1 for m in all_metadata if m.get("cover_local")))
    log.info("  With ratings: %d", sum(1 for m in all_metadata if m.get("rating")))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
