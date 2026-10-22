"""
Fetcher for standard RSS and Atom feeds.
"""

from typing import List, Optional
from datetime import datetime, timezone, timedelta
import time
import requests
import feedparser
from dateutil import parser as date_parser
import urllib3

from src.models import Article, SourceConfig
from src.fetchers.base import BaseFetcher

# Suppress insecure request warnings for feeds with self-signed or expired certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RSSFetcher(BaseFetcher):
    """Fetches articles from RSS/Atom feeds with robust error resilience."""

    def __init__(self, config: SourceConfig, timeout: int = 12, max_entries: int = 30):
        super().__init__(config, timeout)
        self.max_entries = max_entries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Brief/1.0 (RSS Aggregator)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
        })

    def _parse_date(self, entry: dict) -> datetime:
        """Extract and parse publication date into a timezone-aware UTC datetime."""
        # 1. Check time struct from feedparser
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct:
            try:
                dt = datetime.fromtimestamp(time.mktime(time_struct), tz=timezone.utc)
                return dt
            except Exception:
                pass

        # 2. Check string date fields
        for field in ("published", "pubDate", "updated", "created", "dc:date"):
            date_str = entry.get(field)
            if date_str:
                try:
                    dt = date_parser.parse(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt
                except Exception:
                    continue

        # Fallback to now UTC if completely missing
        return datetime.now(timezone.utc)

    def fetch(self, cutoff_time: datetime) -> List[Article]:
        """Fetch articles from the RSS feed published on or after cutoff_time."""
        articles: List[Article] = []
        try:
            # First try with verified SSL
            try:
                resp = self.session.get(self.config.url, timeout=self.timeout)
            except requests.exceptions.SSLError:
                # Fallback to unverified SSL if certificate issue
                resp = self.session.get(self.config.url, timeout=self.timeout, verify=False)

            if resp.status_code != 200:
                return []

            parsed_feed = feedparser.parse(resp.content)
            entries = parsed_feed.entries[:self.max_entries]

            for entry in entries:
                pub_date = self._parse_date(entry)
                if pub_date < cutoff_time:
                    continue

                raw_title = entry.get("title", "")
                title = self.clean_title(raw_title)
                if not title:
                    continue

                link = entry.get("link", "").strip()
                if not link:
                    continue
                canonical_link = self.canonicalize_url(link)

                # Summary extraction
                raw_summary = (
                    entry.get("summary")
                    or entry.get("description")
                    or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
                    or ""
                )
                summary = self.clean_text(raw_summary)

                # Author
                author = entry.get("author") or entry.get("dc_creator") or None

                # Tags / categories
                tags = []
                for t in entry.get("tags", []):
                    term = t.get("term") or t.get("label")
                    if term:
                        tags.append(term.strip().lower())

                art_id = Article.create_id(title, canonical_link)
                article = Article(
                    id=art_id,
                    title=title,
                    url=link,
                    canonical_url=canonical_link,
                    source_id=self.config.id,
                    source_name=self.config.name,
                    published_at=pub_date,
                    summary=summary[:1200],  # trim excessive summaries
                    category=self.config.category,
                    author=author,
                    tags=tags,
                    engagement_score=0.0,
                    comment_count=0,
                    raw_content=raw_summary[:2000]
                )
                articles.append(article)

        except Exception as e:
            # Non-blocking fetch error: source failure should not abort pipeline
            pass

        return articles
