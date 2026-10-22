"""
Base fetcher interface for all data sources.
"""

from abc import ABC, abstractmethod
from typing import List
from datetime import datetime, timezone
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from src.models import Article, SourceConfig


class BaseFetcher(ABC):
    """Abstract base class for all news & research source fetchers."""

    def __init__(self, config: SourceConfig, timeout: int = 12):
        self.config = config
        self.timeout = timeout

    @abstractmethod
    def fetch(self, cutoff_time: datetime) -> List[Article]:
        """Fetch articles published on or after cutoff_time."""
        pass

    @staticmethod
    def clean_text(html_or_text: str) -> str:
        """Strip HTML tags, decode entities, and normalize whitespace."""
        if not html_or_text:
            return ""
        # BeautifulSoup handles tags & HTML entities safely
        soup = BeautifulSoup(html_or_text, "html.parser")
        text = soup.get_text(separator=" ")
        # Remove extra whitespaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def clean_title(title: str) -> str:
        """Strip HTML tags and common publisher suffixes."""
        if not title:
            return ""
        t = BaseFetcher.clean_text(title)
        # Remove common trailing publication branding: ' - The Verge', ' | TechCrunch', etc.
        t = re.sub(r"\s*[\-|–|—|\|]\s*(The Verge|TechCrunch|Ars Technica|Wired|MIT Technology Review|MarkTechPost|Hacker News)$", "", t, flags=re.IGNORECASE)
        return t.strip()

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """Normalize URL by stripping tracking parameters, anchors, and standardizing path."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            # Filter tracking parameters
            tracking_params = {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "fbclid", "gclid", "msclkid", "ref", "source", "feed", "rss", "_hsenc", "_hsmi"
            }
            query_dict = parse_qs(parsed.query, keep_blank_values=False)
            filtered_query = {k: v for k, v in query_dict.items() if k.lower() not in tracking_params}
            new_query = urlencode(filtered_query, doseq=True)

            # Strip trailing slash from path if path != '/'
            path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

            # Reconstruct URL without fragment and tracking params
            canonical = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                "",
                new_query,
                ""  # drop fragment
            ))
            return canonical
        except Exception:
            return url.strip()
