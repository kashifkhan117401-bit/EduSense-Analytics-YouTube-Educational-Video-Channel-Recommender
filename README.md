# 🎓 EduSense Analytics — YouTube Educational Video & Channel Recommender

> A student data-analytics project built for Pakistan's educational community.  
> Analyses YouTube viewer comments (English, Urdu script, and Roman Urdu) with sentiment intelligence, follower proxy segmentation, and visualises results in an interactive web dashboard.

---

## 📦 Project Structure

```
Project/
├── yt_edu_recommender.py   # CLI tool — channel-level batch analysis & search
├── gui_server.py           # Local dashboard web server (REST API + static UI)
├── web/
│   ├── index.html          # Interactive dashboard interface
│   ├── style.css           # Modern dark-glass styling & animations
│   └── app.js              # Chart.js graphs, live filtering, and CSV export
├── .env                    # YouTube Data API v3 key (never committed)
├── .gitignore
├── yt_edu_comments.csv     # Output: raw analyzed comment dataset (auto-generated)
└── yt_edu_ranking.csv      # Output: channel ranking summary table (auto-generated)
```

---

## ✨ Key Features

### 🌐 Web Dashboard (`gui_server.py` + `web/`)
- 🔗 **Universal YouTube URL Parser** — supports `youtube.com/watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, or raw 11-character video IDs.
- 📊 **Education Score (0–100)** — composite index combining:
  - **50%** Like-weighted sentiment polarity
  - **30%** Comprehension & praise signals ("Helped Me")
  - **20%** Friction & confusion signals (inverted)
- 💬 **Like-Weighted VADER Sentiment** — comments are multiplied by `(likes + 1)` so high-consensus viewer feedback is properly prioritized.
- 👥 **Audience Segmentation (Follower vs. Non-Follower Proxy)** — categorizes commenters based on behavioral signals since the YouTube API does not disclose subscriber status per comment.
- 🇵🇰 **Roman Urdu & Urdu Learning Signals** — identifies regional praise (*"samajh aa gaya"*, *"concept clear"*, *"shukriya"*, *"bohat acha"*) and pacing/confusion friction (*"samajh nahi aya"*, *"too fast"*, *"palla nahi"*).
- 📈 **Three Interactive Chart.js Visualizations**:
  - **Sentiment Polarity Donut Chart** — Positive vs. Neutral vs. Negative distribution.
  - **Comprehension vs. Confusion Bar Chart** — Direct comparison of learning success vs. difficulty.
  - **Top Educational Phrases Horizontal Bar Chart** — Most frequent Urdu & English educational feedback keywords.
- 📑 **Tabbed Evidence Explorer** — browse top-liked **"Helped Me"** comments, top-liked **"Confused"** questions, or the complete comment stream.
- 🔍 **Live Search & 7 Filter Pills** — instantly filter comments by text, author, sentiment (`positive`, `neutral`, `negative`), signals (`helped`, `confused`), or audience (`🌟 Followers`, `👁️ Non-Followers`).
- 💾 **One-Click CSV Export** — download full comment records including author, likes, sentiment score/label, signal tags, and audience segment.
- ⚡ **Confidence Badges** — **High** (>200 comments), **Medium** (50–200 comments), or **Low** (<50 comments) based on sample depth.
- 🔄 **Pagination Engine** — automatically navigates YouTube API `pageToken` batches up to 2,000 comments.

### 💻 CLI Batch Tool (`yt_edu_recommender.py`)
- Resolve channels by `@handle`, `UC...` ID, or full URL.
- Topic discovery via YouTube Search: `--search "FSc physics lectures" --region PK`.
- Batch evaluates channels across multiple latest uploads (videos × comments).
- Supports both **VADER** and Hugging Face multilingual transformer models (`--model multilingual`).
- Transparent virtual environment auto-delegation (automatically runs inside `.venv` even if launched from system Python).
- Quota-safe: captures and flushes collected data to CSV upon encountering API quota limits.

---

## 👥 Audience Segmentation: Follower Proxy Detection

Because the YouTube Data API v3 does **not** expose subscriber status on individual comments, EduSense Analytics employs a behavioral proxy model:

| Proxy Signal | Condition | Classification |
|---|---|---|
| **Repeat Commenter** | Author channel ID appears > 1 time in the dataset | `🌟 Follower (Proxy)` |
| **High-Like Commenter** | Any comment by this author received $\ge 5$ likes | `🌟 Follower (Proxy)` |
| **Channel Owner** | Author channel ID matches the video channel ID | `🌟 Follower (Proxy)` |
| **Casual Viewer** | Author posted once with $< 5$ likes | `👁️ Non-Follower / Casual` |

Both segments are tagged on every comment, surfaced as filter pills in the dashboard, exported in CSV files, and computed into separate score profiles in the backend JSON API.

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python**: 3.10 or newer (tested on Windows & Linux)
- **YouTube Data API v3 Key**: Free tier from Google Cloud Console (10,000 units/day)

### 2. Obtain a Free YouTube API Key

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Open **APIs & Services → Library** → Search for **"YouTube Data API v3"** → Click **Enable**.
4. Go to **Credentials → Create Credentials → API Key**.
5. Copy your generated API key.

### 3. Project Installation

```powershell
# Navigate to project folder
cd "C:\Users\Kashif Hafeez\Desktop\Project"

# Create virtual environment (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install requests pandas vaderSentiment
```

> **Note for MSYS2 / UCRT64 users:** If `python` is not directly on PATH, specify the binary path:  
> `C:\msys64\ucrt64\bin\python.exe -m venv .venv`

### 4. Configure Environment Variables

Create or edit the `.env` file in the root project folder:

```env
YOUTUBE_API_KEY=AIzaSy_YOUR_COPIED_KEY_HERE
```

> ⚠️ **Security Notice:** Never commit your `.env` file. It is already ignored via `.gitignore`.

---

## 🌐 Running the Web Dashboard

```powershell
# 1. Activate your virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Start the local server
python gui_server.py
```

Open your browser to: **http://127.0.0.1:5000**

1. Paste any YouTube video link (or click one of the preset sample chips like *3Blue1Brown* or *FSc Physics*).
2. Choose your comment sample size (50, 100, or 200).
3. Click **Analyze Video** to generate live metrics, charts, and comment tables.
4. Press `Ctrl + C` in your terminal to shut down the server.

---

## 💻 Running the CLI Recommender

### 1. Analyze Specific Channels

```powershell
python yt_edu_recommender.py `
  --channels "@SabaqPK @3blue1brown @khanacademy" `
  --videos-per-channel 5 `
  --comments-per-video 100
```

### 2. Discover Channels by Topic & Region

```powershell
python yt_edu_recommender.py `
  --search "FSc physics lectures" `
  --region PK `
  --max-channels 5 `
  --videos-per-channel 3 `
  --comments-per-video 100 `
  --out fsc_physics
```

### 3. Multilingual Transformer Model (Urdu / Devanagari)

```powershell
# Install PyTorch and Hugging Face Transformers
pip install transformers torch sentencepiece

python yt_edu_recommender.py `
  --channels "@SabaqPK" `
  --model multilingual
```

### 4. Run Offline Self-Tests

```powershell
python yt_edu_recommender.py --self-test
```
*Validates phrase parsing, weighted scoring math, and edge-case handlers without consuming API quota.*

---

## 📋 CLI Flags Reference

| Flag | Default | Description |
|---|---|---|
| `--channels` | — | Space-separated list of `@handles`, `UC...` IDs, or channel URLs |
| `--search` | — | Query string to discover top channels automatically |
| `--region` | `PK` | Country code for discovery (e.g., `PK`, `US`, `IN`, `GB`) |
| `--max-channels` | `5` | Maximum channels to inspect from `--search` |
| `--videos-per-channel` | `5` | Number of recent videos sampled per channel |
| `--comments-per-video` | `100` | Target comments per video |
| `--model` | `vader` | Model engine: `vader` (fast English/lexicon) or `multilingual` (BERT) |
| `--out` | `yt_edu` | Prefix for output CSV files |
| `--self-test` | — | Executes built-in test suite offline |

---

## 📐 Scoring Formula & Confidence

The **Education Score** maps to a standard $0$ to $100$ scale:

$$\text{Education Score} = 0.50 \times \text{Sentiment}_{\%}^{LW} + 0.30 \times \text{Helped}_{\%} + 0.20 \times (100 - \text{Confused}_{\%})$$

Where:
- $\text{Sentiment}_{\%}^{LW} = \frac{\text{LikeWeightedSentiment} + 1.0}{2.0} \times 100$
- $\text{Helped}_{\%} = \frac{\text{Count}(\text{Helped Comments})}{\text{Total Comments}} \times 100$
- $\text{Confused}_{\%} = \frac{\text{Count}(\text{Confused Comments})}{\text{Total Comments}} \times 100$

### Confidence Ratings
- 🟢 **High Confidence**: $> 200$ comments analyzed.
- 🟡 **Medium Confidence**: $50 \text{ to } 200$ comments analyzed.
- 🔴 **Low Confidence**: $< 50$ comments analyzed *(findings should be treated as indicative only)*.

---

## 🇵🇰 Educational Signal Lexicon

### ✅ Comprehension & Praise ("Helped Me")
- `samajh aa gaya`, `samajh agaya`, `samajh aagaya` ("I understood")
- `concept clear`, `clear ho gaya`, `clear hogaya` ("Concept is crystal clear")
- `shukriya`, `shukriya bhai` ("Thank you")
- `maza aa gaya`, `zabardast` ("Enjoyed / Excellent presentation")
- `bohat acha`, `bahut acha`, `bohat helpful`, `bahut helpful` ("Very good / helpful")
- `best teacher`, `best channel`, `nicely explained`

### ❓ Friction & Pacing ("Confused")
- `samajh nahi aya`, `samajh nahi aaya`, `samajh nahi aata`, `samajh nahi` ("Didn't understand")
- `palla nahi`, `kuch samajh nahi` ("Couldn't grasp anything")
- `too fast`, `very fast`, `please slow down`, `slow down` ("Pacing too rapid")
- `confusing`, `i am confused`, `not clear`, `wrong`, `mistake`, `incorrect`

---

## 🔌 REST API Specification

`gui_server.py` exposes an HTTP JSON endpoint:

### `POST /api/analyze`

**Request Headers:** `Content-Type: application/json`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=fNk_zzaMoSs",
  "max_comments": 100
}
```

**Response Sample:**
```json
{
  "video": {
    "video_id": "fNk_zzaMoSs",
    "title": "Vectors | Chapter 1, Essence of linear algebra",
    "channel_title": "3Blue1Brown",
    "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
    "published_at": "2016-08-05T17:00:00Z",
    "view_count": 4820000,
    "like_count": 142000,
    "comment_count": 3100,
    "thumbnail_url": "https://i.ytimg.com/vi/..."
  },
  "analysis": {
    "total_comments": 100,
    "edu_score": 88.4,
    "confidence": "Medium",
    "lw_sentiment": 0.582,
    "sentiment_summary": { "positive_count": 82, "neutral_count": 14, "negative_count": 4 },
    "signals_summary": { "helped_count": 38, "confused_count": 2 },
    "top_phrases": [ { "phrase": "concept clear", "count": 14 } ],
    "follower_analysis": {
      "follower_count": 26,
      "non_follower_count": 74,
      "followers": { "edu_score": 91.2, "confidence": "Low" },
      "non_followers": { "edu_score": 87.4, "confidence": "Medium" }
    }
  }
}
```

---

## 🔑 YouTube API Quota Management

The YouTube Data API provides a default allocation of **10,000 units/day** for free:

| API Call | Unit Cost | Usage Context |
|---|---|---|
| `videos.list` | ~1 unit | Fetches video title, channel, views, likes |
| `commentThreads.list` | ~1 unit per page | 100 comments fetched per call |
| `channels.list` | ~1 unit | Resolves handle or channel ID |
| `search.list` | 100 units | Invoked only when `--search` query is used |

*Standard video analysis on the web dashboard (100–200 comments) consumes only **2 to 3 units**, allowing thousands of analyses per day on the free quota.*

---

## 🛠️ Configuration & Extension

### Adjusting Scoring Weights
Modify the constants in `gui_server.py` and `yt_edu_recommender.py`:
```python
WEIGHT_SENTIMENT: float = 0.50   # 50%
WEIGHT_HELPED:    float = 0.30   # 30%
WEIGHT_CONFUSED:  float = 0.20   # 20%
```

### Expanding Roman Urdu Keywords
Add phrases to `HELPED_PHRASES` and `CONFUSED_PHRASES` in `gui_server.py` and `yt_edu_recommender.py`. Phrases are matched as case-insensitive substrings.

---

## ⚠️ Limitations & Disclaimers

1. **Viewer Reception vs. Curriculum Validity**: The Education Score quantifies audience perception and feedback clarity; it does not audit academic syllabus compliance or technical accuracy.
2. **Follower Proxy Approximation**: Because subscriber identity is private on YouTube, follower segmentation relies on repeat commenting and like thresholds.
3. **Roman Urdu Orthography**: Roman Urdu lacks standardized spelling; while common variations are included, unconventional spellings may be uncaptured.
4. **Data Privacy**: All data is retrieved through Google's official public API endpoints. No private user data or credentials are collected or shared.

---

## 📄 License & Credits

- **License**: Educational & Academic Research Use.
- **Sentiment Engine**: [VADER Sentiment](https://github.com/cjhutto/vaderSentiment)
- **Charts & Visualizations**: [Chart.js v4](https://www.chartjs.org/)
- **Data Source**: [Google YouTube Data API v3](https://developers.google.com/youtube/v3)
