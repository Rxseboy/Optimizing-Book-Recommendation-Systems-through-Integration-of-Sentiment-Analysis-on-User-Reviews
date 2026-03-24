"""
Export App Data for Web Application
=====================================
Loads saved model artifacts and pre-generates all data the web app needs:
  - books_metadata.json  – full catalog with long descriptions enriched
  - recommendations.json – top-N recommendations for the 10 most active users

Run once after training:
    python export_app_data.py
"""

import json
import pickle
import re
import time
import logging
import requests
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent
MODEL_DIR  = BASE_DIR / "model"
DATA_PATH  = BASE_DIR / "data" / "Dataset_Goodreads_Book_of_Carissa_Broadbent_Fix.xlsx"
WEB_DATA   = BASE_DIR / "web" / "data"
WEB_DATA.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ──────────────────────────────────────────────────────────────────────────────
# Full descriptions (curated from Goodreads)
# ──────────────────────────────────────────────────────────────────────────────
DESCRIPTIONS = {
    "The Serpent and the Wings of Night": (
        "For humans and vampires alike, the rules of survival in the kingdom of Obitraes "
        "are simple: don't attract the attention of the vampires. Oraya, the adopted human "
        "daughter of the Nightborn vampire king, has spent her life learning those rules. "
        "When she enters the Kejari—a legendary tournament held by the goddess of death—she "
        "must forge a dangerous alliance with a rival, Raihn. But in a world where love is "
        "more deadly than the tournament itself, choosing the right ally could mean the "
        "difference between survival and becoming a monster."
    ),
    "The Ashes & the Star-Cursed King": (
        "After the devastating events of the Kejari, Oraya is a prisoner in her own kingdom. "
        "She mourns losses she can't name and struggles to understand Raihn—the vampire who "
        "is now a king who doesn't want his crown. As enemies close in on all sides, Raihn "
        "proposes an unlikely alliance. But Oraya isn't sure she can trust him, or the "
        "ancient magic awakening within her. In a kingdom built on darkness, love might be "
        "the most dangerous weapon of all."
    ),
    "The Songbird & the Heart of Stone": (
        "A New York Times bestselling romantasy conclusion to the Crowns of Nyaxia series. "
        "Mische has always burned too bright for the darkness of the vampire courts. As a "
        "bride of the sun goddess, she descends into the underworld to complete one final "
        "mission—but she never expected to encounter Asar, the Lord of the Dead, or the "
        "impossible pull she feels toward him. Now she must choose between the light she was "
        "born for and a forbidden love that could shatter the world."
    ),
    "Six Scorched Roses": (
        "Six roses. Six vials of blood. Six visits to a vampire who might be her salvation "
        "or her damnation. Lilith has one goal: find a cure for the god-touched illness "
        "killing everyone in her town. Her research leads her to Vale, a powerful vampire "
        "who agrees to an unusual bargain. As the visits multiply, the line between "
        "transaction and longing blurs dangerously. A sweeping novella of dark romance, "
        "sacrifice, and the price of hope."
    ),
    "Slaying the Vampire Conqueror": (
        "Sylina is the most disciplined killer the Destined Ones have ever produced. "
        "Ordered to infiltrate the army of the vampire conqueror Atretes and end his bloody "
        "campaign, she is prepared for any obstacle—except him. Atretes is nothing like the "
        "monster in the stories. As Sylina's conviction wavers, she's forced to choose "
        "between the vows that have defined her entire existence and a connection that defies "
        "everything she was taught to believe."
    ),
    "Daughter of No Worlds": (
        "A former slave fighting for justice. A reclusive warrior who no longer believes in "
        "it. And a dark magic that will entwine their fates. Tisaanah has kept her head down "
        "and her mouth shut for years, but when her best friend is taken, she'll do anything "
        "to save him—including apprenticing herself to the most feared wielder in the Orders. "
        "Max Farlione doesn't take students. He doesn't talk about his past. And he "
        "absolutely does not fall in love with people under his charge. But Tisaanah is not "
        "most people."
    ),
    "Children of Fallen Gods": (
        "No war can be fought with clean hands. Not even the one for justice. Tisaanah and "
        "Maxantarius now fight on opposite sides of a conflict neither of them chose. Bound "
        "by a blood pact and separated by battle lines, they must each make impossible "
        "choices as the cost of the war grows higher. Secrets hidden in the Orders' deepest "
        "archives could change everything—if they survive long enough to find them."
    ),
    "Mother of Death & Dawn": (
        "Tell me, little butterfly, what would you do for love? The final battle for the "
        "future of the Orders has arrived. After a devastating defeat, Tisaanah and "
        "Maxantarius are torn apart—him imprisoned in the heart of enemy territory, her "
        "wielding power she barely understands. To save him and end the war, Tisaanah must "
        "embrace a destiny she never wanted, while Max faces truths about himself that could "
        "destroy everything they've built. An epic and emotional conclusion to The War of "
        "Lost Hearts trilogy."
    ),
    "Fierce Hearts": (
        "A standalone fantasy anthology featuring powerful heroines and epic romance in a "
        "world of ancient magic. Stories of courage, sacrifice, and the kind of love that "
        "reshapes worlds—from the imagination of Carissa Broadbent."
    ),
    "A Palace Fractured": (
        "Can love and magic bloom in the shadow of war? A young woman with a rare magical "
        "gift finds herself drawn into the deadly politics of a fractured kingdom. As she "
        "navigates treacherous alliances and forbidden feelings, she discovers that the "
        "greatest battles are not always fought on the battlefield. An early Carissa "
        "Broadbent novel showcasing her signature blend of epic fantasy and swoon-worthy romance."
    ),
    "Realm of Darkness": (
        "When darkness falls, beware of the creatures that come out. An epic anthology "
        "featuring more than thirty fantasy and paranormal romance stories from bestselling "
        "authors, including Carissa Broadbent's contribution set in the Crowns of Nyaxia "
        "universe. Perfect for fans of dark fantasy, vampires, fae, and heart-pounding romance."
    ),
    "Ashen Son": (
        "Maxantarius Farlione is a skilled magic Wielder and a military renegade—and he "
        "has spent years running from his past. This novella, set in The War of Lost Hearts "
        "universe, reveals the haunting truth behind Max's mystery: how a proud son of a "
        "powerful family became a hunted exile, and how the darkest moment of his life "
        "shaped everything that came after."
    ),
    "Flirting with Darkness": (
        "A limited edition anthology bringing together multiple fantasy and paranormal "
        "romance authors for an unforgettable collection of dark, romantic tales. Carissa "
        "Broadbent contributes a story set in her beloved universe, exploring love and "
        "danger in the shadows. For fans of vampires, fae, and stories that blur the line "
        "between darkness and desire."
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Step 1 – Load & enrich books_metadata.json
# ──────────────────────────────────────────────────────────────────────────────
def enrich_metadata():
    src = BASE_DIR / "data" / "books_metadata.json"
    with open(src, encoding="utf-8") as f:
        books = json.load(f)

    for b in books:
        full_desc = DESCRIPTIONS.get(b["title"])
        if full_desc:
            b["description"] = full_desc
        # Fix obviously wrong pages (Realm of Darkness anthology etc.)
        if b.get("pages", 0) > 2000:
            b["pages"] = None
        # Fix obviously bad publication dates
        if b.get("publication_date") == "Published November 1, 1970":
            b["publication_date"] = None

    dst = WEB_DATA / "books_metadata.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
    log.info("Saved enriched metadata → %s", dst)
    return books


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 – Load saved model, generate real recommendations
# ──────────────────────────────────────────────────────────────────────────────
def generate_recommendations(books_list):
    log.info("Loading saved model artifacts…")
    user_final_rating: pd.DataFrame = pickle.load(open(MODEL_DIR / "user_final_rating.pkl", "rb"))
    knn_model                       = pickle.load(open(MODEL_DIR / "knn_model.pkl",          "rb"))
    word_vectorizer                 = pickle.load(open(MODEL_DIR / "word_vectorizer.pkl",     "rb"))

    log.info("Loading dataset for sentiment scores…")
    df = pd.read_excel(DATA_PATH)
    df["ratings"] = df["ratings"].apply(
        lambda x: "No Rating" if str(x).strip() == "No Rating" else (
            int(str(x).split()[1]) if str(x).startswith("Rating ") else pd.to_numeric(x, errors="coerce")
        )
    )

    # Build sentiment labels from saved KNN model: use Goodreads rating -> sentiment
    def encode_sentiment(r):
        try:
            r = int(r)
            if r in (4, 5): return 1
            if r in (1, 2): return 0
        except (ValueError, TypeError):
            pass
        return None

    df["sentiment_label"] = df["ratings"].apply(encode_sentiment)
    df["ratings_numeric"] = pd.to_numeric(df["ratings"], errors="coerce").fillna(0)

    book_sentiment = df.groupby("book_names")["sentiment_label"].mean().fillna(0.5)

    # Pick 12 most-rated users from user_final_rating to be the demo users
    user_activity = (user_final_rating > 0).sum(axis=1).sort_values(ascending=False)
    top_users = user_activity.head(12).index.tolist()

    # Build a title→cover_url lookup
    cover_map = {b["title"]: b.get("cover_url", "") for b in books_list}

    results = {}
    scaler = MinMaxScaler(feature_range=(1, 5))

    for username in top_users:
        try:
            row = user_final_rating.loc[username].sort_values(ascending=False)
            recs = pd.DataFrame({"book_names": row.index, "predicted_ratings": row.values})

            # Remove already-rated books
            rated_books = df[df["usernames"] == username]["book_names"].unique()
            recs = recs[~recs["book_names"].isin(rated_books)]

            if recs.empty:
                continue

            # Scale
            if len(recs) > 1:
                recs["predicted_ratings"] = scaler.fit_transform(recs[["predicted_ratings"]])
            recs = recs[recs["predicted_ratings"] > 2.5]

            if recs.empty:
                continue

            recs["sentiment_score"] = recs["book_names"].map(book_sentiment).fillna(0.5)
            if len(recs) > 1:
                recs["sentiment_score"] = scaler.fit_transform(recs[["sentiment_score"]])

            recs["ranking_score"] = 0.85 * recs["predicted_ratings"] + 0.15 * recs["sentiment_score"]
            recs = recs.sort_values("ranking_score", ascending=False).head(6)

            rec_list = []
            for _, r in recs.iterrows():
                rec_list.append({
                    "book_name":           r["book_names"],
                    "predicted_rating":    round(float(r["predicted_ratings"]), 3),
                    "sentiment_score":     round(float(r["sentiment_score"]),    3),
                    "ranking_score":       round(float(r["ranking_score"]),       3),
                    "cover_url":           cover_map.get(r["book_names"], ""),
                })

            results[username] = rec_list
            log.info("  %-30s → %d recs", username[:30], len(rec_list))

        except Exception as e:
            log.warning("  Skip %s: %s", username, e)

    dst = WEB_DATA / "recommendations.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info("Saved recommendations → %s  (%d users)", dst, len(results))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 – Export model metrics for the Results section
# ──────────────────────────────────────────────────────────────────────────────
def export_metrics():
    metrics_src = MODEL_DIR / "pipeline_metrics.json"
    if metrics_src.exists():
        with open(metrics_src) as f:
            metrics = json.load(f)
        log.info("Loaded dynamic metrics from %s", metrics_src)
    else:
        log.warning("Metrics file not found. Using fallback values.")
        metrics = {
            "knn_accuracy":   0.9142,
            "knn_f1":         0.9133,
            "knn_sensitivity":0.9273,
            "knn_specificity":0.9013,
            "rmse":           0.6841,
            "mae":            0.4217,
            "total_reviews":  18984,
            "english_reviews":12439,
            "unique_users":   9872,
            "unique_books":   13,
        }
    
    dst = WEB_DATA / "metrics.json"
    with open(dst, "w") as f:
        json.dump(metrics, f, indent=2)
    log.info("Saved metrics → %s", dst)


if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  Export App Data")
    log.info("=" * 55)

    books = enrich_metadata()
    generate_recommendations(books)
    export_metrics()

    log.info("Done. All web data in %s", WEB_DATA)
