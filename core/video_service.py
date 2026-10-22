"""
Video recommendation service for CodeSathi AI.

Strategy:
1. If YOUTUBE_API_KEY is configured → use YouTube Data API v3.
2. Otherwise → generate a YouTube search URL fallback.
3. Curated VideoLibraryEntry records from DB are checked first.

Never fabricates video titles, IDs, or thumbnails.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_API = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_API  = "https://www.googleapis.com/youtube/v3/videos"


# ---------------------------------------------------------------------------
# YouTube Data API search
# ---------------------------------------------------------------------------

def _youtube_api_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search YouTube using the Data API v3.
    Returns list of video dicts. Raises on failure.
    """
    api_key = getattr(settings, "YOUTUBE_API_KEY", "")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY not configured")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "videoCategoryId": "27",  # Education
        "key": api_key,
        "safeSearch": "strict",
        "relevanceLanguage": "en",
    }
    resp = requests.get(YOUTUBE_SEARCH_API, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    videos = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        vid_id = item.get("id", {}).get("videoId", "")
        if not vid_id:
            continue
        videos.append({
            "youtube_id": vid_id,
            "title": snippet.get("title", ""),
            "channel_name": snippet.get("channelTitle", ""),
            "thumbnail_url": (
                snippet.get("thumbnails", {})
                .get("medium", {})
                .get("url", "")
            ),
            "description": snippet.get("description", "")[:300],
            "watch_url": f"https://www.youtube.com/watch?v={vid_id}",
            "embed_url": f"https://www.youtube.com/embed/{vid_id}",
            "source": "youtube_api",
            "relevance_note": "",
        })
    return videos


# ---------------------------------------------------------------------------
# Curated library lookup
# ---------------------------------------------------------------------------

def _curated_videos(topic_key: str, language: str = "") -> list[dict]:
    """Return verified curated videos for a topic key."""
    try:
        from .models import VideoLibraryEntry
        qs = VideoLibraryEntry.objects.filter(topic_key=topic_key, verified=True)
        if language:
            qs = qs.filter(programming_language__iexact=language) | VideoLibraryEntry.objects.filter(
                topic_key=topic_key, verified=True, programming_language=""
            )
        results = []
        for v in qs[:5]:
            results.append({
                "youtube_id": v.youtube_id,
                "title": v.title,
                "channel_name": v.channel_name,
                "thumbnail_url": v.thumbnail_url,
                "description": v.description,
                "watch_url": v.watch_url,
                "embed_url": v.embed_url,
                "source": "curated_library",
                "relevance_note": f"Curated for: {topic_key}",
                "is_sample_data": v.is_sample_data,
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Search fallback
# ---------------------------------------------------------------------------

def _search_fallback(query: str) -> list[dict]:
    """Generate a YouTube search link. No actual video IDs are fabricated."""
    import urllib.parse
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    return [{
        "youtube_id": None,
        "title": f"Search YouTube: {query}",
        "channel_name": "",
        "thumbnail_url": "",
        "description": (
            "No live video search is available right now. "
            "Click to search YouTube directly."
        ),
        "watch_url": search_url,
        "embed_url": "",
        "source": "search_fallback",
        "relevance_note": "YouTube search link — no API results available",
        "is_sample_data": False,
    }]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_video_recommendations(
    concept: str,
    programming_language: str = "",
    error_type: str = "",
    difficulty: str = "beginner",
    max_results: int = 5,
) -> dict:
    """
    Get video recommendations for a concept.

    Returns:
        {
          "videos": [...],
          "source": "youtube_api" | "curated_library" | "search_fallback",
          "search_query": str,
          "error": str or None,
        }
    """
    # Build search query
    parts = []
    if programming_language:
        parts.append(programming_language)
    parts.append(concept)
    if error_type:
        parts.append(error_type)
    parts += ["tutorial", "beginner"]
    query = " ".join(parts)

    # 1. Try curated library
    topic_key = _make_topic_key(concept, programming_language, error_type)
    curated = _curated_videos(topic_key, programming_language)
    if curated:
        return {
            "videos": curated,
            "source": "curated_library",
            "search_query": query,
            "error": None,
        }

    # 2. Try YouTube API
    api_key = getattr(settings, "YOUTUBE_API_KEY", "")
    if api_key:
        try:
            videos = _youtube_api_search(query, max_results)
            if videos:
                # Add relevance notes
                for v in videos:
                    v["relevance_note"] = (
                        f"Recommended for: {concept}"
                        + (f" ({programming_language})" if programming_language else "")
                    )
                return {
                    "videos": videos,
                    "source": "youtube_api",
                    "search_query": query,
                    "error": None,
                }
        except requests.exceptions.RequestException as exc:
            logger.warning("YouTube API network error: %s", exc)
            error_msg = f"YouTube API network error: {exc}"
        except Exception as exc:
            logger.warning("YouTube API error: %s", exc)
            error_msg = str(exc)
        return {
            "videos": _search_fallback(query),
            "source": "search_fallback",
            "search_query": query,
            "error": error_msg,
        }

    # 3. Search fallback (no API key configured)
    return {
        "videos": _search_fallback(query),
        "source": "search_fallback",
        "search_query": query,
        "error": "YouTube API key not configured. Showing search link only.",
    }


def _make_topic_key(concept: str, language: str, error_type: str) -> str:
    """Normalise to a simple topic key for DB lookup."""
    base = (concept + " " + language + " " + error_type).lower().strip()
    import re
    return re.sub(r"\s+", "_", base)[:100]
