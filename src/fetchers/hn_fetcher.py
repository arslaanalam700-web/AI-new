"""
Fetcher for Hacker News stories using the Algolia Search API.
"""

from typing import List
from datetime import datetime, timezone
import requests

from src.models import Article, SourceConfig
from src.fetchers.base import BaseFetcher


class HackerNewsFetcher(BaseFetcher):
    """Fetches trending AI stories and discussions from Hacker News."""

    def __init__(self, config: SourceConfig, timeout: int = 12, hits_per_page: int = 30):
        super().__init__(config, timeout)
        self.hits_per_page = hits_per_page
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Brief/1.0"
        })

    def fetch(self, cutoff_time: datetime) -> List[Article]:
        articles: List[Article] = []
        try:
            cutoff_timestamp = int(cutoff_time.timestamp())
            params = {
                "tags": "story",
                "query": "AI OR LLM OR GPT OR OpenAI OR Anthropic OR Claude OR Gemini OR DeepMind",
                "numericFilters": f"created_at_i>{cutoff_timestamp}",
                "hitsPerPage": self.hits_per_page
            }

            resp = self.session.get(self.config.url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            data = resp.json()
            hits = data.get("hits", [])

            for hit in hits:
                title = self.clean_title(hit.get("title", ""))
                if not title:
                    continue

                points = hit.get("points") or 0
                num_comments = hit.get("num_comments") or 0
                object_id = hit.get("objectID")
                hn_item_url = f"https://news.ycombinator.com/item?id={object_id}"

                # Prefer original article URL if present, otherwise HN item URL
                target_url = hit.get("url") or hn_item_url
                canonical_link = self.canonicalize_url(target_url)

                created_at_i = hit.get("created_at_i")
                if created_at_i:
                    pub_date = datetime.fromtimestamp(created_at_i, tz=timezone.utc)
                else:
                    pub_date = datetime.now(timezone.utc)

                story_text = hit.get("story_text") or ""
                summary = self.clean_text(story_text)
                if not summary:
                    summary = f"Community discussion on Hacker News with {points} points and {num_comments} comments."

                author = hit.get("author")

                art_id = Article.create_id(title, canonical_link)
                article = Article(
                    id=art_id,
                    title=title,
                    url=target_url,
                    canonical_url=canonical_link,
                    source_id=self.config.id,
                    source_name=self.config.name,
                    published_at=pub_date,
                    summary=summary[:1200],
                    category=self.config.category,
                    author=author,
                    tags=["hackernews", "community", "discussion"],
                    engagement_score=float(points),
                    comment_count=num_comments,
                    raw_content=f"Points: {points}, Comments: {num_comments}. HN URL: {hn_item_url}"
                )
                articles.append(article)

        except Exception:
            pass

        return articles
