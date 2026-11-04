"""
yt_edu_recommender.py (yt_marketing_recommender.py)
===================================================
Recommends the best marketing YouTube channels and video reviews by analysing
viewer comments with sentiment analysis, purchase intent, and ad friction signals.
Strictly configured to evaluate marketing reviews, brand campaigns, and commercial breakdowns.

QUOTA NOTES
-----------
- Each search.list call costs 100 units.
- Each channels.list / playlistItems.list / commentThreads.list costs 1 unit each page.
- Default daily quota is 10 000 units.
- With 3 channels x 5 videos x 2 comment pages ~36 units (no search).
- With --search (10 results) ~100 + ~120 units.

DEPENDENCIES
------------
    pip install requests pandas vaderSentiment

For --model multilingual also install:
    pip install transformers torch

EXAMPLE COMMANDS
----------------
# Rank marketing channels by handle (English VADER)
python yt_edu_recommender.py --channels @GaryVee @marketingagainstthegrain

# Marketing campaign search, multilingual model
python yt_edu_recommender.py --search "viral marketing ad breakdown" --region US \
    --max-channels 5 --videos-per-channel 10 --model vader

# Self-test (no API key needed)
python yt_edu_recommender.py --self-test
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Any

# Transparently delegate to local .venv if launched via a system Python lacking dependencies
try:
    import pandas as pd
    import requests
except ImportError:
    _venv_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    if os.path.isfile(_venv_py) and sys.executable.lower() != os.path.abspath(_venv_py).lower():
        import subprocess
        _res = subprocess.run([_venv_py, *sys.argv])
        sys.exit(_res.returncode)
    raise


# ---------------------------------------------------------------------------
# EDITABLE CONSTANTS
# ---------------------------------------------------------------------------

# --- Academic Educational Terms (Used to filter out non-marketing videos) ---
ACADEMIC_EDU_TERMS: list[str] = [
    "physics", "chemistry", "mathematics", "calculus", "algebra", "geometry",
    "fsc", "cbse", "neet", "jee", "ncert", "syllabus", "textbook",
    "matric", "intermediate", "board exam", "past papers", "past paper",
    "lecture 1", "lecture 2", "chapter 1", "chapter 2", "exercise 1",
    "class 9", "class 10", "class 11", "class 12", "linear algebra"
]

# --- Phrase lists for Product & Marketing Video Reviews ---
PURCHASE_INTENT_PHRASES: list[str] = [
    # English: Purchase intent, brand love, product praise
    "bought this", "bought it", "buying this", "buying right now", "just bought",
    "take my money", "just ordered", "worth the money", "worth buying", "great product",
    "must buy", "game changer", "highly recommend", "sold me", "great marketing",
    "great campaign", "brilliant ad", "genius marketing", "best ad", "clever ad",
    "loved the ad", "great commercial", "brilliant commercial", "marketing genius",
    "creative marketing", "brand loyalty", "need this", "ordering now", "want this",
    "add to cart", "will purchase", "shut up and take my money", "effective campaign",
    "10/10 marketing", "best investment", "good marketing", "amazing campaign",
    "best commercial", "amazing ad", "superb ad", "great ad", "loved this ad",
    "best campaign", "clever marketing", "definitely buying", "love this product",
    "best purchase", "10/10 product", "best ever", "five stars", "5 stars",
    # Roman Urdu & Urdu: Khareedari, paisa wasool, zabardast ad/product
    "kharid liya", "kharid raha hoon", "kharidna hai", "paisa wasool",
    "kya marketing hai", "kya ad hai", "zabardast ad", "bohat zabardast product",
    "bohat acha ad", "kya campaign hai", "best ad hai", "order kar diya",
    "mangwa liya", "shandar commercial", "kamal ki marketing", "lazmi kharidain",
    "bohat acha product", "paisa wasool product", "dil jeet liya", "shandar product",
    "faydemand", "zarur lunga", "zarur kharidunga", "kya baat hai ad ki",
    "zabardast marketing", "lajawab ad", "lazmi lena hai", "kamal ka ad",
    "kya product hai", "shandar quality", "behtareen product",
]

MARKETING_FRICTION_PHRASES: list[str] = [
    # English: Ad friction, skepticism, product complaints, scam alerts, overpriced
    "scam", "overpriced", "waste of money", "don't buy", "do not buy", "clickbait",
    "sponsored trash", "fake", "terrible ad", "misleading", "cringe ad", "not worth it",
    "bad marketing", "too expensive", "hyped up", "paid review", "sponsor", "boycott",
    "fraud", "false advertising", "dishonest", "cringe commercial", "worst ad",
    "cheap marketing", "boring ad", "waste of time", "terrible marketing", "annoying ad",
    "unskippable trash", "overrated", "rip off", "ripoff", "dont buy", "dont waste",
    "skip this", "poor quality", "garbage", "manipulative", "dislike this ad",
    "hate this ad", "boring commercial", "bad ad", "deceptive", "shady marketing",
    "worst product", "broken product", "bad quality", "cheap quality", "returned it",
    # Roman Urdu & Urdu: Dhoka, bekaar ad/product, paisa zaya, fazool
    "paisa zaya", "bekaar", "fazool", "mat kharidna", "dhoka", "fraud hai",
    "loot rahe hain", "koi faida nahi", "bekar ad", "fazool ad", "cringe hai",
    "jhoota ad", "ghatiya marketing", "bohat mehenga", "mehenga hai",
    "kharab product", "mat lena", "bura ad", "kuch faida nahi", "bakwas ad",
    "bakwas product", "time waste", "kisi kaam ka nahi", "bilkul bekar",
    "bekaar product", "fazool product", "ghatiya quality", "wapas kar diya",
]

# Backward compatibility aliases
HELPED_PHRASES = PURCHASE_INTENT_PHRASES
CONFUSED_PHRASES = MARKETING_FRICTION_PHRASES

# --- Scoring weights (must sum to 1.0) ---
WEIGHT_SENTIMENT: float = 0.50   # like-weighted avg sentiment (0-100)
WEIGHT_INTENT: float    = 0.30   # share of purchase intent / advocacy comments (0-100)
WEIGHT_FRICTION: float  = 0.20   # LOW friction / pushback share is GOOD (inverted)

WEIGHT_HELPED = WEIGHT_INTENT
WEIGHT_CONFUSED = WEIGHT_FRICTION

# --- Confidence thresholds (total comments per channel) ---
CONFIDENCE_LOW_MAX: int = 49
CONFIDENCE_MED_MAX: int = 200

# --- API ---
YT_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS_PER_PAGE = 100      # YouTube's max per page for commentThreads
REQUEST_RETRY_SLEEP = 2         # seconds between retries on transient errors
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# HELPERS - API
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load key-value pairs from a local .env file if present."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass


def _get_api_key() -> str:
    """Read the YouTube API key from the environment or .env; exit clearly if absent."""
    _load_dotenv()
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        sys.exit(
            "[ERROR] Environment variable YOUTUBE_API_KEY is not set.\n"
            "        Add it to a .env file or set it in your shell:\n"
            "          .env file: YOUTUBE_API_KEY=AIza...\n"
            "          Windows  : set YOUTUBE_API_KEY=AIza...\n"
            "          Linux/Mac: export YOUTUBE_API_KEY=AIza..."
        )
    return key



def _yt_get(endpoint: str, params: dict[str, Any], api_key: str) -> dict | None:
    """
    GET a YouTube Data API endpoint with retry logic.

    Returns the parsed JSON dict, or None on quota exhaustion / unrecoverable
    error (caller should save collected data and exit).
    """
    params["key"] = api_key
    url = f"{YT_API_BASE}/{endpoint}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                print(f"[WARN] Network error after {MAX_RETRIES} attempts: {exc}")
                return None
            time.sleep(REQUEST_RETRY_SLEEP)
            continue

        if resp.status_code == 200:
            return resp.json()

        try:
            err = resp.json()["error"]
        except Exception:
            err = {"message": resp.text, "errors": []}

        reason = err.get("errors", [{}])[0].get("reason", "")
        if reason == "quotaExceeded":
            print("[WARN] YouTube API quota exceeded. Saving collected data and stopping.")
            return None
        if resp.status_code in (403, 404):
            print(f"[WARN] API error {resp.status_code}: {err.get('message', '')} (reason={reason})")
            return None
        if attempt < MAX_RETRIES:
            time.sleep(REQUEST_RETRY_SLEEP)
        else:
            print(f"[WARN] API error {resp.status_code}: {err.get('message', '')} -- skipping.")
            return None
    return None


# ---------------------------------------------------------------------------
# HELPERS - Channel resolution
# ---------------------------------------------------------------------------

_UC_RE = re.compile(r"^UC[\w-]{22}$")


def _resolve_channel(raw: str, api_key: str) -> tuple[str, str] | None:
    """
    Accept a @handle, a UC... channel ID, or a YouTube URL.
    Return (channel_id, channel_title) or None if not found.
    """
    # Strip URL down to handle or ID
    if "youtube.com" in raw:
        m = re.search(r"/@([\w.-]+)", raw)
        if m:
            raw = f"@{m.group(1)}"
        else:
            m = re.search(r"/channel/(UC[\w-]{22})", raw)
            if m:
                raw = m.group(1)

    raw = raw.strip()

    # Already a channel ID
    if _UC_RE.match(raw):
        data = _yt_get("channels", {"part": "snippet", "id": raw, "maxResults": 1}, api_key)
        if data and data.get("items"):
            item = data["items"][0]
            return item["id"], item["snippet"]["title"]
        print(f"[WARN] Channel ID not found: {raw}")
        return None

    # @handle
    handle = raw.lstrip("@")
    data = _yt_get("channels", {"part": "snippet", "forHandle": handle, "maxResults": 1}, api_key)
    if data and data.get("items"):
        item = data["items"][0]
        return item["id"], item["snippet"]["title"]
    print(f"[WARN] Channel handle not found: @{handle}")
    return None


def _search_channels(query: str, region: str, max_channels: int, api_key: str) -> list[tuple[str, str]]:
    """Search for channels matching *query*; return list of (channel_id, title)."""
    params: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "channel",
        "regionCode": region,
        "maxResults": min(max_channels, 50),
        "relevanceLanguage": "en",
    }
    data = _yt_get("search", params, api_key)
    if not data:
        return []
    results: list[tuple[str, str]] = []
    for item in data.get("items", []):
        cid = item["snippet"]["channelId"]
        title = item["snippet"]["channelTitle"]
        results.append((cid, title))
    return results[:max_channels]


# ---------------------------------------------------------------------------
# HELPERS - Video & comment collection
# ---------------------------------------------------------------------------

def _get_uploads_playlist(channel_id: str, api_key: str) -> str | None:
    """Return the uploads playlist ID for a channel, or None on failure."""
    data = _yt_get(
        "channels",
        {"part": "contentDetails", "id": channel_id, "maxResults": 1},
        api_key,
    )
    if not data or not data.get("items"):
        return None
    return data["items"][0]["contentDetails"]["relatedPlaylists"].get("uploads")


def _get_latest_videos(playlist_id: str, n: int, api_key: str) -> list[dict]:
    """Fetch the *n* most-recent video IDs and titles from an uploads playlist."""
    videos: list[dict] = []
    page_token: str | None = None
    while len(videos) < n:
        params: dict[str, Any] = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(n - len(videos), 50),
        }
        if page_token:
            params["pageToken"] = page_token
        data = _yt_get("playlistItems", params, api_key)
        if not data:
            break
        for item in data.get("items", []):
            sn = item["snippet"]
            videos.append({
                "video_id": sn["resourceId"]["videoId"],
                "video_title": sn.get("title", ""),
            })
            if len(videos) >= n:
                break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return videos


def _fetch_comments(
    video_id: str,
    video_title: str,
    channel_title: str,
    max_comments: int,
    api_key: str,
) -> list[dict]:
    """
    Fetch top-level comments for a video with pagination.

    Returns dicts with keys: text, likes, published_at, video_title, channel_name.
    Returns an empty list (not a crash) if comments are disabled.
    """
    comments: list[dict] = []
    page_token: str | None = None
    while len(comments) < max_comments:
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": min(max_comments - len(comments), MAX_RESULTS_PER_PAGE),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        data = _yt_get("commentThreads", params, api_key)
        if data is None:
            break
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            sn = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": sn.get("textDisplay", ""),
                "likes": int(sn.get("likeCount", 0)),
                "published_at": sn.get("publishedAt", ""),
                "video_title": video_title,
                "channel_name": channel_title,
            })
            if len(comments) >= max_comments:
                break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return comments


def collect_channel_comments(
    channel_id: str,
    channel_title: str,
    videos_per_channel: int,
    comments_per_video: int,
    api_key: str,
) -> list[dict]:
    """Resolve uploads -> videos -> comments for one channel."""
    playlist_id = _get_uploads_playlist(channel_id, api_key)
    if not playlist_id:
        print(f"[WARN] Could not get uploads playlist for '{channel_title}'. Skipping.")
        return []

    videos = _get_latest_videos(playlist_id, videos_per_channel, api_key)
    if not videos:
        print(f"[WARN] No videos found for '{channel_title}'.")
        return []

    all_comments: list[dict] = []
    for vid in videos:
        try:
            coms = _fetch_comments(
                vid["video_id"],
                vid["video_title"],
                channel_title,
                comments_per_video,
                api_key,
            )
        except Exception as exc:
            print(f"  [WARN] Could not fetch comments for '{vid['video_title']}': {exc}")
            coms = []
        all_comments.extend(coms)

    if not all_comments:
        print(f"  [WARN] No comments collected for '{channel_title}' (comments may be disabled).")
    return all_comments


# ---------------------------------------------------------------------------
# SENTIMENT
# ---------------------------------------------------------------------------

def _vader_score(text: str, analyser: Any) -> float:
    """Return VADER compound score in [-1, +1]."""
    return float(analyser.polarity_scores(text)["compound"])


def _label_from_score(score: float) -> str:
    """Map a [-1, +1] score to a human-readable label."""
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


def apply_vader(df: pd.DataFrame) -> pd.DataFrame:
    """Add *sentiment_score* and *sentiment_label* columns using VADER."""
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
    analyser = SentimentIntensityAnalyzer()
    df["sentiment_score"] = df["text"].apply(lambda t: _vader_score(str(t), analyser))
    df["sentiment_label"] = df["sentiment_score"].apply(_label_from_score)
    return df


def apply_multilingual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add sentiment columns using cardiffnlp/twitter-xlm-roberta-base-sentiment.
    Supports English, Urdu script, and Roman Urdu (results are approximate
    for informal Roman Urdu).
    """
    try:
        from transformers import pipeline  # type: ignore
    except ImportError:
        sys.exit(
            "[ERROR] --model multilingual requires 'transformers' and 'torch'.\n"
            "        Run: pip install transformers torch"
        )

    print("[INFO] Loading multilingual model (first run downloads ~1 GB)...")
    pipe = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
        truncation=True,
        max_length=128,
        device=-1,   # CPU; change to 0 for GPU
    )
    label_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

    texts = df["text"].fillna("").astype(str).tolist()
    scores: list[float] = []
    labels: list[str] = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        results = pipe(batch)
        for r in results:
            lbl = r["label"].lower()
            scores.append(label_map.get(lbl, 0.0))
            labels.append(lbl)

    df["sentiment_score"] = scores
    df["sentiment_label"] = labels
    return df


# ---------------------------------------------------------------------------
# MARKETING SIGNALS
# ---------------------------------------------------------------------------

def _contains_phrases(text: str, phrases: list[str]) -> bool:
    """Return True if *text* contains any phrase (case-insensitive substring)."""
    lower = text.lower()
    return any(ph in lower for ph in phrases)


def add_marketing_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean columns is_intent and is_friction based on marketing phrase lists."""
    df["is_intent"] = df["text"].apply(
        lambda t: _contains_phrases(str(t), PURCHASE_INTENT_PHRASES)
    )
    df["is_friction"] = df["text"].apply(
        lambda t: _contains_phrases(str(t), MARKETING_FRICTION_PHRASES)
    )
    # Aliases
    df["is_helped"] = df["is_intent"]
    df["is_confused"] = df["is_friction"]
    return df

# Alias
add_education_signals = add_marketing_signals


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def _confidence_label(n: int) -> str:
    """Map comment count to a confidence tier."""
    if n <= CONFIDENCE_LOW_MAX:
        return "Low"
    if n <= CONFIDENCE_MED_MAX:
        return "Medium"
    return "High"


def compute_channel_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-channel metrics and compute the Marketing Review Score (0-100).

    Formula:
      marketing_score = 0.50 * sentiment_0_100
                      + 0.30 * intent_pct
                      + 0.20 * (100 - friction_pct)

    where sentiment_0_100 = (like_weighted_mean_sentiment + 1) / 2 * 100
    """
    rows = []
    for channel, grp in df.groupby("channel_name"):
        n = len(grp)
        weight = grp["likes"].astype(float) + 1.0          # +1 so 0-like comments still count

        lw_sentiment = float((grp["sentiment_score"] * weight).sum() / weight.sum())
        sentiment_0_100 = (lw_sentiment + 1.0) / 2.0 * 100.0

        intent_pct    = float(grp["is_intent"].mean()) * 100.0
        friction_pct  = float(grp["is_friction"].mean()) * 100.0
        positive_pct  = float((grp["sentiment_label"] == "positive").mean()) * 100.0

        mktg_score = (
            WEIGHT_SENTIMENT * sentiment_0_100
            + WEIGHT_INTENT  * intent_pct
            + WEIGHT_FRICTION * (100.0 - friction_pct)
        )
        mktg_score = max(0.0, min(100.0, mktg_score))   # clamp to [0, 100]

        rows.append({
            "channel":         channel,
            "marketing_score": round(mktg_score, 2),
            "edu_score":       round(mktg_score, 2),  # alias
            "confidence":      _confidence_label(n),
            "comment_count":   n,
            "positive_pct":    round(positive_pct, 1),
            "intent_pct":      round(intent_pct, 1),
            "friction_pct":    round(friction_pct, 1),
            # Aliases
            "helped_pct":      round(intent_pct, 1),
            "confused_pct":    round(friction_pct, 1),
            "lw_sentiment":    round(lw_sentiment, 4),
        })

    ranking = (
        pd.DataFrame(rows)
        .sort_values("marketing_score", ascending=False)
        .reset_index(drop=True)
    )
    ranking.index += 1   # 1-based rank
    return ranking


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

def _top_comments(df: pd.DataFrame, channel: str, flag_col: str, n: int = 2) -> list[str]:
    """Return the *n* most-liked flagged comments for a channel as display strings."""
    mask = (df["channel_name"] == channel) & df[flag_col]
    sub = df[mask].sort_values("likes", ascending=False).head(n)
    out = []
    for _, row in sub.iterrows():
        snippet = str(row["text"])[:200].replace("\n", " ")
        out.append(f'  Like {int(row["likes"]):>5}  "{snippet}"')
    return out if out else ["  (none found)"]


def print_results(ranking: pd.DataFrame, df: pd.DataFrame) -> None:
    """Pretty-print ranked table, top pick, and evidence comments."""
    print("\n" + "=" * 80)
    print("  YOUTUBE MARKETING CHANNEL & CAMPAIGN REVIEW RANKING")
    print("=" * 80)

    header = (
        f"{'#':<4} {'Channel':<30} {'Score':>6} {'Conf':>6} "
        f"{'Comments':>9} {'Pos%':>6} {'Intent%':>8} {'Friction%':>10}"
    )
    print(header)
    print("-" * 80)

    for rank, row in ranking.iterrows():
        print(
            f"{rank:<4} {str(row['channel']):<30} {row['marketing_score']:>6.1f} "
            f"{row['confidence']:>6} {row['comment_count']:>9} "
            f"{row['positive_pct']:>6.1f} {row['intent_pct']:>8.1f} "
            f"{row['friction_pct']:>10.1f}"
        )

    print("=" * 80)

    top = ranking.iloc[0]
    print(f"\n  TOP PICK: {top['channel']}  (score {top['marketing_score']:.1f} | {top['confidence']} confidence)")

    # Evidence per channel
    for rank, row in ranking.iterrows():
        ch = row["channel"]
        print(f"\n-- {ch} --")
        print("  Most-liked 'Purchase Intent / Praise' comments:")
        for line in _top_comments(df, ch, "is_intent"):
            print(line)
        print("  Most-liked 'Ad Friction / Skepticism' comments:")
        for line in _top_comments(df, ch, "is_friction"):
            print(line)

    print("\n" + "-" * 80)
    print(
        "NOTE: The Marketing Review Score measures consumer sentiment, purchase intent,\n"
        "and ad friction signals from viewer feedback. It is strictly tailored for\n"
        "marketing campaigns, ad reviews, and commercial breakdowns (not education)."
    )
    print("-" * 80 + "\n")


def save_outputs(ranking: pd.DataFrame, df: pd.DataFrame, prefix: str) -> None:
    """Save _ranking.csv and _comments.csv."""
    rank_path = f"{prefix}_ranking.csv"
    comments_path = f"{prefix}_comments.csv"
    ranking.to_csv(rank_path, index_label="rank")
    df.to_csv(comments_path, index=False)
    print(f"[INFO] Ranking saved  -> {rank_path}")
    print(f"[INFO] Comments saved -> {comments_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recommend marketing YouTube channels & video reviews via comment sentiment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--channels", nargs="+", metavar="CHANNEL",
        help="One or more @handles, UC... IDs, or YouTube URLs.",
    )
    p.add_argument("--search", metavar="QUERY",
                   help="Topic query to discover marketing channels / ad reviews.")
    p.add_argument("--region", default="US", metavar="CC",
                   help="ISO country code for --search (default: US).")
    p.add_argument("--max-channels", type=int, default=5, metavar="N",
                   help="Max channels returned from --search (default: 5).")
    p.add_argument("--videos-per-channel", type=int, default=5, metavar="N",
                   help="Latest videos to sample per channel (default: 5).")
    p.add_argument("--comments-per-video", type=int, default=100, metavar="N",
                   help="Max comments to fetch per video (default: 100).")
    p.add_argument("--model", choices=["vader", "multilingual"], default="vader",
                   help="Sentiment model (default: vader).")
    p.add_argument("--out", default="yt_marketing", metavar="PREFIX",
                   help="File prefix for output CSVs (default: yt_marketing).")
    return p


def main() -> None:
    """Entry point: parse args, collect, analyse, score, and report."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.channels and not args.search:
        print("[INFO] No --channels or --search provided. Running default topic discovery:")
        print("       Topic: 'viral marketing campaign ad breakdown' | Region: US\n")
        args.search = "viral marketing campaign ad breakdown"
        args.max_channels = 3
        args.videos_per_channel = 3
        args.comments_per_video = 30


    api_key = _get_api_key()

    # --- Resolve channels ---
    channel_list: list[tuple[str, str]] = []

    if args.channels:
        for raw in args.channels:
            result = _resolve_channel(raw, api_key)
            if result:
                channel_list.append(result)

    if args.search:
        found = _search_channels(args.search, args.region, args.max_channels, api_key)
        existing_ids = {cid for cid, _ in channel_list}
        for cid, title in found:
            if cid not in existing_ids:
                channel_list.append((cid, title))
                existing_ids.add(cid)

    if not channel_list:
        sys.exit("[ERROR] No channels could be resolved. Check handles/IDs and API key.")

    print(f"\n[INFO] Channels to analyse: {[t for _, t in channel_list]}")

    # --- Collect comments ---
    all_comments: list[dict] = []
    for cid, title in channel_list:
        print(f"\n[INFO] Collecting comments for '{title}' ...")
        coms = collect_channel_comments(
            cid, title,
            args.videos_per_channel,
            args.comments_per_video,
            api_key,
        )
        print(f"  -> {len(coms)} comments collected.")
        all_comments.extend(coms)

    if not all_comments:
        sys.exit("[ERROR] No comments were collected. Check channel handles and API quota.")

    df = pd.DataFrame(all_comments)

    # --- Sentiment ---
    print(f"\n[INFO] Running sentiment analysis (model={args.model}) ...")
    if args.model == "multilingual":
        df = apply_multilingual(df)
    else:
        df = apply_vader(df)

    # --- Education signals ---
    df = add_education_signals(df)

    # --- Score & report ---
    ranking = compute_channel_scores(df)
    print_results(ranking, df)
    save_outputs(ranking, df, args.out)


# ---------------------------------------------------------------------------
# SELF-TEST  (python yt_edu_recommender.py --self-test)
# No API key required.
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """
    Smoke-test scoring and phrase detection on synthetic comments.
    Demonstrates Roman Urdu phrase matching and like-weighted scoring for marketing reviews.
    """
    import textwrap
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore

    analyser = SentimentIntensityAnalyzer()

    sample: list[tuple[str, int, str]] = [
        # text                                                          likes  channel
        ("Bought this immediately! Best ad ever, great marketing.",      150,  "BrandA_Campaign"),
        ("Shandar commercial, paisa wasool product order kar diya.",     110,  "BrandA_Campaign"),
        ("Scam and overpriced, don't buy this waste of money!",           15,  "BrandA_Campaign"),
        ("Brilliant ad, creative marketing at its best.",                 300,  "BrandA_Campaign"),
        ("Misleading and fake review. Paisa zaya ho gaya.",               20,  "BrandA_Campaign"),
        ("Just ordered two, game changer product!",                       80,  "BrandA_Campaign"),
        ("The commercial is okay.",                                        3,  "BrandB_Ad"),
        ("Worth buying! Kya marketing hai zabardast.",                    95,  "BrandB_Ad"),
        ("Terrible ad, cringe commercial and boring.",                    12,  "BrandB_Ad"),
        ("Loved the ad, shut up and take my money!",                     140,  "BrandB_Ad"),
        ("Bahut acha product hai, paisa wasool!",                         65,  "BrandB_Ad"),
        ("Clickbait and bad marketing, bilkul bekar.",                     5,  "BrandB_Ad"),
    ]

    df = pd.DataFrame(sample, columns=["text", "likes", "channel_name"])
    df["published_at"] = ""
    df["video_title"] = "Sample Marketing Ad Review"

    # VADER sentiment
    df["sentiment_score"] = df["text"].apply(lambda t: _vader_score(t, analyser))
    df["sentiment_label"] = df["sentiment_score"].apply(_label_from_score)
    df = add_marketing_signals(df)

    print("\n" + "=" * 75)
    print("SELF-TEST: Marketing Comment-level analysis")
    print("=" * 75)
    cols = ["text", "likes", "sentiment_score", "sentiment_label", "is_intent", "is_friction"]
    for _, row in df[cols].iterrows():
        snippet = textwrap.shorten(row["text"], width=48, placeholder="...")
        print(
            f"  {snippet:<50} "
            f"score={row['sentiment_score']:+.3f} "
            f"({row['sentiment_label']:<8}) "
            f"intent={str(row['is_intent']):<5} friction={row['is_friction']}"
        )

    ranking = compute_channel_scores(df)
    print("\n" + "=" * 75)
    print("SELF-TEST: Marketing Channel scoring result")
    print("=" * 75)
    cols2 = ["channel", "marketing_score", "confidence", "comment_count",
             "positive_pct", "intent_pct", "friction_pct"]
    print(ranking[cols2].to_string(index=True))

    top = ranking.iloc[0]
    print(f"\n  Top pick in self-test: {top['channel']}  (marketing_score={top['marketing_score']:.2f})")
    print("\nSelf-test passed.")


if "--self-test" in sys.argv:
    _self_test()
    sys.exit(0)

if __name__ == "__main__":
    main()
