"""
Unit tests for the Ranking Engine.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.models import Article, StoryCluster
from src.ranking import RankingEngine


@pytest.fixture
def ranking_engine():
    return RankingEngine()


def create_cluster(
    id: str,
    title: str,
    hours_ago: float,
    sources: list,
    engagement: float = 0.0,
    category: str = "industry"
) -> StoryCluster:
    pub_time = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    art = Article(
        id=id,
        title=title,
        url=f"https://example.com/{id}",
        canonical_url=f"https://example.com/{id}",
        source_id="test",
        source_name=sources[0],
        published_at=pub_time,
        summary=f"Detailed analysis on {title}.",
        category=category,
        engagement_score=engagement
    )
    return StoryCluster(
        id=f"c_{id}",
        canonical_article=art,
        articles=[art],
        sources=sources,
        category=category
    )


def test_recency_decay(ranking_engine):
    now = datetime.now(timezone.utc)
    recent = create_cluster("1", "Recent AI Breakthrough in Robotics", hours_ago=2.0, sources=["TechCrunch"])
    old = create_cluster("2", "Older AI Breakthrough in Robotics", hours_ago=36.0, sources=["TechCrunch"])

    score_recent = ranking_engine.score_cluster(recent, now)
    score_old = ranking_engine.score_cluster(old, now)

    assert score_recent > score_old


def test_multi_source_consensus_bonus(ranking_engine):
    now = datetime.now(timezone.utc)
    single_source = create_cluster(
        "1",
        "OpenAI Launches Next Generation Model",
        hours_ago=4.0,
        sources=["TechCrunch"]
    )
    multi_source = create_cluster(
        "2",
        "OpenAI Launches Next Generation Model",
        hours_ago=4.0,
        sources=["TechCrunch", "The Verge", "Hacker News"]
    )

    score_single = ranking_engine.score_cluster(single_source, now)
    score_multi = ranking_engine.score_cluster(multi_source, now)

    assert score_multi > score_single
    assert multi_source.is_breaking is True


def test_virality_score_boost(ranking_engine):
    now = datetime.now(timezone.utc)
    normal = create_cluster("1", "Developer tools release", hours_ago=5.0, sources=["GitHub"], engagement=0)
    viral = create_cluster("2", "Developer tools release", hours_ago=5.0, sources=["GitHub"], engagement=350)

    score_normal = ranking_engine.score_cluster(normal, now)
    score_viral = ranking_engine.score_cluster(viral, now)

    assert score_viral > score_normal


def test_category_classification(ranking_engine):
    research_cluster = create_cluster(
        "1",
        "Transformer Attention Latent Diffusion Architecture Empirical Convergence",
        hours_ago=2.0,
        sources=["ArXiv"]
    )
    dev_cluster = create_cluster(
        "2",
        "GitHub Open Source CLI Framework for Local LLMs Ollama vLLM",
        hours_ago=2.0,
        sources=["Hacker News"]
    )
    policy_cluster = create_cluster(
        "3",
        "EU AI Act Compliance and Federal Lawsuit over AI Copyright Training",
        hours_ago=2.0,
        sources=["Wired"]
    )

    assert ranking_engine.classify_category(research_cluster) == "research"
    assert ranking_engine.classify_category(dev_cluster) == "dev_tools"
    assert ranking_engine.classify_category(policy_cluster) == "policy"
