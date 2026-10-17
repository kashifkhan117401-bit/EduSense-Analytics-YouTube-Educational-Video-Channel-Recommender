# 🎓 EduSense Analytics — YouTube Educational Video & Channel Recommender

> A student data-analytics project built for Pakistan's educational community.  
> Analyses YouTube viewer comments (English, Urdu script, Roman Urdu) with sentiment intelligence and visualises results in a beautiful web dashboard.

---

## 📦 Project Structure

```
Project/
├── yt_edu_recommender.py   # CLI tool — channel-level batch analysis
├── gui_server.py           # Local web-server (Python stdlib only)
├── web/
│   ├── index.html          # Dashboard UI
│   ├── style.css           # Dark-glass premium styling
│   └── app.js              # Chart.js graphs + API calls
├── .env                    # Your API key (never committed)
├── .gitignore
├── yt_edu_comments.csv     # Output: raw comment data (auto-generated)
└── yt_edu_ranking.csv      # Output: channel ranking table (auto-generated)
```

---

## ✨ Features

### GUI Dashboard (`gui_server.py` + `web/`)
- 🔗 **Paste any YouTube video URL** — resolves `youtube.com/watch?v=`, `youtu.be/`, `/shorts/`, raw 11-char IDs
- 📊 **Education Score (0–100)** — weighted formula: 50% like-weighted sentiment + 30% comprehension signals + 20% low confusion
- 💬 **Like-weighted VADER Sentiment** — each comment score multiplied by `(likes + 1)` to weight influential consensus
- 🇵🇰 **Roman Urdu & Urdu Phrase Detection** — "samajh aa gaya", "concept clear", "shukriya", "samajh nahi aya", etc.
- 📈 **Three interactive Chart.js graphs**:
  - Sentiment Polarity Donut (Positive / Neutral / Negative)
  - Comprehension vs Confusion Signal Bar Chart
  - Top Educational Phrases Horizontal Bar Chart
- 🗂️ **Tabbed Comment Explorer** — browse "Helped Me" evidence, "Confused" feedback, and all sampled comments
- 🔍 **Live comment search & filter** — filter by sentiment label or signal type
- 💾 **Export CSV** — download the full analyzed comment dataset in one click
- ⚡ **Confidence badges** — Low (<50 comments), Medium (50–200), High (>200)

### CLI Tool (`yt_edu_recommender.py`)
- Resolve channels via `@handle`, `UC...` ID, or full URL
- Optional topic discovery: `--search "FSc physics lectures" --region PK`
- Batch process multiple channels: latest N videos × M comments each
- VADER (default) or multilingual Hugging Face model (`--model multilingual`)
- Saves `yt_edu_comments.csv` and `yt_edu_ranking.csv`
- Quota-safe: saves partial results on `quotaExceeded` and exits cleanly

---

## 🚀 Quick Start

### 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or newer |
| YouTube Data API v3 key | Free (Google Cloud Console) |

### 2. Get a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services → Enable APIs**
3. Search for **"YouTube Data API v3"** → Enable
4. **Credentials → Create Credentials → API Key**
5. Copy the key

### 3. Set Up the Project

```powershell
# Navigate to the project folder
cd "C:\Users\Kashif Hafeez\Desktop\Project"

# Create and activate virtual environment
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install requests pandas vaderSentiment
```

> **Note for MSYS2 users:** If `python` is not on PATH, use the full path:
> `C:\msys64\ucrt64\bin\python.exe`

### 4. Configure Your API Key

Edit the `.env` file in the project root:

```env
YOUTUBE_API_KEY=AIzaSy_YOUR_KEY_HERE
```

> ⚠️ Never commit your `.env` file. It is already listed in `.gitignore`.

---

## 🌐 Running the Web GUI

```powershell
# Activate venv first (if not already active)
.\.venv\Scripts\Activate.ps1

# Start the dashboard server
python gui_server.py
```

Then open your browser at: **http://127.0.0.1:5000**

Paste any YouTube educational video URL and click **Analyze Video** to see:
- The education score, sentiment meter, and comprehension signals
- Three interactive graphs
- A browsable, filterable comment table

To stop the server: press `Ctrl+C` in the terminal.

---

## 💻 Running the CLI Tool

### Basic — Analyze specific channels

```powershell
python yt_edu_recommender.py `
  --channels "@SabaqPK @3blue1brown @khanacademy" `
  --videos-per-channel 5 `
  --comments-per-video 100
```

### With Topic Discovery

```powershell
python yt_edu_recommender.py `
  --search "FSc physics lectures" `
  --region PK `
  --max-channels 10 `
  --videos-per-channel 3 `
  --comments-per-video 100 `
  --out fsc_physics
```

### Use Multilingual Model (Urdu-aware)

```powershell
# Install extra dependencies first
pip install transformers torch sentencepiece

python yt_edu_recommender.py `
  --channels "@SabaqPK" `
  --model multilingual
```

### CLI Flags Reference

| Flag | Default | Description |
|---|---|---|
| `--channels` | — | Space-separated list of `@handles`, UC… IDs, or URLs |
| `--search` | — | Search query to discover channels |
| `--region` | `PK` | ISO 3166-1 alpha-2 region code (e.g. `PK`, `US`) |
| `--max-channels` | `5` | Max channels to discover from `--search` |
| `--videos-per-channel` | `5` | Number of latest videos to sample per channel |
| `--comments-per-video` | `100` | Max top-level comments to fetch per video |
| `--model` | `vader` | Sentiment model: `vader` or `multilingual` |
| `--out` | `yt_edu` | Output file prefix (generates `.csv` files) |
| `--self-test` | — | Run built-in unit tests without API calls |

### Output Files

| File | Contents |
|---|---|
| `{out}_ranking.csv` | One row per channel: education score, confidence, sentiment, helped%, confused% |
| `{out}_comments.csv` | One row per comment: text, likes, VADER score, sentiment label, phrase signals |

---

## 📐 Education Score Formula

```
Education Score (0–100) =
    0.50 × like_weighted_sentiment_pct   (maps [-1,+1] → [0,100])
  + 0.30 × helped_comment_pct           (% comments with comprehension signals)
  + 0.20 × (100 - confused_comment_pct) (inverted confusion ratio)
```

**Confidence Tiers:**

| Tier | Comments Analyzed |
|---|---|
| 🟢 High | > 200 |
| 🟡 Medium | 50 – 200 |
| 🔴 Low | < 50 |

> Low confidence results should be interpreted conservatively.

---

## 🇵🇰 Roman Urdu & Urdu Signal Phrases

### ✅ Comprehension / "Helped Me" Signals

| Roman Urdu | Meaning |
|---|---|
| `samajh aa gaya` / `samajh agaya` | "I understood" |
| `concept clear` / `clear ho gaya` | "Concept is clear now" |
| `shukriya` / `shukriya bhai` | "Thank you" |
| `maza aa gaya` | "Really enjoyed / got it" |
| `zabardast` | "Excellent / superb" |
| `bohat acha` / `bahut acha` | "Very good" |
| `bohat helpful` | "Very helpful" |
| `best teacher` / `best channel` | Praise signal |

### ❓ Confusion / Friction Signals

| Roman Urdu | Meaning |
|---|---|
| `samajh nahi aya` / `samajh nahi aaya` | "I didn't understand" |
| `palla nahi` | "I didn't get it" |
| `kuch samajh nahi` | "Didn't understand anything" |
| `samajh nahi aata` | "Can't understand" |
| `please slow down` | Pacing complaint |
| `too fast` / `very fast` | Speed complaint |

---

## 🔑 API Quota Notes

The YouTube Data API v3 uses a daily quota (10,000 units by default):

| Operation | Units Used |
|---|---|
| Channel resolve | ~1 unit |
| Video list (uploads) | ~1 unit per page |
| Comment fetch | ~1 unit per page (100 comments) |
| Video details | ~1 unit per request |

For 5 channels × 5 videos × 100 comments, expect ~30–50 units total — well within the free daily limit.

If quota is exceeded, the CLI saves all collected data so far before exiting.

---

## 🛠️ Development & Extension

### Adding More Phrases

Edit the `HELPED_PHRASES` and `CONFUSED_PHRASES` lists in both `gui_server.py` (for the web GUI) and `yt_edu_recommender.py` (for the CLI).

### Changing Score Weights

In `gui_server.py`:
```python
WEIGHT_SENTIMENT: float = 0.50
WEIGHT_HELPED:    float = 0.30
WEIGHT_CONFUSED:  float = 0.20
```

### Running Self-Tests (CLI)

```powershell
python yt_edu_recommender.py --self-test
```

This runs built-in unit tests on the scoring logic without making any API calls.

---

## ⚠️ Limitations & Disclaimers

- **Roman Urdu matching** uses simple case-insensitive substring search. Spelling varies; some variants may be missed.
- **VADER** was designed for English. Urdu/Roman Urdu sentiment may be inaccurate; use `--model multilingual` for better Urdu coverage (requires `transformers` + `torch`).
- The **Education Score** measures *viewer reception and feedback signals*, not factual accuracy or curriculum quality.
- YouTube comments are public data accessed through the official API. No scraping is performed.
- **Never hard-code your API key** in any source file.

---

## 📄 License

This project is for educational and student research use. No warranty is provided.
YouTube Data API usage is subject to [Google's Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service).

---

## 👨‍💻 Author

Built as a student data-analytics project — Pakistan 🇵🇰

Sentiment engine: [VADER](https://github.com/cjhutto/vaderSentiment) | Visualisation: [Chart.js](https://www.chartjs.org/) | Data: [YouTube Data API v3](https://developers.google.com/youtube/v3)
