import json
import logging
import re
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
COVERS_DIR = BASE_DIR / "data" / "covers"
JSON_PATH = BASE_DIR / "data" / "books_metadata.json"
WEB_JSON_PATH = BASE_DIR / "web" / "data" / "books_metadata.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "image/*",
}

def main():
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        books = json.load(f)
        
    for i, book in enumerate(books):
        title = book.get("title", f"book_{i}")
        cover_url = book.get("cover_url")
        
        if cover_url:
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', title)
            # Sometimes URL doesn't end in .jpg, but we save as .jpg anyway
            filename = f"{safe_name}.jpg"
            filepath = COVERS_DIR / filename
            rel_path = f"data/covers/{filename}"
            
            try:
                logging.info(f"Downloading cover for: {title}")
                resp = requests.get(cover_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                with open(filepath, "wb") as img_file:
                    img_file.write(resp.content)
                book["cover_local"] = rel_path.replace("/", "\\") # Match existing format or use forward slash
            except Exception as e:
                logging.error(f"Failed to download cover for {title}: {e}")
        else:
            logging.warning(f"No cover URL for {title}")
            
    # Save back
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
    
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WEB_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
        
    logging.info("DONE downloading covers")

if __name__ == "__main__":
    main()
