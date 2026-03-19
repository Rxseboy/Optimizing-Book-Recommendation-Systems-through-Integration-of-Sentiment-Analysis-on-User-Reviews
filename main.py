"""
Sentiment-Based Book Recommendation System
============================================
A production pipeline that integrates sentiment analysis of Goodreads book
reviews with collaborative filtering to provide sentiment-enhanced book
recommendations.

Pipeline:
    1. Data Loading & Cleaning (language detection, deduplication)
    2. Text Preprocessing (NLP pipeline: lowercase, abbreviation expansion,
       special character removal, tokenization, stopword removal, lemmatization)
    3. Sentiment Analysis (KNN classifier with SMOTE oversampling)
    4. Collaborative Filtering (user–user cosine similarity)
    5. Sentiment-Enhanced Recommendation (predicted ratings × sentiment scores)

Author : Rizqi Fajar
Dataset: Goodreads Book Reviews of Carissa Broadbent
"""

# ──────────────────────────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────────────────────────
import os
import re
import string
import pickle
import logging
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import nltk
from nltk.corpus import stopwords as nltk_stopwords
from nltk.tokenize import word_tokenize, RegexpTokenizer
from nltk.stem import WordNetLemmatizer
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.preprocessing import MinMaxScaler
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "Dataset_Goodreads_Book_of_Carissa_Broadbent_Fix.xlsx"
MODEL_DIR = BASE_DIR / "model"
RANDOM_STATE = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Ensure reproducibility for language detection
DetectorFactory.seed = 0


# ──────────────────────────────────────────────────────────────────────────────
# 1. Data Loading & Cleaning
# ──────────────────────────────────────────────────────────────────────────────
class DataLoader:
    """Load and perform initial cleaning of the Goodreads dataset."""

    MIN_WORD_COUNT = 2

    def __init__(self, file_path: Path = DATA_PATH):
        self.file_path = file_path

    # ---- helpers ----
    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect language of a text string using langdetect."""
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"

    @staticmethod
    def _word_count(text: str) -> int:
        """Count the number of words in a text string."""
        return len(text.split())

    # ---- main ----
    def load_and_clean(self) -> pd.DataFrame:
        """
        Load the Excel dataset and apply initial filters:
          - Convert reviews to string
          - Remove reviews with fewer than MIN_WORD_COUNT words
          - Keep only English‑language reviews
          - Remove rows with 'No tittle' book names
          - Drop duplicate rows
        """
        log.info("Loading dataset from %s", self.file_path)
        df = pd.read_excel(self.file_path)
        log.info("Raw dataset shape: %s", df.shape)

        df["reviews"] = df["reviews"].astype(str)

        # Word‑count filter
        df["word_count"] = df["reviews"].apply(self._word_count)
        df = df[df["word_count"] >= self.MIN_WORD_COUNT]

        # Language filter
        log.info("Detecting languages (may take a minute)...")
        df["language"] = df["reviews"].apply(self._detect_language)
        df = df[df["language"] == "en"]

        # Remove placeholder titles
        df = df[df["book_names"] != "No tittle"]

        # Deduplication
        before = len(df)
        df.drop_duplicates(keep="first", inplace=True)
        log.info("Removed %d duplicate rows", before - len(df))

        log.info("Cleaned dataset shape: %s", df.shape)
        return df


# ──────────────────────────────────────────────────────────────────────────────
# 2. Text Preprocessing
# ──────────────────────────────────────────────────────────────────────────────
class TextPreprocessor:
    """NLP preprocessing pipeline for review text."""

    # Contraction mapping
    CONTRACTIONS = {
        "isn't": "is not", "he's": "he is", "wasn't": "was not",
        "there's": "there is", "couldn't": "could not", "won't": "will not",
        "they're": "they are", "she's": "she is", "wouldn't": "would not",
        "haven't": "have not", "that's": "that is", "you've": "you have",
        "what's": "what is", "weren't": "were not", "we're": "we are",
        "hasn't": "has not", "you'd": "you would", "shouldn't": "should not",
        "let's": "let us", "they've": "they have", "you'll": "you will",
        "i'm": "i am", "we've": "we have", "it's": "it is",
        "don't": "do not", "that\u00b4s": "that is", "i\u00b4m": "i am",
        "it\u2019s": "it is", "she\u00b4s": "she is", "he's'": "he is",
        "i\u2019m": "i am", "i\u2019d": "i did",
    }

    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "]+",
        flags=re.UNICODE,
    )

    def __init__(self):
        # Download required NLTK data
        for resource in ["stopwords", "punkt", "punkt_tab", "wordnet",
                         "averaged_perceptron_tagger",
                         "averaged_perceptron_tagger_eng"]:
            nltk.download(resource, quiet=True)

        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(nltk_stopwords.words("english"))
        self.tokenizer = RegexpTokenizer(r"\w+")

    # ---- step functions ----
    def clean_initial(self, text: str) -> str:
        """Initial cleaning: handle non‑strings, tokenize, lemmatize, remove stop words."""
        if not isinstance(text, str):
            return ""
        stop = list(nltk_stopwords.words("english"))
        punc = list(string.punctuation)
        bad_tokens = set(stop + punc)
        lemma = WordNetLemmatizer()
        tokens = word_tokenize(text)
        word_tokens = [t for t in tokens if t.isalpha()]
        clean_tokens = [lemma.lemmatize(t.lower()) for t in word_tokens if t.lower() not in bad_tokens]
        return " ".join(clean_tokens)

    def lowercase(self, text: str) -> str:
        return text.lower()

    def expand_contractions(self, text: str) -> str:
        for contraction, expansion in self.CONTRACTIONS.items():
            text = re.sub(re.escape(contraction), expansion, text)
        return text

    def remove_noise(self, text: str) -> str:
        """Remove URLs, numbers, HTML tags, punctuation, newlines, emojis."""
        text = text.strip()
        text = re.sub(r"https?://\S+|www\.\S+", "", text)
        text = re.sub(r"\b\d+\b", "", text)
        text = re.sub(r"<.*?>+", "", text)
        text = re.sub("[%s]" % re.escape(string.punctuation), "", text)
        text = re.sub(r"\n", "", text)
        text = re.sub("[\u2018\u201c\u201d\u2026]", "", text)
        text = self.EMOJI_PATTERN.sub("", text)
        return text

    def lemmatize_token(self, token: str) -> str:
        """Multi‑pass lemmatization across all POS tags."""
        for pos in ("v", "n", "a", "r", "s"):
            result = self.lemmatizer.lemmatize(token, pos)
            if result != token:
                return result
        return token

    @staticmethod
    def extract_nouns(tokens: list) -> list:
        """POS‑tag tokens and keep only nouns (NN*)."""
        tagged = nltk.pos_tag(tokens)
        return [tok for tok, tag in tagged if tag.startswith("NN")]

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the full preprocessing pipeline to the DataFrame:
          lowercase → expand contractions → remove noise →
          tokenize → remove stopwords → lemmatize → rejoin
        """
        log.info("Applying text preprocessing pipeline...")
        col = "cleaned_reviews"

        df[col] = df[col].apply(self.lowercase)
        df[col] = df[col].apply(self.expand_contractions)
        df[col] = df[col].apply(self.remove_noise)

        # Tokenize
        df["tokenized"] = df[col].apply(self.tokenizer.tokenize)

        # Remove stopwords
        df["tokenized"] = df["tokenized"].apply(
            lambda tokens: [t for t in tokens if t not in self.stop_words]
        )

        # Lemmatize
        df["lemmatized"] = df["tokenized"].apply(
            lambda tokens: [self.lemmatize_token(t) for t in tokens]
        )

        # Rejoin into clean text
        df["clean_text"] = df["lemmatized"].apply(lambda x: " ".join(x))

        # Extract nouns for aspect analysis
        df["nouns"] = df["lemmatized"].apply(self.extract_nouns)
        df["nouns_merge"] = df["nouns"].apply(lambda x: " ".join(x))

        log.info("Preprocessing complete.")
        return df


# ──────────────────────────────────────────────────────────────────────────────
# 3. Sentiment Analysis
# ──────────────────────────────────────────────────────────────────────────────
class SentimentAnalyzer:
    """
    KNN‑based sentiment classifier using CountVectorizer + SMOTE.

    Sentiment rules:
        - Rating 4–5 → positive
        - Rating 1–2 → negative
        - Rating 3 / No Rating → undecided (excluded from training)
    """

    def __init__(self, random_state: int = RANDOM_STATE):
        self.random_state = random_state
        self.vectorizer: CountVectorizer | None = None
        self.model: KNeighborsClassifier | None = None
        self.word_vectorizer: TfidfVectorizer | None = None

    # ---- sentiment encoding ----
    @staticmethod
    def encode_sentiment(rating) -> str:
        if rating in (4, 5):
            return "positive"
        elif rating in (1, 2):
            return "negative"
        return "undecided"

    @staticmethod
    def label_encode(sentiment: str) -> int:
        return 1 if sentiment == "positive" else 0

    # ---- training pipeline ----
    def prepare_labels(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Add sentiment and sentiment_label columns to the dataset."""
        dataset["ratings"] = dataset["ratings"].apply(
            lambda x: "No Rating" if x == "No Rating" else int(x.split(" ")[1])
        )
        dataset["sentiment"] = dataset["ratings"].apply(self.encode_sentiment)
        dataset["sentiment_label"] = dataset["sentiment"].apply(self.label_encode)
        return dataset

    def train(self, dataset: pd.DataFrame, preprocessor: TextPreprocessor):
        """
        Full training pipeline:
            1. Filter rated reviews (exclude undecided)
            2. Undersample for balance
            3. Preprocess text
            4. Split train/test (90:10)
            5. Vectorize with CountVectorizer
            6. Oversample with SMOTE
            7. Find optimal K via accuracy sweep
            8. Train final KNN model
        """
        # Step 1: Filter to rated only
        rated = dataset[dataset["sentiment"] != "undecided"].copy()
        rated = rated.dropna(subset=["cleaned_reviews"])
        df = rated[["cleaned_reviews", "sentiment_label"]].copy()

        # Step 2: Random undersample
        rus = RandomUnderSampler(random_state=0)
        df, df["sentiment_label"] = rus.fit_resample(
            df[["cleaned_reviews"]], df["sentiment_label"]
        )
        log.info("After undersampling: %s", df["sentiment_label"].value_counts().to_dict())

        # Step 3: Preprocess
        df = preprocessor.preprocess(df)

        # Step 4: Split
        X = df["clean_text"]
        y = df["sentiment_label"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.1, shuffle=True, random_state=self.random_state
        )
        X_train = X_train.fillna("")
        X_test = X_test.fillna("")
        log.info("Train size: %d | Test size: %d", len(X_train), len(X_test))

        # Step 5: Count Vectorizer
        self.vectorizer = CountVectorizer()
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)

        # Step 6: SMOTE oversampling
        smote = SMOTE(random_state=self.random_state)
        X_train_res, y_train_res = smote.fit_resample(X_train_vec, y_train)

        # Step 7: Find optimal K
        value_count = y_train_res.value_counts()
        index_range = int(value_count.max() * len(value_count))
        log.info("Searching for optimal K in range 1..%d", index_range)

        accuracies = []
        for k in range(1, index_range + 1):
            knn = KNeighborsClassifier(n_neighbors=k).fit(X_train_res, y_train_res)
            y_pred = knn.predict(X_test_vec)
            accuracies.append(accuracy_score(y_test, y_pred))

        best_k = accuracies.index(max(accuracies)) + 1
        log.info("Best K = %d (accuracy = %.4f)", best_k, max(accuracies))

        # Step 8: Train final model
        self.model = KNeighborsClassifier(n_neighbors=best_k).fit(
            X_train_res, y_train_res
        )

        # Evaluate
        y_pred_test = self.model.predict(X_test_vec)
        self._evaluate(y_test, y_pred_test, label="Test")

        # Store references for later
        self._X_train = X_train
        self._rated_dataset = rated

        return dataset

    def predict_no_rating(self, dataset: pd.DataFrame):
        """Predict sentiment for reviews with 'No Rating'."""
        reverse_map = {1: "positive", 0: "negative"}
        no_rating = dataset[dataset["ratings"] == "No Rating"].copy()
        no_rating = no_rating.dropna(subset=["cleaned_reviews"])

        # Fit TF-IDF on combined training + no-rating reviews
        all_reviews = pd.concat(
            [self._X_train, no_rating["cleaned_reviews"]], ignore_index=True
        )
        self.word_vectorizer = TfidfVectorizer(max_features=6852, stop_words="english")
        self.word_vectorizer.fit(all_reviews)

        X_no_rating = self.word_vectorizer.transform(no_rating["cleaned_reviews"])
        preds = self.model.predict(X_no_rating)
        no_rating["sentiment"] = [reverse_map[p] for p in preds]

        log.info("Predicted sentiment for %d 'No Rating' reviews", len(no_rating))
        return no_rating

    def build_full_dataset(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """Combine rated + predicted‑no‑rating into a single prediction dataset."""
        no_rating_df = self.predict_no_rating(dataset)
        rated = self._rated_dataset

        combined = pd.concat([rated, no_rating_df])
        combined = combined.dropna(subset=["sentiment"])
        combined = combined.drop_duplicates(subset=["cleaned_reviews"])
        combined.reset_index(drop=True, inplace=True)
        combined = combined[combined["book_names"] != "No tittle"]

        log.info("Full prediction dataset: %d rows", len(combined))
        return combined

    def save_models(self):
        """Persist KNN model and TF-IDF vectorizer to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        pickle.dump(self.model, open(MODEL_DIR / "knn_model.pkl", "wb"))
        pickle.dump(
            self.word_vectorizer, open(MODEL_DIR / "word_vectorizer.pkl", "wb")
        )
        log.info("Saved KNN model and word vectorizer to %s", MODEL_DIR)

    # ---- evaluation helpers ----
    @staticmethod
    def _evaluate(y_true, y_pred, label: str = ""):
        """Print classification metrics."""
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()
        acc = accuracy_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        sensitivity = round(tp / (fn + tp), 4) if (fn + tp) > 0 else 0
        specificity = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0

        log.info("─── %s Evaluation ───", label)
        log.info("Accuracy   : %.4f", acc)
        log.info("F1 Score   : %.4f", f1)
        log.info("Sensitivity: %.4f", sensitivity)
        log.info("Specificity: %.4f", specificity)
        print(classification_report(y_true, y_pred, target_names=["negative", "positive"]))


# ──────────────────────────────────────────────────────────────────────────────
# 4. Recommendation Engine
# ──────────────────────────────────────────────────────────────────────────────
class RecommendationEngine:
    """
    User–user collaborative filtering recommendation system
    enhanced with sentiment scores.
    """

    def __init__(self, random_state: int = RANDOM_STATE, top_n: int = 6):
        self.random_state = random_state
        self.top_n = top_n
        self.user_final_rating: pd.DataFrame | None = None

    @staticmethod
    def _pivot(df: pd.DataFrame, fill=None) -> pd.DataFrame:
        """Create a user × book pivot table of ratings."""
        pivot = df.pivot_table(index="usernames", columns="book_names", values="ratings")
        if fill is not None:
            pivot = pivot.fillna(fill)
        return pivot

    def build(self, dataset: pd.DataFrame):
        """
        Build the collaborative filtering model:
            1. Train/test split
            2. Compute user–item pivot tables
            3. Compute user‑similarity matrix (cosine)
            4. Predict ratings via matrix multiplication
        """
        log.info("Building recommendation engine...")

        # Split
        train, test = train_test_split(
            dataset, test_size=0.1, random_state=self.random_state
        )
        test = test[test.usernames.isin(train.usernames)]

        # Convert ratings to numeric
        train["ratings"] = pd.to_numeric(train["ratings"], errors="coerce").fillna(0)
        test["ratings"] = pd.to_numeric(test["ratings"], errors="coerce").fillna(0)

        # Pivot tables
        train_pivot = self._pivot(train, fill=0)
        test_pivot = self._pivot(test, fill=0)

        # Dummy matrices (mask already‑rated items)
        dummy_train = train.copy()
        dummy_train["ratings"] = dummy_train["ratings"].apply(lambda x: 0 if x >= 1 else 1)
        dummy_train = self._pivot(dummy_train, fill=1)

        # Mean‑centered ratings
        mean_ratings = np.nanmean(self._pivot(train), axis=1)
        subtracted = (self._pivot(train).T - mean_ratings).T.fillna(0)

        # User similarity (cosine)
        user_corr = 1 - pairwise_distances(subtracted, metric="cosine")
        user_corr = np.nan_to_num(user_corr, nan=0)

        # Predicted ratings
        predicted = np.dot(user_corr, train_pivot)
        self.user_final_rating = pd.DataFrame(
            np.multiply(predicted, dummy_train),
            index=train_pivot.index,
            columns=train_pivot.columns,
        )

        # Evaluation
        self._evaluate_recommendation(
            user_corr, subtracted, train, test, train_pivot, test_pivot
        )

        log.info("Recommendation engine built successfully.")
        return self

    def recommend(
        self,
        username: str,
        dataset: pd.DataFrame,
        sentiment_analyzer: SentimentAnalyzer,
    ) -> pd.DataFrame:
        """
        Get top‑N sentiment‑enhanced recommendations for a user.

        Score = 1 × predicted_rating + 2 × normalized_sentiment_score
        """
        if self.user_final_rating is None:
            raise RuntimeError("Call build() before recommend().")

        # Base recommendations
        user_ratings = self.user_final_rating.loc[username].sort_values(ascending=False)
        recs = user_ratings.head(self.top_n)
        recs = pd.DataFrame(recs).reset_index()
        recs.columns = ["book_names", "predicted_ratings"]

        # Scale predicted ratings to 1–5
        scaler = MinMaxScaler(feature_range=(1, 5))
        recs["predicted_ratings"] = scaler.fit_transform(recs[["predicted_ratings"]])

        # Remove zero‑prediction items
        recs = recs[recs["predicted_ratings"] > 1.0]

        # Add sentiment scores
        def _get_sentiment_score(book_name: str) -> float:
            reviews = dataset[dataset["book_names"] == book_name]["reviews"].tolist()
            if not reviews:
                return 0.5
            features = sentiment_analyzer.word_vectorizer.transform(reviews)
            return sentiment_analyzer.model.predict(features).mean()

        recs["sentiment_score"] = recs["book_names"].apply(_get_sentiment_score)

        # Normalize sentiment scores
        if len(recs) > 1:
            scaler.fit(recs[["sentiment_score"]])
            recs["sentiment_score"] = scaler.transform(recs[["sentiment_score"]])

        # Final ranking
        recs["ranking_score"] = (
            1 * recs["predicted_ratings"] + 2 * recs["sentiment_score"]
        )
        recs = recs.sort_values("ranking_score", ascending=False)

        return recs

    def save_model(self):
        """Persist the user final rating matrix."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        pickle.dump(
            self.user_final_rating, open(MODEL_DIR / "user_final_rating.pkl", "wb")
        )
        log.info("Saved user_final_rating to %s", MODEL_DIR)

    # ---- evaluation ----
    def _evaluate_recommendation(self, user_corr, subtracted, train, test,
                                  train_pivot, test_pivot):
        """Calculate RMSE and MAE for the recommendation system."""
        user_corr_df = pd.DataFrame(
            user_corr, index=subtracted.index, columns=subtracted.index
        )

        # Filter correlation to test users
        test_users = list(set(test.usernames) & set(user_corr_df.index))
        if not test_users:
            log.warning("No overlapping test users for evaluation.")
            return

        corr_test = user_corr_df.loc[test_users, test_users]
        predicted_test = np.dot(corr_test, test_pivot.reindex(test_users, fill_value=0))

        # Dummy test
        dummy_test = test.copy()
        dummy_test["ratings"] = dummy_test["ratings"].apply(lambda x: 1 if x >= 1 else 0)
        dummy_test_pivot = self._pivot(dummy_test, fill=0)
        dummy_test_pivot = dummy_test_pivot.reindex(test_users, fill_value=0)

        predicted_test = np.multiply(predicted_test, dummy_test_pivot)

        # Compute metrics
        true_ratings = test_pivot.reindex(test_users, fill_value=0).values
        pred_values = np.nan_to_num(np.array(predicted_test), nan=0)

        rmse = np.sqrt(np.mean((true_ratings - pred_values) ** 2))
        mae = np.mean(np.abs(true_ratings - pred_values))

        log.info("Recommendation RMSE: %.4f", rmse)
        log.info("Recommendation MAE : %.4f", mae)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Main Pipeline
# ──────────────────────────────────────────────────────────────────────────────
def main():
    """Orchestrate the full sentiment + recommendation pipeline."""
    log.info("=" * 60)
    log.info("  Sentiment-Based Book Recommendation System")
    log.info("=" * 60)

    # ── Step 1: Load & Clean Data ──
    loader = DataLoader()
    dataset = loader.load_and_clean()

    # ── Step 2: Initial Text Cleaning ──
    preprocessor = TextPreprocessor()
    dataset["cleaned_reviews"] = dataset["reviews"].apply(preprocessor.clean_initial)

    # ── Step 3: Sentiment Analysis ──
    analyzer = SentimentAnalyzer()
    dataset = analyzer.prepare_labels(dataset)
    dataset = analyzer.train(dataset, preprocessor)
    prediction_dataset = analyzer.build_full_dataset(dataset)
    analyzer.save_models()

    # ── Step 4: Build Recommendation Engine ──
    engine = RecommendationEngine(top_n=6)
    engine.build(prediction_dataset)
    engine.save_model()

    # ── Step 5: Generate Sample Recommendations ──
    target_user = prediction_dataset["usernames"].value_counts().index[1]
    log.info("Generating recommendations for user: '%s'", target_user)

    recommendations = engine.recommend(target_user, prediction_dataset, analyzer)

    print("\n" + "=" * 60)
    print(f"  Top Recommendations for '{target_user}'")
    print("=" * 60)
    print(recommendations.to_string(index=False))
    print()

    log.info("Pipeline complete. Models saved to %s/", MODEL_DIR)


if __name__ == "__main__":
    main()
