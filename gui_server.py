"""
gui_server.py
=============
Local web dashboard server for YouTube Educational Video & Channel Analyzer.
Provides interactive visual graphs, sentiment breakdowns, education scores,
and Roman Urdu signal detection.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Load environment variables from .env
def _load_dotenv() -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_path):
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

_load_dotenv()

API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# --- Phrase Signals ---
HELPED_PHRASES: list[str] = [
    "thank you", "thanks", "helpful", "easy to understand", "helped me",
    "great explanation", "well explained", "amazing", "love this",
    "shukriya", "shukriya bhai", "samajh aa gaya", "samajh agaya",
    "samajh aagaya", "concept clear", "clear ho gaya", "clear hogaya",
    "maza aa gaya", "zabardast", "bohat acha", "bahut acha",
    "bahut helpful", "bohat helpful", "best channel", "best teacher",
    "mujhe samajh aa", "samajh aya", "very helpful", "nicely explained",
]

CONFUSED_PHRASES: list[str] = [
    "don't understand", "dont understand", "do not understand",
    "not clear", "too fast", "very fast", "can someone explain",
    "please explain", "i am confused", "i'm confused", "confusing",
    "wrong", "mistake", "incorrect", "samajh nahi", "samajh nahi aaya",
    "samajh nahi aya", "palla nahi", "samajh nahi aata",
    "please slow down", "slow down", "repeat", "kuch samajh nahi",
]

# Weights
WEIGHT_SENTIMENT: float = 0.50
WEIGHT_HELPED: float = 0.30
WEIGHT_CONFUSED: float = 0.20

vader_analyzer = SentimentIntensityAnalyzer()


def extract_video_id(url_or_id: str) -> str | None:
    """Extract 11-char YouTube video ID from various URL patterns or raw ID."""
    url_or_id = url_or_id.strip()
    if re.match(r"^[\w-]{11}$", url_or_id):
        return url_or_id
    
    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"[?&]v=([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return None


def yt_get(endpoint: str, params: dict[str, Any]) -> dict | None:
    """Query YouTube Data API v3 with timeout and error handling."""
    params["key"] = API_KEY
    url = f"{YT_API_BASE}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code == 200:
            return r.json()
        print(f"[API ERROR] {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"[REQUEST ERROR] {e}")
        return None


def fetch_video_details(video_id: str) -> dict | None:
    """Fetch video title, channel, stats, and thumbnails."""
    data = yt_get("videos", {
        "part": "snippet,statistics",
        "id": video_id,
    })
    if not data or not data.get("items"):
        return None
    item = data["items"][0]
    sn = item["snippet"]
    st = item.get("statistics", {})
    
    thumbs = sn.get("thumbnails", {})
    thumb_url = (
        thumbs.get("maxres", {}).get("url") or
        thumbs.get("high", {}).get("url") or
        thumbs.get("medium", {}).get("url") or
        thumbs.get("default", {}).get("url") or ""
    )
    
    return {
        "video_id": video_id,
        "title": sn.get("title", ""),
        "channel_title": sn.get("channelTitle", ""),
        "channel_id": sn.get("channelId", ""),
        "published_at": sn.get("publishedAt", ""),
        "description": sn.get("description", "")[:400],
        "thumbnail_url": thumb_url,
        "view_count": int(st.get("viewCount", 0)),
        "like_count": int(st.get("likeCount", 0)),
        "comment_count": int(st.get("commentCount", 0)),
    }


def fetch_video_comments(video_id: str, max_comments: int = 150) -> list[dict]:
    """Fetch top comments with likes, authors, and timestamps."""
    comments: list[dict] = []
    page_token: str | None = None
    
    while len(comments) < max_comments:
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": min(max_comments - len(comments), 100),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
            
        data = yt_get("commentThreads", params)
        if not data or "items" not in data:
            break
            
        for it in data.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "id": it["id"],
                "author": sn.get("authorDisplayName", "Viewer"),
                "author_avatar": sn.get("authorProfileImageUrl", ""),
                "text": sn.get("textDisplay", ""),
                "likes": int(sn.get("likeCount", 0)),
                "published_at": sn.get("publishedAt", ""),
            })
            if len(comments) >= max_comments:
                break
                
        page_token = data.get("nextPageToken")
        if not page_token:
            break
            
    return comments


def analyze_comments(comments: list[dict]) -> dict:
    """Perform sentiment analysis, phrase detection, and education scoring."""
    if not comments:
        return {
            "total_comments": 0,
            "edu_score": 0,
            "confidence": "Low",
            "sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0},
            "signals_summary": {"helped": 0, "confused": 0},
            "matched_phrases": [],
            "comments": [],
        }

    phrase_counts: dict[str, int] = {}
    total_likes = 0
    pos_count = 0
    neu_count = 0
    neg_count = 0
    helped_count = 0
    confused_count = 0
    weighted_sentiment_sum = 0.0
    total_weights = 0.0

    analyzed_comments = []

    for c in comments:
        text = c["text"]
        likes = c["likes"]
        total_likes += likes
        
        # VADER compound score in [-1, +1]
        score = float(vader_analyzer.polarity_scores(text)["compound"])
        if score >= 0.05:
            label = "positive"
            pos_count += 1
        elif score <= -0.05:
            label = "negative"
            neg_count += 1
        else:
            label = "neutral"
            neu_count += 1

        # Like weight
        w = float(likes + 1)
        weighted_sentiment_sum += score * w
        total_weights += w

        # Phrase detection
        lower_text = text.lower()
        matched_helped: list[str] = []
        matched_confused: list[str] = []

        for p in HELPED_PHRASES:
            if p in lower_text:
                matched_helped.append(p)
                phrase_counts[p] = phrase_counts.get(p, 0) + 1

        for p in CONFUSED_PHRASES:
            if p in lower_text:
                matched_confused.append(p)
                phrase_counts[p] = phrase_counts.get(p, 0) + 1

        is_helped = len(matched_helped) > 0
        is_confused = len(matched_confused) > 0

        if is_helped:
            helped_count += 1
        if is_confused:
            confused_count += 1

        analyzed_comments.append({
            **c,
            "sentiment_score": round(score, 3),
            "sentiment_label": label,
            "is_helped": is_helped,
            "is_confused": is_confused,
            "matched_helped": matched_helped,
            "matched_confused": matched_confused,
        })

    n = len(comments)
    lw_sentiment = (weighted_sentiment_sum / total_weights) if total_weights > 0 else 0.0
    sentiment_0_100 = (lw_sentiment + 1.0) / 2.0 * 100.0

    helped_pct = (helped_count / n) * 100.0
    confused_pct = (confused_count / n) * 100.0
    positive_pct = (pos_count / n) * 100.0
    neutral_pct = (neu_count / n) * 100.0
    negative_pct = (neg_count / n) * 100.0

    edu_score = (
        WEIGHT_SENTIMENT * sentiment_0_100
        + WEIGHT_HELPED * helped_pct
        + WEIGHT_CONFUSED * (100.0 - confused_pct)
    )
    edu_score = max(0.0, min(100.0, edu_score))

    confidence = "Low" if n < 50 else ("Medium" if n <= 200 else "High")

    # Top phrase list
    sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top evidence comments
    top_helped = sorted(
        [c for c in analyzed_comments if c["is_helped"]],
        key=lambda x: x["likes"],
        reverse=True
    )[:5]

    top_confused = sorted(
        [c for c in analyzed_comments if c["is_confused"]],
        key=lambda x: x["likes"],
        reverse=True
    )[:5]

    return {
        "total_comments": n,
        "total_likes": total_likes,
        "edu_score": round(edu_score, 1),
        "confidence": confidence,
        "lw_sentiment": round(lw_sentiment, 3),
        "sentiment_summary": {
            "positive_count": pos_count,
            "positive_pct": round(positive_pct, 1),
            "neutral_count": neu_count,
            "neutral_pct": round(neutral_pct, 1),
            "negative_count": neg_count,
            "negative_pct": round(negative_pct, 1),
        },
        "signals_summary": {
            "helped_count": helped_count,
            "helped_pct": round(helped_pct, 1),
            "confused_count": confused_count,
            "confused_pct": round(confused_pct, 1),
        },
        "top_phrases": [{"phrase": p, "count": c} for p, c in sorted_phrases],
        "top_helped": top_helped,
        "top_confused": top_confused,
        "comments": analyzed_comments,
    }


class AppHandler(SimpleHTTPRequestHandler):
    """Serve web assets and API endpoints."""
    def __init__(self, *args, **kwargs):
        directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
        super().__init__(*args, directory=directory, **kwargs)

    def do_POST(self):
        if self.path == "/api/analyze":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            try:
                data = json.loads(post_body.decode("utf-8"))
            except Exception:
                self.send_error(400, "Invalid JSON")
                return

            url_input = data.get("url", "").strip()
            max_comments = int(data.get("max_comments", 100))
            max_comments = max(10, min(max_comments, 300))

            if not API_KEY:
                self.send_json_response({
                    "error": "YOUTUBE_API_KEY is not configured in .env file."
                }, status=500)
                return

            video_id = extract_video_id(url_input)
            if not video_id:
                self.send_json_response({
                    "error": "Could not parse a valid YouTube video ID from your input. Please provide a standard YouTube video link or ID."
                }, status=400)
                return

            # Fetch video details
            video_meta = fetch_video_details(video_id)
            if not video_meta:
                self.send_json_response({
                    "error": f"Could not find video details for ID '{video_id}'. The video may be private, deleted, or the API key quota exceeded."
                }, status=404)
                return

            # Fetch comments
            comments = fetch_video_comments(video_id, max_comments=max_comments)
            if not comments:
                # Video has disabled comments or 0 comments
                analysis = analyze_comments([])
                self.send_json_response({
                    "video": video_meta,
                    "analysis": analysis,
                    "warning": "No comments could be retrieved. Comments may be disabled on this video."
                })
                return

            analysis = analyze_comments(comments)
            self.send_json_response({
                "video": video_meta,
                "analysis": analysis,
            })
            return

        self.send_error(404, "Endpoint not found")

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port: int = 5000):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, AppHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"  🌟 YouTube Educational Analyzer Web GUI")
    print(f"  🌐 Running at: {url}")
    print(f"  📂 Press Ctrl+C to stop the server")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    p = 5000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        p = int(sys.argv[1])
    run_server(p)
