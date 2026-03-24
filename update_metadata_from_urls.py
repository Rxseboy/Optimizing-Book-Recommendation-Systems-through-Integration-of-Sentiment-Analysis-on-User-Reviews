import json
import logging
import re
import time
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def scrape_book_page(url: str) -> dict:
    metadata = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Cover Image
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            metadata["cover_url"] = og_img["content"]
        else:
            cover_img = soup.select_one("img.BookCover__image, img.ResponsiveImage")
            if cover_img and cover_img.get("src"):
                metadata["cover_url"] = cover_img["src"]

        # Description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            metadata["description"] = og_desc["content"]
        else:
            desc_el = soup.select_one("[data-testid='description'] .Formatted, .BookPageMetadataSection__description .Formatted")
            if desc_el:
                metadata["description"] = desc_el.get_text(strip=True)

        # Rating
        rating_el = soup.select_one("[data-testid='averageRating'], .RatingStatistics__rating")
        if rating_el:
            try:
                metadata["rating"] = float(rating_el.get_text(strip=True))
            except ValueError:
                pass

        if "rating" not in metadata:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and "aggregateRating" in data:
                        metadata["rating"] = float(data["aggregateRating"].get("ratingValue", 0))
                        metadata["ratings_count"] = int(data["aggregateRating"].get("ratingCount", 0))
                        break
                except Exception:
                    pass
        
        # If we didn't find ratings_count from ld-json but we found ratings count elsewhere
        if "ratings_count" not in metadata:
            ratings_count_el = soup.select_one("[data-testid='ratingsCount']")
            if ratings_count_el:
                text = ratings_count_el.get_text(strip=True)
                match = re.search(r'([\d,]+)\s*ratings?', text)
                if match:
                    metadata["ratings_count"] = int(match.group(1).replace(',', ''))

        # Genres
        genre_links = soup.select("[data-testid='genresList'] a span.Button__labelItem, a[href*='/genres/'] .Button__labelItem")
        if genre_links:
            metadata["genres"] = list(dict.fromkeys(g.get_text(strip=True) for g in genre_links))

        # Pages
        pages_el = soup.select_one("[data-testid='pagesFormat'], p[data-testid='pagesFormat']")
        if pages_el:
            text = pages_el.get_text(strip=True)
            match = re.search(r"(\d+)\s*pages?", text, re.IGNORECASE)
            if match:
                metadata["pages"] = int(match.group(1))

        # Publication Date
        pub_el = soup.select_one("[data-testid='publicationInfo'], p[data-testid='publicationInfo']")
        if pub_el:
            metadata["publication_date"] = pub_el.get_text(strip=True)

        # Series
        series_el = soup.select_one("h3[class*='BookPageTitleSection__title'] a, [data-testid='seriesTitle'] a")
        if series_el:
            metadata["series"] = series_el.get_text(strip=True)
            
    except Exception as e:
        logging.error(f"Failed to scrape {url}: {e}")

    return metadata

def main():
    json_path = "c:/Users/rizqy/Desktop/Github-Repository-Management/File 1/data/books_metadata.json"
    
    with open(json_path, "r", encoding="utf-8") as f:
        books = json.load(f)
        
    for i, book in enumerate(books):
        url = book.get("goodreads_url")
        if url:
            logging.info(f"[{i+1}/{len(books)}] Scraping {url}")
            scraped_data = scrape_book_page(url)
            
            # Update fields if found
            for key in ["cover_url", "rating", "ratings_count", "genres", "pages", "publication_date", "series", "description"]:
                if scraped_data.get(key):
                    book[key] = scraped_data[key]
            
            time.sleep(2)
            
    # Save back
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
        
    # Also save to web folder
    web_json_path = "c:/Users/rizqy/Desktop/Github-Repository-Management/File 1/web/data/books_metadata.json"
    with open(web_json_path, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
        
    logging.info("DONE")

if __name__ == "__main__":
    main()
