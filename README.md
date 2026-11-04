# 🛍️ ReviewSense Analytics — YouTube Product Review & Sentiment Intelligence

> A specialized YouTube product review and commercial analytics platform.  
> Analyzes **any product review video** across tech, gadgets, gaming, beauty & skincare, food & drinks, fashion, automotive, home appliances, unboxings, and marketing ad campaigns — with automated validation that **strictly filters out pure academic lectures**.  
> Evaluates viewer comments (English and Roman Urdu) with sentiment intelligence, purchase intent & complaint signals, brand follower segmentation, and visualises results in an interactive web dashboard.

---

## 📦 Project Structure

```
Project/
├── gui_server.py              # Local dashboard web server with product review validation
├── yt_marketing_recommender.py# CLI tool — product/marketing channel batch analysis & discovery
├── yt_edu_recommender.py      # Alias CLI tool
├── web/
│   ├── index.html             # Interactive product review dashboard interface
│   ├── style.css              # Modern dark-glass styling & animations
│   └── app.js                 # Chart.js graphs, live filtering, and CSV export
├── .env                       # YouTube Data API v3 key (never committed)
├── .gitignore
├── yt_marketing_comments.csv  # Output: raw analyzed comment dataset (auto-generated)
└── yt_marketing_ranking.csv   # Output: channel ranking summary table (auto-generated)
```

---

## 🚫 Content Scope & Educational Lecture Filter

The analyzer is built to process **any product review, unboxing, comparison, or commercial/marketing video**. Pure academic lectures and school coursework are rejected before comment collection:

| Content Type | Status | Detection Mechanism |
|---|---|---|
| **Tech & Gadgets** | ✅ **Accepted** | Smartphones (iPhone, Samsung), laptops, GPUs, audio, wearables, unboxings, comparisons |
| **Gaming & Hardware** | ✅ **Accepted** | Console reviews (PS5, Xbox, Switch), PC gaming hardware, game reviews, accessories |
| **Beauty, Skincare & Makeup** | ✅ **Accepted** | Skincare routines, cosmetic reviews, ingredient breakdowns, hauls, beauty product tests |
| **Food, Auto, Fashion & Home** | ✅ **Accepted** | Taste tests, restaurant/snack reviews, car/EV reviews, clothing hauls, home appliances |
| **Commercials & Marketing Ads** | ✅ **Accepted** | Super Bowl ads, viral ad breakdowns, commercial reviews, promotional campaigns |
| **Pure Academic Educational Lectures** | ❌ **Rejected** | YouTube Category 27 (*Education*) with coursework keywords (*calculus, linear algebra, physics, cbse, fsc, past papers, syllabus, exam prep*) |
| **Unrelated Non-Product Videos** | ❌ **Rejected** | Videos lacking any product, review, unboxing, or commercial signals |

---

## ✨ Key Features

### 🌐 Web Dashboard (`gui_server.py` + `web/`)
- 🔒 **Automated Content Validator** — checks YouTube category and metadata; accepts any product review or commercial while rejecting pure academic coursework.
- 🔗 **Universal YouTube URL Parser** — supports `youtube.com/watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, or raw 11-character video IDs.
- 📊 **Product Review Score (0–100)** — composite performance index:
  - **50%** Like-weighted sentiment polarity
  - **30%** Purchase intent & product praise signals
  - **20%** Low friction & complaint rate (inverted)
- 💬 **Like-Weighted VADER Sentiment** — comments are multiplied by `(likes + 1)` so high-consensus viewer feedback is properly prioritized.
- 👥 **Audience Segmentation (Brand Followers vs. Casual Prospects)** — separates commenters using behavioral proxy signals:
  - **🌟 Brand Followers / Advocates**: commenters who posted multiple times or earned $\ge 5$ likes.
  - **👁️ Casual Prospects / Viewers**: first-time or casual commenters.
- 🇵🇰 **Roman Urdu & English Product Lexicon** — detects buy signals (*"kharid liya"*, *"paisa wasool"*, *"kya product hai"*, *"game changer"*, *"worth the money"*, *"10/10"*) vs complaints & friction (*"scam"*, *"overpriced"*, *"poor quality"*, *"paisa zaya"*, *"bekaar product"*, *"returned it"*).
- 📈 **Three Interactive Chart.js Visualizations**:
  - **Sentiment Polarity Donut Chart** — Positive vs. Neutral vs. Negative distribution.
  - **Purchase Intent vs. Complaints Bar Chart** — Direct comparison of consumer buy signals vs pushback.
  - **Top Product Phrases Horizontal Bar Chart** — Most frequent Urdu & English consumer reactions.
- 📑 **Tabbed Evidence Explorer** — browse top-liked **"Purchase Intent & Praise"** comments, top-liked **"Complaints & Friction"** pushback, or the full comment stream.
- 🔍 **Live Search & Filter Pills** — filter comments by keyword, sentiment (`positive`, `neutral`, `negative`), signals (`intent`, `friction`), or audience (`🌟 Brand Followers`, `👁️ Casual Prospects`).
- 💾 **One-Click CSV Export** — download full comment records including author, likes, sentiment score/label, intent/friction tags, and audience segment.
- ⚡ **Confidence Badges** — **High** (>200 comments), **Medium** (50–200 comments), or **Low** (<50 comments) based on sample depth.

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python**: 3.10 or newer (tested on Windows & Linux)
- **YouTube Data API v3 Key**: Free tier from Google Cloud Console (10,000 units/day)

### 2. Configure Environment Variables

In your `.env` file in the root project folder:

```env
YOUTUBE_API_KEY=AIzaSy_YOUR_COPIED_KEY_HERE
```

### 3. Start the Web Dashboard

```powershell
# 1. Activate your virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Run the local server
python gui_server.py
```

Open your browser to: **http://127.0.0.1:5000**

1. Paste any YouTube marketing video link, or click one of the preset sample chips:
   - **Apple "1984" Super Bowl Ad** (`https://www.youtube.com/watch?v=ErwS24cBZPc`)
   - **WestJet Viral Campaign** (`https://www.youtube.com/watch?v=zIEIvi2MuEk`)
   - **2,000 Ads Breakdown** (`https://www.youtube.com/watch?v=9XIgalr9aWY`)
2. If you try an educational video (e.g. *3Blue1Brown* math lecture or *FSc Physics*), the server will cleanly reject it and display an informative notice.
3. Choose your sample size (100 to 2,000+ comments) and click **Analyze Marketing Video**.

---

## 💻 Running the CLI Tool

You can run either `yt_marketing_recommender.py` or `yt_edu_recommender.py`:

```powershell
# Run built-in self-test (no API key needed)
python yt_marketing_recommender.py --self-test

# Search and rank top marketing campaign review channels
python yt_marketing_recommender.py `
  --search "viral marketing campaign ad breakdown" `
  --region US `
  --max-channels 3 `
  --videos-per-channel 3 `
  --comments-per-video 50
```

---

## 📐 Scoring Formula & Confidence

The **Marketing Review Score** maps to a standard $0$ to $100$ scale:

$$\text{Marketing Review Score} = 0.50 \times \text{Sentiment}_{\%}^{LW} + 0.30 \times \text{Intent}_{\%} + 0.20 \times (100 - \text{Friction}_{\%})$$

Where:
- $\text{Sentiment}_{\%}^{LW} = \frac{\text{LikeWeightedSentiment} + 1.0}{2.0} \times 100$
- $\text{Intent}_{\%} = \frac{\text{Count}(\text{Purchase Intent Comments})}{\text{Total Comments}} \times 100$
- $\text{Friction}_{\%} = \frac{\text{Count}(\text{Ad Friction Comments})}{\text{Total Comments}} \times 100$

### Confidence Ratings
- 🟢 **High Confidence**: $> 200$ comments analyzed.
- 🟡 **Medium Confidence**: $50 \text{ to } 200$ comments analyzed.
- 🔴 **Low Confidence**: $< 50$ comments analyzed.

---

## 🇵🇰 Marketing Signal Lexicon (English & Roman Urdu)

### 🛒 Purchase Intent & Praise
- `bought this`, `buying right now`, `worth the money`, `game changer`, `must buy`, `highly recommend`
- `great marketing`, `brilliant ad`, `genius marketing`, `shut up and take my money`, `sold me`
- `kharid liya`, `kharid raha hoon`, `paisa wasool`, `kya marketing hai`, `kya ad hai`, `zabardast ad`
- `order kar diya`, `mangwa liya`, `shandar commercial`, `kamal ki marketing`, `lazmi kharidain`

### ⚠️ Ad Friction & Pushback
- `scam`, `overpriced`, `waste of money`, `don't buy`, `clickbait`, `sponsored trash`, `fake`
- `misleading`, `cringe ad`, `bad marketing`, `too expensive`, `paid review`, `cringe commercial`
- `paisa zaya`, `bekaar`, `fazool`, `mat kharidna`, `dhoka`, `fraud hai`, `loot rahe hain`
- `bekar ad`, `fazool ad`, `cringe hai`, `jhoota ad`, `ghatiya marketing`, `bohat mehenga`

---

## 🔌 REST API Specification

### `POST /api/analyze`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=ErwS24cBZPc",
  "max_comments": 2000
}
```

**Rejection Response (for Educational / Non-Marketing Videos):**
```json
{
  "error": "❌ Rejection: 'Vectors | Chapter 1, Essence of linear algebra' is classified under YouTube's 'Education' category. This analyzer is strictly restricted to marketing-related video reviews, ad breakdowns, and commercial campaigns. Purely educational or academic lectures are not allowed."
}
```

**Success Response (Sample Structure):**
```json
{
  "video": {
    "video_id": "ErwS24cBZPc",
    "title": "4K Restoration: 1984 Super Bowl APPLE MACINTOSH Ad by Ridley Scott",
    "channel_title": "Mac History",
    "view_count": 2500000,
    "like_count": 85000,
    "comment_count": 2100
  },
  "analysis": {
    "marketing_score": 89.2,
    "confidence": "High",
    "lw_sentiment": 0.612,
    "sentiment_summary": { "positive_count": 820, "neutral_count": 140, "negative_count": 40 },
    "signals_summary": { "intent_count": 310, "intent_pct": 31.0, "friction_count": 20, "friction_pct": 2.0 },
    "top_phrases": [ { "phrase": "brilliant ad", "count": 84 } ],
    "follower_analysis": {
      "followers": { "marketing_score": 92.5, "confidence": "High" },
      "non_followers": { "marketing_score": 87.8, "confidence": "High" }
    }
  }
}
```
