# Sentiment-Based Book Recommendation System

A machine learning pipeline that integrates **Sentiment Analysis** of Goodreads book reviews with a **Collaborative Filtering Recommendation System** to provide sentiment-enhanced book recommendations.

## 📋 Objective

Build a recommendation system that goes beyond traditional collaborative filtering by incorporating **review sentiment** into the ranking algorithm. This produces more meaningful recommendations by weighting books that not only match user preferences but also have overwhelmingly positive reader sentiment.

## 🔍 Problem Statement

Traditional recommendation systems rely solely on numerical ratings, ignoring the rich context embedded in text reviews. A book rated 4/5 could have a glowing review or a lukewarm one — **sentiment analysis bridges this gap** by extracting the true opinion from review text.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA PIPELINE                           │
│  Excel Dataset → Language Detection → Deduplication         │
│                     → Text Cleaning                         │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌─────────────────────┐     ┌──────────────────────────┐
│ SENTIMENT ANALYSIS  │     │ COLLABORATIVE FILTERING  │
│                     │     │                          │
│ Text Preprocessing  │     │ User-Item Pivot Matrix   │
│ ↓                   │     │ ↓                        │
│ TF-IDF Vectorizer   │     │ Cosine Similarity        │
│ ↓                   │     │ ↓                        │
│ KNN Classifier      │     │ Predicted Ratings        │
│ (SMOTE + CountVec)  │     │                          │
└─────────┬───────────┘     └────────────┬─────────────┘
          │                              │
          └──────────┬───────────────────┘
                     ▼
      ┌────────────────────────────────┐
      │  SENTIMENT-ENHANCED RANKING   │
      │                                │
      │  Score = 1×Rating + 2×Sentiment│
      │  → Top-N Recommendations       │
      └────────────────────────────────┘
```

## 🛠️ Tools & Technologies

| Category         | Technology                                          |
|------------------|-----------------------------------------------------|
| Language         | Python 3.10+                                        |
| Data Processing  | Pandas, NumPy                                       |
| NLP              | NLTK (tokenization, lemmatization, POS tagging)     |
| Language Detection| langdetect                                         |
| ML / Classification | scikit-learn (KNN), imbalanced-learn (SMOTE)     |
| Vectorization    | CountVectorizer, TF-IDF                             |
| Similarity       | Cosine Similarity (sklearn pairwise_distances)      |
| Visualization    | Matplotlib, Seaborn, WordCloud                      |

## 📊 Dataset

- **Source**: Goodreads book reviews of Carissa Broadbent's works
- **Size**: ~18,000+ raw reviews → ~16,600 after cleaning
- **Columns**: `authors`, `book_names`, `usernames`, `ratings`, `reviews`
- **Books**: 13 titles including *The Serpent and the Wings of Night*, *Daughter of No Worlds*, and more

## 📈 Key Results

| Metric                    | Value         |
|---------------------------|---------------|
| KNN Sentiment Accuracy    | ~0.70–0.85    |
| Sentiment F1 Score        | ~0.70–0.85    |
| Recommendation RMSE       | Computed at runtime |
| Recommendation MAE        | Computed at runtime |

> **Note**: Exact metrics depend on the random seed and dataset split. Run the pipeline to see current values.

## 📁 Project Structure

```
├── data/
│   └── Dataset_Goodreads_Book_of_Carissa_Broadbent_Fix.xlsx
├── docs/
│   ├── IEEE_Conference_rizqifajar__rev_.pdf
│   └── Proposal_TA_1305210094_Rizqi_Fajar__Final.pdf
├── model/                  # Generated at runtime
│   ├── knn_model.pkl
│   ├── word_vectorizer.pkl
│   └── user_final_rating.pkl
├── main.py                 # Production pipeline
├── notebook.ipynb          # Exploration & EDA
├── requirements.txt
├── .gitignore
└── README.md
```

## 🚀 How to Run

### Prerequisites

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### Run the Pipeline

```bash
python main.py
```

This will:
1. Load and clean the Goodreads dataset
2. Train the KNN sentiment classifier
3. Predict sentiment for unrated reviews
4. Build the collaborative filtering model
5. Generate sentiment-enhanced recommendations
6. Save trained models to `model/`

### Explore in Notebook

```bash
jupyter notebook notebook.ipynb
```

The notebook contains detailed EDA, visualizations (word clouds, sentiment distribution, confusion matrices), and step-by-step explanations of the methodology.

## 📝 Approach Summary

1. **Data Cleaning**: Filtered for English reviews only (using `langdetect`), removed short reviews (<2 words), dropped duplicates and placeholder titles.

2. **Sentiment Labeling**: Mapped ratings to sentiment: 4–5★ → positive, 1–2★ → negative, 3★/No Rating → undecided.

3. **Text Preprocessing**: Applied a multi-step NLP pipeline — lowercasing, contraction expansion, URL/emoji/punctuation removal, tokenization, stopword removal, multi-POS lemmatization, and noun extraction.

4. **Sentiment Classification**: Trained a KNN classifier on CountVectorizer features with SMOTE oversampling, optimizing K through accuracy sweep. Used the model to predict sentiment for "No Rating" reviews.

5. **Collaborative Filtering**: Built a user–user similarity matrix using cosine distance on mean-centered ratings, then generated predicted ratings through matrix multiplication.

6. **Sentiment-Enhanced Ranking**: Combined predicted ratings with sentiment scores using a weighted formula: `Score = 1 × Predicted Rating + 2 × Sentiment Score`, producing the final recommendation list.

## 📄 License

This project is part of an academic thesis (Tugas Akhir). See the `docs/` directory for the related IEEE conference paper and thesis proposal.

## 📬 Contact

For further questions or inquiries, feel free to reach out:

**RIZQI FAJAR**

📧 **Email:**  
<a href="mailto:rizqyfajar777@gmail.com">
  <img src="https://img.shields.io/badge/Email-rizqyfajar777%40gmail.com-red?style=for-the-badge&logo=gmail&logoColor=white" />
</a>

🌐 **Social Profiles:**  
<a href="https://instagram.com/_rizqifajar_" target="_blank">
  <img src="https://img.shields.io/badge/Instagram-_rizqifajar_-E4405F?style=for-the-badge&logo=instagram&logoColor=white" />
</a>
&nbsp;
<a href="http://wa.me/6289644460579" target="_blank">
  <img src="https://img.shields.io/badge/WhatsApp-Chat-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" />
</a>
