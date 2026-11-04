"""
gui_server.py
=============
Local web dashboard server for YouTube Product Review & Commercial Analyzer.
Analyzes ANY product review video — tech, beauty, food, gaming, fashion, automotive,
home appliances, marketing ads, and more. Strictly filters out pure educational/academic
lectures that have no product or commercial angle.
Provides interactive visual graphs, sentiment breakdowns, product review scores (0-100),
Roman Urdu purchase intent / friction signals, and follower vs non-follower audience analysis.

FOLLOWER DETECTION STRATEGY
----------------------------
YouTube Data API v3 does NOT expose subscriber status per comment.
We use two proxy signals to separate "Brand Followers / Advocates" from "Casual Prospects":

  1. REPEAT COMMENTER  – A commenter whose channel-ID appears more than once
     in the fetched dataset (they consistently engage → likely brand subscriber).
  2. HIGH-LIKE COMMENTER – A commenter whose comment(s) received >= 5 likes
     (community recognises them → likely active brand follower).

Commenters matching EITHER signal are labelled "Brand Follower (Proxy)".
All others are labelled "Casual Prospect / Viewer".
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
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

# --- Educational / Academic Terms for Strict Rejection ---
# ONLY pure academic lectures (no product angle) are rejected.
ACADEMIC_EDU_TERMS: list[str] = [
    "physics lecture", "chemistry lecture", "mathematics lecture",
    "calculus tutorial", "algebra tutorial", "geometry tutorial",
    "fsc lecture", "cbse lecture", "neet preparation", "jee preparation",
    "ncert solution", "board exam preparation", "past papers solution",
    "lecture 1", "lecture 2", "lecture 3",
    "exercise 1 solution", "exercise 2 solution",
    "class 9 lecture", "class 10 lecture", "class 11 lecture", "class 12 lecture",
    "biology lecture", "organic chemistry lecture", "linear algebra lecture",
    "differentiation tutorial", "integration tutorial",
    "thermodynamics lecture", "quantum mechanics lecture",
    "exam preparation lecture", "academic lesson", "school lecture",
    "university lecture", "curriculum lesson", "course lecture",
    "solution manual", "derivation proof", "theorem proof",
    "matric lecture", "intermediate lecture",
]

# --- Product / Commercial / Review Terms for Validation ---
# Accepts ANY product review, unboxing, comparison, marketing ad, brand campaign, etc.
PRODUCT_REVIEW_TERMS: list[str] = [
    # Generic review / product signals
    "review", "unboxing", "unbox", "hands on", "hands-on", "first look",
    "first impression", "impressions", "worth it", "should you buy",
    "best", "top", "comparison", "vs", "versus", "which is better",
    "buying guide", "honest review", "detailed review", "full review",
    "pros and cons", "is it worth", "after using", "long term review",

    # Tech & Gadgets
    "iphone", "samsung", "pixel", "oneplus", "xiaomi", "redmi", "realme",
    "oppo", "vivo", "huawei", "nothing phone", "smartphone", "phone review",
    "laptop review", "macbook", "dell xps", "lenovo", "hp laptop", "asus",
    "tablet review", "ipad", "galaxy tab", "headphones", "earbuds", "airpods",
    "smartwatch", "apple watch", "galaxy watch", "cpu", "gpu", "graphics card",
    "gaming pc", "rtx", "monitor review", "keyboard review", "mouse review",
    "camera review", "dslr", "mirrorless", "gopro", "drone review",
    "tv review", "oled", "qled", "projector review", "speaker review",
    "router review", "tech review", "gadget review", "product review",

    # Gaming
    "game review", "gaming review", "gameplay", "ps5 review", "xbox review",
    "nintendo switch", "gaming controller", "gaming headset", "gaming chair",
    "gaming mouse", "gaming keyboard", "steam deck", "game worth buying",

    # Beauty, Skincare & Makeup
    "skincare review", "makeup review", "foundation review", "lipstick review",
    "serum review", "moisturizer review", "sunscreen review", "toner review",
    "beauty review", "product review", "skincare routine", "makeup tutorial review",
    "hair care review", "shampoo review", "conditioner review", "perfume review",
    "nail polish review", "eye shadow", "mascara review", "blush review",

    # Fashion & Clothing
    "fashion review", "clothing review", "outfit review", "haul",
    "try on haul", "sneaker review", "shoe review", "nike review", "adidas review",
    "watch review", "bag review", "purse review", "accessory review",

    # Food & Beverages
    "food review", "taste test", "restaurant review", "fast food review",
    "grocery haul", "snack review", "drink review", "coffee review",
    "energy drink review", "recipe review", "mukbang", "cooking review",

    # Automotive
    "car review", "suv review", "electric car review", "ev review",
    "tesla review", "bmw review", "mercedes review", "toyota review",
    "bike review", "motorcycle review", "test drive", "auto review",
    "mileage review", "fuel efficiency",

    # Home & Appliances
    "home appliance", "refrigerator review", "washing machine review",
    "air conditioner review", "ac review", "vacuum cleaner review",
    "air fryer review", "blender review", "kitchen appliance",
    "furniture review", "mattress review", "pillow review",
    "smart home", "alexa review", "google home review", "robot vacuum",

    # Health & Fitness
    "supplement review", "protein powder review", "gym equipment review",
    "treadmill review", "fitness tracker review", "health product review",
    "vitamin review", "pre workout review",

    # Books, Courses & Entertainment
    "book review", "course review", "app review", "software review",
    "subscription review", "netflix review", "streaming review",

    # Marketing / Ads / Commercial
    "marketing", "ad review", "ad breakdown", "commercial review",
    "advertisement", "commercial", "brand review", "brand strategy",
    "super bowl ad", "marketing strategy", "digital marketing",
    "influencer marketing", "product marketing", "unboxing review",
    "marketing case study", "ad critique", "promotional campaign",
    "brand campaign", "sponsored review", "viral marketing",
    "marketing tips", "marketing analysis", "ad analysis",
    "ecommerce", "e-commerce", "dropshipping",

    # Roman Urdu product review signals
    "review kar raha", "unboxing kar raha", "kitna acha", "kaisa lagta",
    "khareedna chahiye", "product kaisa hai", "review in urdu",
    "review in hindi", "pakistani review", "indian review",
]

# --- Phrase Signals: Positive Purchase Intent & Product Praise ---
PURCHASE_INTENT_PHRASES: list[str] = [
    # English: Purchase intent, product love, positive reception
    "bought this", "bought it", "buying this", "buying right now", "just bought",
    "take my money", "just ordered", "worth the money", "worth buying",
    "great product", "must buy", "game changer", "highly recommend",
    "sold me", "need this", "ordering now", "want this", "add to cart",
    "will purchase", "shut up and take my money", "best investment",
    "definitely buying", "signing up", "downloading now", "got me sold",
    "worth every penny", "ordered one", "got mine", "picked this up",
    "10/10 product", "love this product", "absolutely love it",
    "best purchase", "great purchase", "happy with this",
    "exceeded expectations", "would buy again", "already ordered",
    "impressed by this", "actually worth it", "surprised me",
    "this is amazing", "so good", "best ever", "five stars",
    "5 stars", "perfect product", "love the quality", "best quality",
    # Gaming signals
    "best game", "game of the year", "must play", "worth every penny",
    "buying this game", "great gameplay",
    # Beauty/skincare signals
    "holy grail", "repurchasing", "already repurchased", "skin loves it",
    "works great", "glowing skin", "amazing results",
    # Food signals
    "so delicious", "highly recommend", "must try", "so tasty", "amazing taste",
    # Tech signals
    "best smartphone", "best laptop", "great battery life", "fast phone",
    "love the camera", "best value", "flagship killer",
    # Marketing/ad signals
    "great campaign", "brilliant ad", "genius marketing", "best ad",
    "clever ad", "loved the ad", "great commercial", "effective campaign",
    # Roman Urdu & Urdu: Product praise & purchase intent
    "kharid liya", "kharid raha hoon", "kharidna hai", "paisa wasool",
    "kya product hai", "zabardast product", "bohat zabardast product",
    "bohat acha product", "best product hai", "order kar diya",
    "mangwa liya", "shandar product", "kamal ka product", "lazmi kharidain",
    "paisa wasool product", "dil jeet liya", "shandar quality",
    "faydemand product", "zarur lunga", "zarur kharidunga",
    "kya baat hai is product ki", "zabardast quality", "lajawab product",
    "lazmi lena hai", "kamal hai yeh", "kharid li", "acha product",
    "bahut acha laga", "khushi hui kharid ke", "behtareen product",
    "kya zabardast hai", "try karna chahiye", "bilkul sahi hai",
    "kya ad hai", "zabardast ad", "bohat acha ad", "kamal ki marketing",
    "shandar commercial", "lajawab ad",
]

# --- Phrase Signals: Negative Reception, Skepticism & Concerns ---
MARKETING_FRICTION_PHRASES: list[str] = [
    # English: Product complaints, bad reviews, skepticism
    "scam", "overpriced", "waste of money", "don't buy", "do not buy",
    "clickbait", "fake review", "paid review", "fake", "misleading",
    "not worth it", "too expensive", "hyped up", "boycott", "fraud",
    "false advertising", "dishonest", "worst product", "broken product",
    "poor quality", "bad quality", "cheap quality", "fell apart",
    "stopped working", "returned it", "refund", "returned this",
    "would not recommend", "do not recommend", "disappointed",
    "waste of time", "overrated", "rip off", "ripoff", "dont buy",
    "dont waste", "skip this", "garbage", "junk", "terrible product",
    "worst purchase", "regret buying", "bad experience", "broke after",
    "died after", "stopped working", "defective", "faulty product",
    "battery drains fast", "overheating", "lagging", "slow phone",
    "blurry camera", "bad camera", "screen broke", "cracked screen",
    "not as advertised", "doesn't work", "does not work",
    # Gaming
    "pay to win", "broken game", "unplayable", "too many bugs",
    "worst game", "refunded this game",
    # Beauty/skincare
    "broke me out", "skin reaction", "allergic reaction", "irritated skin",
    "doesn't work", "no results", "useless product",
    # Food
    "tastes awful", "disgusting", "not edible", "worst food",
    "made me sick", "food poisoning",
    # Tech
    "bad battery", "overheats", "screen issues", "build quality bad",
    # Marketing/ad
    "cringe ad", "bad marketing", "annoying ad", "boring ad",
    "worst ad", "terrible marketing", "bad commercial", "deceptive",
    "greenwashing", "shady marketing",
    # Roman Urdu & Urdu: Negative product feedback
    "paisa zaya", "bekaar product", "fazool product", "mat kharidna",
    "dhoka", "fraud hai", "loot rahe hain", "koi faida nahi",
    "bekar product", "cringe hai", "jhoota review", "ghatiya quality",
    "bohat mehenga", "mehenga hai", "kharab product", "mat lena",
    "bura product", "kuch faida nahi", "bakwas product", "time waste",
    "kisi kaam ka nahi", "dhokay baazi", "bilkul bekar", "fraud company",
    "nahi kharidna", "paisa waste", "nakami", "quality kharab hai",
    "toot gaya", "kharab ho gaya", "wapas kar diya", "refund manga",
    "bekar ad", "fazool ad", "ghatiya marketing", "boring commercial",
]

# Aliases for backward compatibility
HELPED_PHRASES = PURCHASE_INTENT_PHRASES
CONFUSED_PHRASES = MARKETING_FRICTION_PHRASES

# Scoring Weights
WEIGHT_SENTIMENT: float = 0.50
WEIGHT_INTENT: float = 0.30
WEIGHT_FRICTION: float = 0.20

WEIGHT_HELPED: float = WEIGHT_INTENT
WEIGHT_CONFUSED: float = WEIGHT_FRICTION

vader_analyzer = SentimentIntensityAnalyzer()

# Alias: old name still used in some call sites
MARKETING_TERMS = PRODUCT_REVIEW_TERMS


def validate_marketing_video(video_meta: dict) -> tuple[bool, str]:
    """
    Validate that the video is a product review, unboxing, commercial breakdown,
    or any video discussing a product, brand, or service.

    Accepts:
      - Product reviews of ANY category (tech, beauty, food, gaming, fashion, auto, etc.)
      - Marketing ads, commercial breakdowns, brand campaign analyses
      - Unboxing, comparison, buying guide videos
      - Sponsored / influencer product videos

    Rejects ONLY:
      - Pure academic/educational lectures with zero product signals
        (e.g. math class, physics tutorial, board exam prep)

    Returns (True, "OK") if accepted, or (False, error_reason) if rejected.
    """
    title = video_meta.get("title", "").strip()
    desc  = video_meta.get("description", "").strip()
    tags  = [str(t).lower() for t in video_meta.get("tags", [])]
    cat_id = str(video_meta.get("category_id", "")).strip()
    combined_text = f"{title} {desc} {' '.join(tags)}".lower()

    # Check for product/commercial/review signals (very broad)
    has_product_signals = any(term in combined_text for term in PRODUCT_REVIEW_TERMS)

    # Check for PURE academic lecture signals (strict multi-word phrases)
    has_pure_academic = any(term in combined_text for term in ACADEMIC_EDU_TERMS)

    # YouTube category 27 = Education
    is_cat_education = (cat_id == "27")

    # REJECT: Educational category with no product review signals
    if is_cat_education and not has_product_signals:
        return (
            False,
            f"❌ Rejection: '{title}' is classified under YouTube's 'Education' category. "
            f"This analyzer only processes product reviews, unboxings, commercial breakdowns, "
            f"and marketing campaigns. Academic coursework or lectures are not allowed."
        )

    # REJECT: Academic terms with no product signals
    if has_pure_academic and not has_product_signals:
        return (
            False,
            f"❌ Rejection: '{title}' is detected as an academic or educational lecture. "
            f"This analyzer is strictly for product reviews, commercial breakdowns, and consumer feedback."
        )

    # ACCEPT: has product/review/commercial signals
    if has_product_signals:
        return (True, "Product/Review video verified.")

    # REJECT: unrelated content lacking product review signals
    return (
        False,
        f"❌ Rejection: '{title}' does not contain recognized product review, unboxing, "
        f"commercial, or consumer product signals. Please paste a product review or marketing video."
    )


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
    """Fetch video title, channel, stats, category, tags, and thumbnails."""
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
        "description": sn.get("description", "")[:500],
        "category_id": sn.get("categoryId", ""),
        "tags": sn.get("tags", []),
        "thumbnail_url": thumb_url,
        "view_count": int(st.get("viewCount", 0)),
        "like_count": int(st.get("likeCount", 0)),
        "comment_count": int(st.get("commentCount", 0)),
    }


def fetch_video_comments(video_id: str, max_comments: int = 2000) -> list[dict]:
    """
    Fetch top-level comments with likes, authors, timestamps, and author channel IDs.

    Supports fetching at least 2000 comments (and up to 5000) using automatic pagination.
    Each page returns up to 100 results (YouTube API maximum per page).
    The `author_channel_id` field is used downstream for follower-proxy detection.

    Args:
        video_id:     YouTube video ID to fetch comments for.
        max_comments: Maximum number of comments to retrieve (default 2000).

    Returns:
        List of comment dicts, each containing:
          id, author, author_channel_id, author_avatar, text, likes, published_at.
    """
    comments: list[dict] = []
    page_token: str | None = None
    page_num = 0
    print(f"[COMMENTS] Initiating fetch for video '{video_id}' (target: up to {max_comments} comments)...")

    while len(comments) < max_comments:
        page_num += 1
        # YouTube allows max 100 results per commentThreads page
        batch_size = min(max_comments - len(comments), 100)
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": batch_size,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token  # Continue from previous page

        data = yt_get("commentThreads", params)
        if not data or "items" not in data:
            break  # API returned empty or error — stop pagination

        items = data.get("items", [])
        if not items:
            break

        for it in items:
            sn = it["snippet"]["topLevelComment"]["snippet"]
            # Extract author channel ID for follower-proxy detection
            author_ch_id = sn.get("authorChannelId", {}).get("value", "") if isinstance(
                sn.get("authorChannelId"), dict
            ) else sn.get("authorChannelId", "")
            comments.append({
                "id": it["id"],
                "author": sn.get("authorDisplayName", "Viewer"),
                "author_channel_id": author_ch_id,   # used for follower detection
                "author_avatar": sn.get("authorProfileImageUrl", ""),
                "text": sn.get("textDisplay", ""),
                "likes": int(sn.get("likeCount", 0)),
                "published_at": sn.get("publishedAt", ""),
            })
            if len(comments) >= max_comments:
                break  # Reached requested cap

        if page_num % 5 == 0 or len(comments) >= max_comments:
            print(f"       [Page {page_num}] Accumulated {len(comments)} / {max_comments} comments...")

        page_token = data.get("nextPageToken")
        if not page_token:
            break  # No more pages available

    print(f"[COMMENTS] Finished fetch: {len(comments)} total comments retrieved.")
    return comments


def _classify_followers(comments: list[dict], channel_id: str) -> dict[str, str]:
    """
    Classify each commenter as "follower" or "non_follower" using proxy signals.

    Since the YouTube API does not expose subscriber status per comment, we use
    two behavioral proxies to identify likely engaged followers:

      Signal 1 – REPEAT COMMENTER:
        If the same author_channel_id appears more than once in the fetched
        dataset, they engage repeatedly → likely a subscriber.

      Signal 2 – HIGH-LIKE COMMENTER:
        If any comment by this author received >= 5 likes, the community
        recognises them as a regular contributor → likely a follower.

      Special case – CHANNEL OWNER:
        If the commenter's channel ID matches the video's channel ID,
        they are the channel owner (always classified as follower).

    Args:
        comments:   List of comment dicts (must contain author_channel_id & likes).
        channel_id: The video's parent channel ID for owner detection.

    Returns:
        Dict mapping author_channel_id → "follower" | "non_follower".
        Empty-string author_channel_ids are mapped to "non_follower".
    """
    from collections import Counter

    # Count how many times each author_channel_id appears
    id_counts: Counter = Counter(
        c["author_channel_id"] for c in comments if c.get("author_channel_id")
    )

    # Track max likes per author_channel_id
    max_likes: dict[str, int] = {}
    for c in comments:
        aid = c.get("author_channel_id", "")
        if aid:
            max_likes[aid] = max(max_likes.get(aid, 0), c.get("likes", 0))

    follower_map: dict[str, str] = {}
    for aid in id_counts:
        is_owner      = (aid == channel_id and bool(channel_id))  # channel owner
        is_repeat     = id_counts[aid] > 1                         # posted multiple times
        is_high_liked = max_likes.get(aid, 0) >= 5                # recognised by community
        if is_owner or is_repeat or is_high_liked:
            follower_map[aid] = "follower"
        else:
            follower_map[aid] = "non_follower"

    return follower_map


def _score_subset(subset: list[dict]) -> dict:
    """
    Compute sentiment counts, purchase intent & ad friction counts, and marketing_score
    for a subset of already-analyzed comment dicts.

    This is a lightweight aggregation helper used to produce separate stats
    for the follower and non-follower segments.

    Args:
        subset: List of analyzed comment dicts (from analyze_comments output).

    Returns:
        Dict with total_comments, sentiment_summary, signals_summary,
        marketing_score, and confidence for the subset.
    """
    n = len(subset)
    if n == 0:
        return {
            "total_comments": 0,
            "marketing_score": 0.0,
            "edu_score": 0.0,  # alias
            "confidence": "Low",
            "sentiment_summary": {"positive_count": 0, "positive_pct": 0.0,
                                   "neutral_count": 0, "neutral_pct": 0.0,
                                   "negative_count": 0, "negative_pct": 0.0},
            "signals_summary": {"intent_count": 0, "intent_pct": 0.0,
                                 "friction_count": 0, "friction_pct": 0.0,
                                 "helped_count": 0, "helped_pct": 0.0,
                                 "confused_count": 0, "confused_pct": 0.0},
        }

    pos_count  = sum(1 for c in subset if c["sentiment_label"] == "positive")
    neu_count  = sum(1 for c in subset if c["sentiment_label"] == "neutral")
    neg_count  = sum(1 for c in subset if c["sentiment_label"] == "negative")
    intent_cnt = sum(1 for c in subset if c.get("is_intent", c.get("is_helped", False)))
    friction_cnt = sum(1 for c in subset if c.get("is_friction", c.get("is_confused", False)))

    # Like-weighted average sentiment for this subset
    total_weights = sum(float(c["likes"] + 1) for c in subset)
    lw_sentiment  = sum(c["sentiment_score"] * float(c["likes"] + 1) for c in subset) / total_weights

    sentiment_0_100 = (lw_sentiment + 1.0) / 2.0 * 100.0
    intent_pct   = (intent_cnt   / n) * 100.0
    friction_pct = (friction_cnt / n) * 100.0

    marketing_score = (
        WEIGHT_SENTIMENT * sentiment_0_100
        + WEIGHT_INTENT  * intent_pct
        + WEIGHT_FRICTION * (100.0 - friction_pct)
    )
    marketing_score = max(0.0, min(100.0, marketing_score))

    confidence = "Low" if n < 50 else ("Medium" if n <= 200 else "High")

    return {
        "total_comments": n,
        "product_score": round(marketing_score, 1),
        "marketing_score": round(marketing_score, 1),
        "edu_score": round(marketing_score, 1),  # alias for backward compatibility
        "confidence": confidence,
        "lw_sentiment": round(lw_sentiment, 3),
        "sentiment_summary": {
            "positive_count": pos_count,
            "positive_pct":   round((pos_count  / n) * 100, 1),
            "neutral_count":  neu_count,
            "neutral_pct":    round((neu_count  / n) * 100, 1),
            "negative_count": neg_count,
            "negative_pct":   round((neg_count  / n) * 100, 1),
        },
        "signals_summary": {
            "intent_count":   intent_cnt,
            "intent_pct":     round(intent_pct,   1),
            "friction_count": friction_cnt,
            "friction_pct":   round(friction_pct, 1),
            # Aliases
            "helped_count":   intent_cnt,
            "helped_pct":     round(intent_pct,   1),
            "confused_count": friction_cnt,
            "confused_pct":   round(friction_pct, 1),
        },
    }


def analyze_comments(comments: list[dict], channel_id: str = "") -> dict:
    """
    Perform sentiment analysis, marketing phrase detection, marketing scoring,
    and follower vs non-follower audience breakdown.

    Steps:
      1. Run VADER sentiment on each comment text.
      2. Detect PURCHASE_INTENT_PHRASES and MARKETING_FRICTION_PHRASES.
      3. Compute like-weighted marketing review score (0-100) for all comments.
      4. Classify commenters as brand follower or casual prospect (proxy-based).
      5. Produce separate stats for each audience segment.

    Args:
        comments:   Raw comment dicts from fetch_video_comments().
        channel_id: Parent channel ID; used for owner detection in follower
                    classification. Pass empty string if unknown.

    Returns:
        Analysis dict containing overall stats, per-comment details,
        follower/non-follower segment breakdowns, and top evidence comments.
    """
    # Early return for empty input — all counters zeroed
    if not comments:
        empty_segment = _score_subset([])
        return {
            "total_comments": 0,
            "marketing_score": 0,
            "edu_score": 0,
            "confidence": "Low",
            "sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0},
            "signals_summary": {
                "intent": 0, "friction": 0,
                "helped": 0, "confused": 0
            },
            "matched_phrases": [],
            "comments": [],
            "follower_analysis": {
                "followers": empty_segment,
                "non_followers": empty_segment,
            },
        }

    phrase_counts: dict[str, int] = {}
    total_likes = 0
    pos_count = 0
    neu_count = 0
    neg_count = 0
    intent_count = 0
    friction_count = 0
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
        matched_intent: list[str] = []
        matched_friction: list[str] = []

        for p in PURCHASE_INTENT_PHRASES:
            if p in lower_text:
                matched_intent.append(p)
                phrase_counts[p] = phrase_counts.get(p, 0) + 1

        for p in MARKETING_FRICTION_PHRASES:
            if p in lower_text:
                matched_friction.append(p)
                phrase_counts[p] = phrase_counts.get(p, 0) + 1

        is_intent = len(matched_intent) > 0
        is_friction = len(matched_friction) > 0

        if is_intent:
            intent_count += 1
        if is_friction:
            friction_count += 1

        analyzed_comments.append({
            **c,
            "sentiment_score": round(score, 3),
            "sentiment_label": label,
            "is_intent": is_intent,
            "is_friction": is_friction,
            "matched_intent": matched_intent,
            "matched_friction": matched_friction,
            # Aliases for frontend backward compatibility
            "is_helped": is_intent,
            "is_confused": is_friction,
            "matched_helped": matched_intent,
            "matched_confused": matched_friction,
        })

    n = len(comments)
    # Compute overall like-weighted sentiment
    lw_sentiment    = (weighted_sentiment_sum / total_weights) if total_weights > 0 else 0.0
    sentiment_0_100 = (lw_sentiment + 1.0) / 2.0 * 100.0

    intent_pct   = (intent_count / n) * 100.0
    friction_pct = (friction_count / n) * 100.0
    positive_pct = (pos_count / n) * 100.0
    neutral_pct  = (neu_count  / n) * 100.0
    negative_pct = (neg_count  / n) * 100.0

    # Overall marketing review score clamped to [0, 100]
    marketing_score = (
        WEIGHT_SENTIMENT * sentiment_0_100
        + WEIGHT_INTENT  * intent_pct
        + WEIGHT_FRICTION * (100.0 - friction_pct)
    )
    marketing_score = max(0.0, min(100.0, marketing_score))

    # Confidence tier based on total analyzed comments (>200 = High)
    confidence = "Low" if n < 50 else ("Medium" if n <= 200 else "High")

    # Top 10 most-frequent marketing phrases across all comments
    sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top 5 most-liked comments in each signal category (evidence cards)
    top_intent = sorted(
        [c for c in analyzed_comments if c["is_intent"]],
        key=lambda x: x["likes"],
        reverse=True
    )[:5]

    top_friction = sorted(
        [c for c in analyzed_comments if c["is_friction"]],
        key=lambda x: x["likes"],
        reverse=True
    )[:5]

    # ------------------------------------------------------------------
    # FOLLOWER vs NON-FOLLOWER BREAKDOWN
    # ------------------------------------------------------------------
    follower_map = _classify_followers(analyzed_comments, channel_id)

    # Tag each analyzed comment with its audience segment label
    for c in analyzed_comments:
        aid = c.get("author_channel_id", "")
        c["audience_segment"] = follower_map.get(aid, "non_follower")

    # Split the analyzed comments into two audience segments
    follower_comments     = [c for c in analyzed_comments if c["audience_segment"] == "follower"]
    non_follower_comments = [c for c in analyzed_comments if c["audience_segment"] == "non_follower"]

    # Compute independent stats for each audience segment
    follower_stats     = _score_subset(follower_comments)
    non_follower_stats = _score_subset(non_follower_comments)

    return {
        "total_comments":  n,
        "total_likes":     total_likes,
        "product_score":   round(marketing_score, 1),
        "marketing_score": round(marketing_score, 1),
        "edu_score":       round(marketing_score, 1),  # alias
        "confidence":      confidence,
        "lw_sentiment":    round(lw_sentiment, 3),
        "sentiment_summary": {
            "positive_count": pos_count,
            "positive_pct":   round(positive_pct, 1),
            "neutral_count":  neu_count,
            "neutral_pct":    round(neutral_pct,  1),
            "negative_count": neg_count,
            "negative_pct":   round(negative_pct, 1),
        },
        "signals_summary": {
            "intent_count":   intent_count,
            "intent_pct":     round(intent_pct,   1),
            "friction_count": friction_count,
            "friction_pct":   round(friction_pct, 1),
            # Aliases for frontend compatibility
            "helped_count":   intent_count,
            "helped_pct":     round(intent_pct,   1),
            "confused_count": friction_count,
            "confused_pct":   round(friction_pct, 1),
        },
        "top_phrases":  [{"phrase": p, "count": c} for p, c in sorted_phrases],
        "top_intent":   top_intent,
        "top_friction": top_friction,
        # Aliases for frontend
        "top_helped":   top_intent,
        "top_confused": top_friction,
        "comments":     analyzed_comments,
        # Audience-segment breakdown (follower proxy analysis)
        "follower_analysis": {
            "followers":     follower_stats,      # brand followers / advocates
            "non_followers": non_follower_stats,  # casual prospects / viewers
            "follower_count":     len(follower_comments),
            "non_follower_count": len(non_follower_comments),
        },
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
            # Support fetching at least 2000 comments (up to 5000); default 2000
            max_comments = int(data.get("max_comments", 2000))
            max_comments = max(10, min(max_comments, 5000))

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

            # Strict Marketing Review Validation: Reject Educational or non-marketing videos
            is_marketing, rejection_reason = validate_marketing_video(video_meta)
            if not is_marketing:
                self.send_json_response({
                    "error": rejection_reason
                }, status=400)
                return

            # Fetch up to max_comments (supports pagination up to 2000)
            comments = fetch_video_comments(video_id, max_comments=max_comments)
            if not comments:
                # Video has disabled comments or yielded 0 results
                analysis = analyze_comments([], channel_id=video_meta.get("channel_id", ""))
                self.send_json_response({
                    "video": video_meta,
                    "analysis": analysis,
                    "warning": "No comments could be retrieved. Comments may be disabled on this video."
                })
                return

            # Pass channel_id so follower detection can identify the channel owner
            analysis = analyze_comments(
                comments,
                channel_id=video_meta.get("channel_id", ""),
            )
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
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, AppHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"  🛍️  YouTube Product Review & Commercial Analyzer")
    print(f"  🌐 Running at: {url} (or http://localhost:{port})")
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
