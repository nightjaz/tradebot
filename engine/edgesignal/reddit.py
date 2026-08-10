from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import IntelligenceEvent
from .rss import SymbolResolver, strip_markup
from .sentiment import make_event


TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_ROOT = "https://oauth.reddit.com"
PROMOTIONAL = re.compile(
    r"\b(guaranteed|sure[- ]?shot|buy now|multibagger|upper circuit|to the moon|rocket|target price)\b",
    re.I,
)


@dataclass(frozen=True)
class SubredditSpec:
    name: str
    credibility: float
    enabled: bool = True
    limit: int = 50


@dataclass(frozen=True)
class RedditPost:
    source_id: str
    subreddit: str
    title: str
    body: str
    url: str
    published_at: datetime
    score: int
    comments: int
    upvote_ratio: float
    stickied: bool = False
    over_18: bool = False


def load_subreddits(path: str | Path) -> tuple[list[SubredditSpec], int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    specs = [SubredditSpec(**row) for row in payload["subreddits"] if row.get("enabled", True)]
    return specs, int(payload.get("retention_days", 14))


def parse_listing(payload: dict) -> list[RedditPost]:
    posts: list[RedditPost] = []
    for child in payload.get("data", {}).get("children", []):
        row = child.get("data", {})
        created = datetime.fromtimestamp(float(row.get("created_utc", 0)), tz=timezone.utc)
        permalink = row.get("permalink", "")
        posts.append(RedditPost(
            source_id=row.get("name") or f"t3_{row.get('id', '')}",
            subreddit=row.get("subreddit", ""),
            title=strip_markup(row.get("title", "")),
            body=strip_markup(row.get("selftext", "")),
            url=f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink,
            published_at=created,
            score=int(row.get("score", 0)),
            comments=int(row.get("num_comments", 0)),
            upvote_ratio=float(row.get("upvote_ratio", 0.5)),
            stickied=bool(row.get("stickied", False)),
            over_18=bool(row.get("over_18", False)),
        ))
    return posts


class RedditOAuthClient:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, timeout_seconds: int = 15):
        if not client_id or not client_secret or not user_agent:
            raise ValueError("Reddit OAuth requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT")
        if "/u/" not in user_agent:
            raise ValueError("REDDIT_USER_AGENT must include a contact username in Reddit's '(by /u/name)' format")
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self._token = ""

    def authenticate(self) -> str:
        encoded = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        request = Request(TOKEN_URL, data=urlencode({"grant_type": "client_credentials"}).encode(), method="POST",
            headers={"Authorization": f"Basic {encoded}", "User-Agent": self.user_agent,
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.load(response)
        self._token = payload.get("access_token", "")
        if not self._token:
            raise RuntimeError("Reddit OAuth response did not include an access token")
        return self._token

    def newest(self, spec: SubredditSpec) -> list[RedditPost]:
        token = self._token or self.authenticate()
        limit = max(1, min(spec.limit, 100))
        request = Request(f"{API_ROOT}/r/{spec.name}/new?raw_json=1&limit={limit}",
            headers={"Authorization": f"bearer {token}", "User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return parse_listing(json.load(response))


class RedditIngestor:
    def __init__(self, resolver: SymbolResolver):
        self.resolver = resolver

    def transform(self, spec: SubredditSpec, posts: list[RedditPost]) -> list[IntelligenceEvent]:
        ingested_at = datetime.now(timezone.utc)
        events: list[IntelligenceEvent] = []
        for post in posts:
            if post.stickied or post.over_18 or not post.title or post.body in {"[removed]", "[deleted]"}:
                continue
            analysis_text = f"{post.title} {post.body}"
            symbols = self.resolver.resolve(analysis_text)
            if not symbols:
                continue
            engagement = min(1.0, (max(post.score, 0) + 2 * max(post.comments, 0)) / 100.0)
            quality = spec.credibility * (0.55 + 0.30 * engagement + 0.15 * max(0.0, min(1.0, post.upvote_ratio)))
            if PROMOTIONAL.search(analysis_text) or len(symbols) > 3:
                quality *= 0.35
            # Keep only a compact excerpt; usernames are never collected.
            excerpt = post.body[:280]
            for symbol in symbols:
                events.append(make_event(f"reddit:r/{post.subreddit}", post.source_id, symbol,
                    post.published_at, post.title, excerpt, quality, ingested_at, post.url))
        return events
