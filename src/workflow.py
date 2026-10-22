"""
Workflow Orchestrator for the AI News Brief Generator.
Integrates Ingestion, Deduplication, Ranking, Summarization, and Multi-Channel Generation.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os
import yaml
import requests

from src.models import Article, StoryCluster, DailyBrief, SourceConfig
from src.ingestion import IngestionManager
from src.deduplication import DeduplicationEngine
from src.ranking import RankingEngine
from src.summarizer import SummarizerEngine
from src.generator import BriefGenerator


class BriefWorkflow:
    """Executes the complete end-to-end AI news brief workflow."""

    def __init__(
        self,
        sources_config_path: str = "config/sources.yaml",
        settings_path: str = "config/settings.yaml"
    ):
        self.sources_config_path = sources_config_path
        self.settings_path = settings_path

        self.ingestion = IngestionManager(sources_config_path, settings_path)
        self.dedup = DeduplicationEngine()
        self.ranker = RankingEngine(settings_path, sources_config_path)
        self.summarizer = SummarizerEngine()

        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def run(
        self,
        lookback_hours: int = 24,
        source_ids: Optional[List[str]] = None,
        custom_sources: Optional[List[SourceConfig]] = None,
        top_n: int = 5,
        section_limit: int = 4,
        similarity_threshold: Optional[float] = None
    ) -> DailyBrief:
        """
        Execute the full pipeline:
        Fetch -> Deduplicate -> Rank & Classify -> Enrich & Summarize -> Assemble DailyBrief
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        if similarity_threshold is not None:
            self.dedup.similarity_threshold = similarity_threshold

        # Step 1: Ingestion
        articles = self.ingestion.fetch_all(
            lookback_hours=lookback_hours,
            source_ids=source_ids,
            custom_sources=custom_sources
        )
        total_ingested = len(articles)

        # Step 2: Deduplication
        clusters = self.dedup.cluster_articles(articles)
        total_duplicates = total_ingested - len(clusters)

        # Step 3: Ranking and Classification
        ranked_clusters = self.ranker.rank_and_classify(clusters, now=now)

        # Step 4: Summarization & Entity Extraction
        self.summarizer.enrich_clusters(ranked_clusters)

        # Step 5: Curate Sections
        # Top stories: highest scoring stories
        top_stories = ranked_clusters[:top_n]
        top_ids = {s.id for s in top_stories}

        # Segregate into categories for remaining stories
        sections: Dict[str, List[StoryCluster]] = {
            "research": [],
            "industry": [],
            "dev_tools": [],
            "policy": []
        }

        for story in ranked_clusters:
            # Don't repeat stories already featured in top headlines unless few stories exist
            if story.id in top_ids and len(ranked_clusters) > top_n:
                continue

            cat = story.category
            if cat in sections:
                if len(sections[cat]) < section_limit:
                    sections[cat].append(story)
            else:
                if len(sections["industry"]) < section_limit:
                    sections["industry"].append(story)

        # Unique active sources
        sources_included = list({a.source_name for a in articles})

        total_selected = len(top_stories) + sum(len(s) for s in sections.values())

        # Step 6: Executive Synthesis
        exec_summary = self.summarizer.synthesize_executive_summary(
            top_stories=top_stories,
            date_str=date_str,
            total_ingested=total_ingested
        )

        brief = DailyBrief(
            id=f"brief_{date_str}_{now.strftime('%H%M%S')}",
            generated_at=now,
            date_str=date_str,
            time_window_hours=lookback_hours,
            total_articles_ingested=total_ingested,
            total_duplicates_merged=total_duplicates,
            total_stories_selected=total_selected,
            top_stories=top_stories,
            sections=sections,
            sources_included=sources_included,
            executive_summary=exec_summary
        )

        return brief

    def save_brief(
        self,
        brief: DailyBrief,
        output_dir: str = "output/briefs",
        formats: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Save generated brief to files on disk in specified formats."""
        if formats is None:
            formats = ["markdown", "html", "json"]

        os.makedirs(output_dir, exist_ok=True)
        base_name = f"ai_news_brief_{brief.date_str}"
        saved_files = {}

        if "markdown" in formats:
            md_path = os.path.join(output_dir, f"{base_name}.md")
            md_content = BriefGenerator.to_markdown(brief)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            saved_files["markdown"] = md_path

        if "html" in formats:
            html_path = os.path.join(output_dir, f"{base_name}.html")
            html_content = BriefGenerator.to_html(brief)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            saved_files["html"] = html_path

        if "json" in formats:
            json_path = os.path.join(output_dir, f"{base_name}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(brief.to_json(indent=2))
            saved_files["json"] = json_path

        return saved_files

    def send_webhook(self, brief: DailyBrief, webhook_url: str) -> bool:
        """Send formatted Slack payload to an incoming webhook."""
        if not webhook_url:
            return False
        try:
            payload = BriefGenerator.to_slack_payload(brief)
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
