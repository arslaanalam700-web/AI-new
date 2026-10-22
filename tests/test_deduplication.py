"""
Unit tests for the Deduplication Engine.
"""

import pytest
from datetime import datetime, timezone
from src.models import Article
from src.deduplication import DeduplicationEngine
from src.fetchers.base import BaseFetcher


@pytest.fixture
def dedup_engine():
    return DeduplicationEngine(similarity_threshold=0.58)


def create_sample_article(id: str, title: str, url: str, source: str = "Test Source", summary: str = "") -> Article:
    canonical = BaseFetcher.canonicalize_url(url)
    return Article(
        id=id,
        title=title,
        url=url,
        canonical_url=canonical,
        source_id="test_src",
        source_name=source,
        published_at=datetime.now(timezone.utc),
        summary=summary or f"Summary for {title}"
    )


def test_url_canonicalization():
    url1 = "https://techcrunch.com/2026/10/22/openai-o3/?utm_source=twitter&utm_medium=social"
    url2 = "https://techcrunch.com/2026/10/22/openai-o3"
    url3 = "https://techcrunch.com/2026/10/22/openai-o3/#comments"

    c1 = BaseFetcher.canonicalize_url(url1)
    c2 = BaseFetcher.canonicalize_url(url2)
    c3 = BaseFetcher.canonicalize_url(url3)

    assert c1 == c2
    assert c2 == c3
    assert "utm_source" not in c1
    assert "#comments" not in c3


def test_exact_url_duplicate(dedup_engine):
    art1 = create_sample_article("1", "OpenAI Releases New Model", "https://news.com/openai?utm_source=rss", "News Outlet A")
    art2 = create_sample_article("2", "OpenAI Releases New Model Announced", "https://news.com/openai?ref=hn", "News Outlet B")

    assert dedup_engine.is_duplicate(art1, art2) is True


def test_fuzzy_title_duplicate(dedup_engine):
    art1 = create_sample_article(
        "1",
        "Anthropic Launches Claude 3.5 Sonnet With Upgraded Vision Capabilities",
        "https://theverge.com/claude-35",
        "The Verge"
    )
    art2 = create_sample_article(
        "2",
        "Anthropic releases Claude 3.5 Sonnet featuring enhanced computer vision",
        "https://techcrunch.com/claude-sonnet",
        "TechCrunch"
    )

    sim = dedup_engine.calculate_similarity(art1.title, art2.title)
    assert sim >= 0.58
    assert dedup_engine.is_duplicate(art1, art2) is True


def test_distinct_stories_not_duplicate(dedup_engine):
    art1 = create_sample_article(
        "1",
        "Nvidia Unveils Blackwell Ultra B200 AI GPUs For Hyperscalers",
        "https://nvidia.com/gpu",
        "Nvidia Blog"
    )
    art2 = create_sample_article(
        "2",
        "Google DeepMind Publishes Groundbreaking AlphaFold 3 Biology Paper",
        "https://deepmind.google/alphafold3",
        "DeepMind"
    )

    sim = dedup_engine.calculate_similarity(art1.title, art2.title)
    assert sim < 0.40
    assert dedup_engine.is_duplicate(art1, art2) is False


def test_clustering_multi_source(dedup_engine):
    art1 = create_sample_article(
        "1",
        "OpenAI Announces SearchGPT AI Search Prototype",
        "https://theverge.com/searchgpt",
        "The Verge",
        summary="Short summary."
    )
    art2 = create_sample_article(
        "2",
        "OpenAI launches SearchGPT prototype to take on Google",
        "https://techcrunch.com/searchgpt",
        "TechCrunch",
        summary="A much longer and comprehensive breakdown of OpenAI's new SearchGPT prototype."
    )
    art3 = create_sample_article(
        "3",
        "DeepSeek releases new open weights reasoning architecture",
        "https://github.com/deepseek-ai",
        "GitHub"
    )

    clusters = dedup_engine.cluster_articles([art1, art2, art3])

    # Should cluster the 2 SearchGPT stories into 1, and DeepSeek into another -> total 2 clusters
    assert len(clusters) == 2

    # Find the SearchGPT cluster
    search_cluster = next(c for c in clusters if "searchgpt" in c.title.lower())
    assert search_cluster.source_count == 2
    assert "The Verge" in search_cluster.sources
    assert "TechCrunch" in search_cluster.sources
    # Canonical article should prefer the longer summary (TechCrunch)
    assert search_cluster.canonical_article.source_name == "TechCrunch"
