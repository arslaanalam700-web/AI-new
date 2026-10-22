"""
Fetcher for Hugging Face Daily Papers API.
"""

from typing import List
from datetime import datetime, timezone
import requests
from dateutil import parser as date_parser

from src.models import Article, SourceConfig
from src.fetchers.base import BaseFetcher


class HuggingFacePapersFetcher(BaseFetcher):
    """Fetches trending academic AI papers curated on Hugging Face Daily Papers."""

    def __init__(self, config: SourceConfig, timeout: int = 12, max_papers: int = 30):
        super().__init__(config, timeout)
        self.max_papers = max_papers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Brief/1.0"
        })

    def fetch(self, cutoff_time: datetime) -> List[Article]:
        articles: List[Article] = []
        try:
            resp = self.session.get(self.config.url, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            items = resp.json()[:self.max_papers]

            for item in items:
                paper = item.get("paper", {})
                raw_title = item.get("title") or paper.get("title", "")
                title = self.clean_title(raw_title)
                if not title:
                    continue

                paper_id = paper.get("id") or item.get("id")
                if paper_id:
                    # Canonical URL is standardized to arxiv link to allow cross-matching with arXiv RSS
                    canonical_url = f"https://arxiv.org/abs/{paper_id}"
                    hf_url = f"https://huggingface.co/papers/{paper_id}"
                else:
                    canonical_url = self.canonicalize_url(item.get("url", ""))
                    hf_url = canonical_url

                # Published date
                pub_str = item.get("publishedAt") or paper.get("publishedAt")
                if pub_str:
                    try:
                        pub_date = date_parser.parse(pub_str)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        else:
                            pub_date = pub_date.astimezone(timezone.utc)
                    except Exception:
                        pub_date = datetime.now(timezone.utc)
                else:
                    pub_date = datetime.now(timezone.utc)

                if pub_date < cutoff_time:
                    continue

                # Summary: prefer ai_summary if available
                summary_raw = paper.get("ai_summary") or item.get("summary") or paper.get("summary") or ""
                summary = self.clean_text(summary_raw)

                upvotes = paper.get("upvotes") or 0
                num_comments = item.get("numComments") or 0

                # Authors
                authors = paper.get("authors", [])
                author_names = [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")]
                author_str = ", ".join(author_names[:3]) if author_names else None

                # Keywords
                tags = paper.get("ai_keywords") or []
                if not isinstance(tags, list):
                    tags = []
                tags.extend(["research", "arxiv", "paper"])

                art_id = Article.create_id(title, canonical_url)
                article = Article(
                    id=art_id,
                    title=title,
                    url=hf_url,
                    canonical_url=canonical_url,
                    source_id=self.config.id,
                    source_name=self.config.name,
                    published_at=pub_date,
                    summary=summary[:1200],
                    category="research",
                    author=author_str,
                    tags=tags,
                    engagement_score=float(upvotes),
                    comment_count=num_comments,
                    raw_content=f"HF Upvotes: {upvotes}, Comments: {num_comments}"
                )
                articles.append(article)

        except Exception:
            pass

        return articles
