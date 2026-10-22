"""
Fetchers package initialization.
"""

from src.fetchers.base import BaseFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.hf_fetcher import HuggingFacePapersFetcher

__all__ = ["BaseFetcher", "RSSFetcher", "HackerNewsFetcher", "HuggingFacePapersFetcher"]
