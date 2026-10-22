"""
Unit and integration tests for the BriefWorkflow and generators.
"""

import pytest
import os
import json
from datetime import datetime, timezone, timedelta
from src.models import Article, DailyBrief
from src.workflow import BriefWorkflow
from src.generator import BriefGenerator


@pytest.fixture
def mock_articles():
    now = datetime.now(timezone.utc)
    return [
        Article(
            id="art1",
            title="OpenAI releases o3 reasoning model with breakthrough coding benchmarks",
            url="https://techcrunch.com/o3",
            canonical_url="https://techcrunch.com/o3",
            source_id="techcrunch_ai",
            source_name="TechCrunch AI",
            published_at=now - timedelta(hours=2),
            summary="OpenAI announced o3, demonstrating unprecedented scores on coding benchmarks.",
            category="industry"
        ),
        Article(
            id="art2",
            title="OpenAI unveils o3 with new high scores on coding benchmarks",
            url="https://theverge.com/o3",
            canonical_url="https://theverge.com/o3",
            source_id="the_verge",
            source_name="The Verge",
            published_at=now - timedelta(hours=2),
            summary="The Verge covers OpenAI's new o3 reasoning model release.",
            category="industry"
        ),
        Article(
            id="art3",
            title="Periodic and Channel-Aligned Encoding of Four-Bit Recurrent States",
            url="https://arxiv.org/abs/2502.12345",
            canonical_url="https://arxiv.org/abs/2502.12345",
            source_id="arxiv_ai",
            source_name="ArXiv cs.AI",
            published_at=now - timedelta(hours=5),
            summary="This paper introduces a novel compression scheme for recurrent transformer states.",
            category="research"
        ),
        Article(
            id="art4",
            title="EU AI Act enters enforcement phase for general purpose models",
            url="https://technologyreview.com/eu-ai-act",
            canonical_url="https://technologyreview.com/eu-ai-act",
            source_id="mit_tech_review",
            source_name="MIT Tech Review",
            published_at=now - timedelta(hours=8),
            summary="Regulatory agencies in Europe have begun enforcing compliance guidelines.",
            category="policy"
        )
    ]


def test_workflow_dedup_and_generation(monkeypatch, mock_articles, tmp_path):
    workflow = BriefWorkflow()

    # Mock the fetcher to return our controlled mock articles
    monkeypatch.setattr(workflow.ingestion, "fetch_all", lambda **kwargs: mock_articles)

    brief = workflow.run(lookback_hours=24, top_n=2)

    # 4 articles with 2 duplicates -> should have 3 unique clusters
    assert brief.total_articles_ingested == 4
    assert brief.total_duplicates_merged == 1
    assert len(brief.top_stories) <= 2
    assert "OpenAI" in brief.executive_summary

    # Test Markdown generation
    md = BriefGenerator.to_markdown(brief)
    assert "# 🧠 AI Daily Intelligence Brief" in md
    assert "OpenAI" in md
    assert "Cross-reported by 2 sources" in md

    # Test HTML generation
    html = BriefGenerator.to_html(brief)
    assert "<!DOCTYPE html>" in html
    assert "AI Daily Intelligence Brief" in html
    assert "Top Headlines & Breaking News" in html

    # Test JSON generation
    data = json.loads(brief.to_json())
    assert data["stats"]["total_articles_ingested"] == 4
    assert data["stats"]["total_duplicates_merged"] == 1
    assert len(data["top_stories"]) > 0

    # Test saving files to disk
    out_dir = str(tmp_path / "briefs")
    saved = workflow.save_brief(brief, output_dir=out_dir)
    assert os.path.exists(saved["markdown"])
    assert os.path.exists(saved["html"])
    assert os.path.exists(saved["json"])
