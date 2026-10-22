"""
Ingestion Manager: coordinates concurrent fetching across all news and research sources.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import re

from src.models import Article, SourceConfig
from src.fetchers.base import BaseFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.hn_fetcher import HackerNewsFetcher
from src.fetchers.hf_fetcher import HuggingFacePapersFetcher


class IngestionManager:
    """Manages multi-source fetching, filtering, and concurrency."""

    def __init__(
        self,
        sources_config_path: str = "config/sources.yaml",
        settings_path: str = "config/settings.yaml",
        max_workers: int = 8
    ):
        self.sources_config_path = sources_config_path
        self.settings_path = settings_path
        self.max_workers = max_workers
        self.sources: List[SourceConfig] = []
        self.ai_keywords: List[str] = []
        self.keyword_regex: Optional[re.Pattern] = None

        self._load_configs()

    def _load_configs(self) -> None:
        """Load source definitions and ingestion settings."""
        # Load sources
        try:
            with open(self.sources_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for src in data.get("sources", []):
                    self.sources.append(SourceConfig(**src))
        except Exception:
            self.sources = []

        # Load settings
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f) or {}
                ingest_settings = settings.get("ingestion", {})
                self.ai_keywords = ingest_settings.get("ai_keywords", [])
        except Exception:
            self.ai_keywords = ["ai", "artificial intelligence", "llm", "gpt", "openai", "claude", "gemini"]

        # Compile regex with word boundaries
        if self.ai_keywords:
            escaped = [re.escape(k) for k in self.ai_keywords]
            pattern = r"\b(" + "|".join(escaped) + r")\b"
            self.keyword_regex = re.compile(pattern, re.IGNORECASE)

    def is_ai_relevant(self, article: Article) -> bool:
        """Check if an article matches AI/tech domain criteria."""
        if not self.keyword_regex:
            return True

        content_to_check = f"{article.title} {article.summary} {' '.join(article.tags)}"
        return bool(self.keyword_regex.search(content_to_check))

    def _get_fetcher(self, source: SourceConfig) -> BaseFetcher:
        """Instantiate the matching fetcher for a given source config."""
        if source.type == "api_hn":
            return HackerNewsFetcher(source)
        elif source.type == "api_hf":
            return HuggingFacePapersFetcher(source)
        else:
            return RSSFetcher(source)

    def fetch_all(
        self,
        lookback_hours: int = 24,
        source_ids: Optional[List[str]] = None,
        custom_sources: Optional[List[SourceConfig]] = None
    ) -> List[Article]:
        """
        Concurrently fetch articles across all active sources within the lookback window.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        # Determine active sources
        target_sources = list(self.sources)
        if custom_sources:
            target_sources.extend(custom_sources)

        if source_ids:
            target_sources = [s for s in target_sources if s.id in source_ids and s.enabled]
        else:
            target_sources = [s for s in target_sources if s.enabled]

        all_articles: List[Article] = []

        def _fetch_worker(src: SourceConfig) -> List[Article]:
            try:
                fetcher = self._get_fetcher(src)
                items = fetcher.fetch(cutoff_time)
                # Apply AI relevance filtering if source is a general tech outlet
                if src.requires_ai_filter:
                    items = [a for a in items if self.is_ai_relevant(a)]
                return items
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(target_sources) or 1)) as executor:
            future_to_source = {executor.submit(_fetch_worker, s): s for s in target_sources}
            for future in as_completed(future_to_source):
                try:
                    res = future.result()
                    if res:
                        all_articles.extend(res)
                except Exception:
                    pass

        return all_articles
