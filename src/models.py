"""
Data models for the AI News Brief Generator.
Defines Article, StoryCluster, DailyBrief, and SourceConfig.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import hashlib
import json


@dataclass
class SourceConfig:
    """Configuration for an individual news or research source."""
    id: str
    name: str
    type: str  # 'rss', 'api_hn', 'api_hf'
    url: str
    category: str
    weight: float = 1.0
    enabled: bool = True
    requires_ai_filter: bool = False
    description: str = ""


@dataclass
class Article:
    """An individual article fetched from a source."""
    id: str
    title: str
    url: str
    canonical_url: str
    source_id: str
    source_name: str
    published_at: datetime
    summary: str
    category: str = "general"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    engagement_score: float = 0.0  # HN points, HF upvotes, etc.
    comment_count: int = 0
    raw_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "category": self.category,
            "author": self.author,
            "tags": self.tags,
            "engagement_score": self.engagement_score,
            "comment_count": self.comment_count,
        }

    @classmethod
    def create_id(cls, title: str, url: str) -> str:
        """Create a deterministic unique hash for an article."""
        raw = f"{title.strip().lower()}|{url.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class StoryCluster:
    """A cluster of one or more duplicate or corroborating articles covering the same event."""
    id: str
    canonical_article: Article
    articles: List[Article] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    score: float = 0.0
    category: str = "general"
    why_it_matters: str = ""
    key_entities: List[str] = field(default_factory=list)
    is_breaking: bool = False

    @property
    def title(self) -> str:
        return self.canonical_article.title

    @property
    def url(self) -> str:
        return self.canonical_article.url

    @property
    def summary(self) -> str:
        return self.canonical_article.summary

    @property
    def published_at(self) -> datetime:
        return self.canonical_article.published_at

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "category": self.category,
            "score": round(self.score, 2),
            "source_count": self.source_count,
            "sources": self.sources,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "key_entities": self.key_entities,
            "is_breaking": self.is_breaking,
            "canonical_article": self.canonical_article.to_dict(),
            "related_articles": [a.to_dict() for a in self.articles if a.id != self.canonical_article.id],
        }


@dataclass
class DailyBrief:
    """The synthesized Daily AI Brief containing ranked, categorized, deduplicated stories."""
    id: str
    generated_at: datetime
    date_str: str
    time_window_hours: int
    total_articles_ingested: int
    total_duplicates_merged: int
    total_stories_selected: int
    top_stories: List[StoryCluster]
    sections: Dict[str, List[StoryCluster]]
    sources_included: List[str]
    executive_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "generated_at": self.generated_at.isoformat(),
            "date": self.date_str,
            "time_window_hours": self.time_window_hours,
            "stats": {
                "total_articles_ingested": self.total_articles_ingested,
                "total_duplicates_merged": self.total_duplicates_merged,
                "total_stories_selected": self.total_stories_selected,
                "sources_count": len(self.sources_included),
            },
            "sources_included": self.sources_included,
            "executive_summary": self.executive_summary,
            "top_stories": [s.to_dict() for s in self.top_stories],
            "sections": {
                cat: [s.to_dict() for s in stories]
                for cat, stories in self.sections.items()
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
