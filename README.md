#AI Content Creator Analyser

## Abstract

Creator Shield is an AI Content Creator Analyser that analyzes social media comments to detect toxic, abusive, harmful, and spam content. It supports platforms such as YouTube and Reddit while providing creator safety scores, analytics dashboards, flagged content management, and moderation insights to help maintain healthy online communities.

---

## Keywords

**Artificial Intelligence (AI), Content Moderation, Toxic Comment Detection, Social Media Analytics, Natural Language Processing (NLP), Streamlit, Gemini AI, Dashboard**

---

## 1. Introduction

Creator Shield helps creators and moderators identify harmful comments using AI-based moderation techniques. It improves community safety by analyzing user-generated content and providing actionable moderation insights.

---

## 2. Problem Statement

Managing large volumes of online comments manually is difficult, allowing toxic, abusive, and spam content to negatively impact online communities.

---

## 3. Objectives

* Detect harmful and toxic comments.
* Classify abusive and spam content.
* Generate creator safety scores.
* Provide moderation analytics.
* Support efficient content management.

---

## 4. Methodology

1. Fetch comments from supported platforms.
2. Analyze comments using AI.
3. Classify content into moderation categories.
4. Calculate creator safety score.
5. Display analytics and flagged content.

---

## 5. Literature Review

Traditional moderation relies on manual review or keyword filtering. AI-powered moderation improves detection accuracy through intelligent text analysis and automated content classification.

---

## 6. System Architecture

```text
Social Media Comments
         │
         ▼
 Comment Fetcher
         │
         ▼
AI Moderation Engine
         │
         ▼
Classification & Safety Score
         │
         ▼
Dashboard & Reports
```

---

## 7. Features

* AI-powered comment moderation
* Toxicity and spam detection
* Creator safety score
* Interactive analytics dashboard
* Flagged content management
* CSV export for reports and blocklists

---

## 8. Implementation

The project is developed using Python and Streamlit. Comments are collected from supported platforms, analyzed using AI models and moderation rules, stored in SQLite, and visualized through an interactive dashboard.

---

## 9. Tech Stack

* Python
* Streamlit
* SQLite
* Pandas
* Altair
* Google Gemini API
* YouTube Data API

---

## 10. Project Modules

* Comment Fetcher
* AI Moderation Engine
* Dashboard & Analytics
* Flagged Content Manager
* Database Management
* Report Export

---

## 11. Project Structure

```text
Creator_Shield/
│── app.py
│── database.py
│── fetcher.py
│── moderator.py
│── requirements.txt
│── assets/
└── README.md
```

---

## 12. Installation

```bash
git clone <repository-link>
cd Creator_Shield
pip install -r requirements.txt
streamlit run app.py
```

---

## 13. Results

The system successfully detects harmful comments, classifies content into moderation categories, generates creator safety scores, and provides real-time moderation analytics through an interactive dashboard.

---

## 14. Conclusion

Creator Shield provides an efficient AI-driven solution for moderating online communities by identifying harmful content and helping creators maintain a safer digital environment.

---

## 15. Future Scope

* Support additional social media platforms
* Deep Learning-based moderation models
* Real-time live comment monitoring
* Multi-language moderation
* Cloud deployment
* Automated moderation actions

---

## 16. References

1. Google Gemini API Documentation
2. YouTube Data API Documentation
3. Streamlit Documentation
4. Python Documentation
5. NLP and Content Moderation Research Papers
