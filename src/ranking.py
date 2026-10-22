"""
Ranking Engine: Evaluates and scores story clusters using a multi-factor weighting model.
Classifies stories into structured editorial categories.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import math
import re
import yaml

from src.models import StoryCluster


class RankingEngine:
    """Scores, ranks, and classifies StoryClusters."""

    # High-impact keywords that increase editorial relevance
    HIGH_IMPACT_KEYWORDS = {
        "breakthrough", "state of the art", "sota", "reasoning", "benchmark",
        "frontier", "agent", "agents", "autonomous", "humanoid", "robotics",
        "open source", "weights", "inference", "supercomputer", "chips", "gpu",
        "funding", "billion", "acquisition", "antitrust", "safety", "alignment",
        "o1", "o3", "gpt-4", "gpt-5", "claude", "gemini", "llama", "deepseek", "mistral"
    }

    CATEGORY_KEYWORDS = {
        "research": {
            "arxiv", "paper", "architecture", "dataset", "neural", "attention",
            "transformer", "training", "algorithm", "empirical", "convergence",
            "diffusion", "latent", "loss", "pretraining", "fine-tuning", "parameter"
        },
        "dev_tools": {
            "github", "open source", "repo", "library", "sdk", "api", "framework",
            "developer", "tool", "cli", "python", "rust", "cuda", "ollama", "vllm",
            "llama.cpp", "weights", "weights release", "huggingface"
        },
        "policy": {
            "policy", "regulation", "law", "copyright", "lawsuit", "court", "ftc",
            "sec", "eu ai act", "governance", "safety", "ethics", "deepfake",
            "surveillance", "congress", "white house", "national security", "ban"
        },
        "industry": {
            "startup", "funding", "raised", "venture", "valuation", "acquisition",
            "microsoft", "google", "meta", "openai", "anthropic", "apple", "nvidia",
            "amazon", "partnership", "launch", "enterprise", "market", "revenue"
        }
    }

    def __init__(
        self,
        settings_path: str = "config/settings.yaml",
        sources_config_path: str = "config/sources.yaml"
    ):
        self.settings_path = settings_path
        self.sources_config_path = sources_config_path
        self.weights = {
            "base_relevance": 2.0,
            "recency": 2.5,
            "source_weight": 1.5,
            "multi_coverage_bonus": 3.0,
            "virality": 1.5,
        }
        self.recency_decay_hours = 36.0
        self.source_weights: Dict[str, float] = {}

        self._load_configs()

    def _load_configs(self) -> None:
        """Load ranking weights and source weights from configuration files."""
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f) or {}
                rank_cfg = settings.get("ranking", {})
                self.weights.update(rank_cfg.get("weights", {}))
                self.recency_decay_hours = float(rank_cfg.get("recency_decay_hours", 36.0))
        except Exception:
            pass

        try:
            with open(self.sources_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for src in data.get("sources", []):
                    self.source_weights[src.get("name", "")] = float(src.get("weight", 1.0))
        except Exception:
            pass

    def calculate_recency_score(self, pub_date: datetime, now: datetime) -> float:
        """Calculate exponential decay score based on hours elapsed."""
        age_hours = max((now - pub_date).total_seconds() / 3600.0, 0.0)
        # Half-life exponential decay: e^(-age / decay_scale)
        return math.exp(-age_hours / self.recency_decay_hours)

    def calculate_relevance_score(self, title: str, summary: str) -> float:
        """Calculate editorial domain relevance based on high-impact terminology."""
        text = f"{title.lower()} {summary.lower()}"
        score = 1.0
        for kw in self.HIGH_IMPACT_KEYWORDS:
            if kw in text:
                score += 0.4
        return min(score, 3.5)

    def calculate_virality_score(self, cluster: StoryCluster) -> float:
        """Compute virality signal from points/upvotes and comment counts across all articles."""
        total_engagement = sum(a.engagement_score for a in cluster.articles)
        total_comments = sum(a.comment_count for a in cluster.articles)
        combined = total_engagement + (total_comments * 1.5)
        if combined <= 0:
            return 0.0
        return math.log2(1.0 + combined)

    def score_cluster(self, cluster: StoryCluster, now: datetime) -> float:
        """
        Compute the final composite ranking score for a story cluster.
        """
        # 1. Base relevance
        rel_score = self.calculate_relevance_score(cluster.title, cluster.summary)

        # 2. Recency
        recency_factor = self.calculate_recency_score(cluster.published_at, now)

        # 3. Source weight (average of participating sources)
        src_weights = [self.source_weights.get(s, 1.0) for s in cluster.sources]
        avg_source_weight = sum(src_weights) / len(src_weights) if src_weights else 1.0

        # 4. Multi-source consensus multiplier
        # 1 source = 1.0x, 2 sources = 1.35x, 3+ sources = 1.75x
        if cluster.source_count >= 3:
            consensus_multiplier = 1.75
        elif cluster.source_count == 2:
            consensus_multiplier = 1.35
        else:
            consensus_multiplier = 1.0

        # 5. Virality
        virality_score = self.calculate_virality_score(cluster)

        # Composite computation
        base_component = (rel_score * self.weights["base_relevance"]) + (virality_score * self.weights["virality"])
        final_score = base_component * (0.3 + 0.7 * recency_factor) * avg_source_weight * consensus_multiplier

        # Mark breaking news if multi-source or high viral engagement
        if cluster.source_count >= 2 or virality_score > 6.0:
            cluster.is_breaking = True

        cluster.score = round(final_score, 2)
        return cluster.score

    def classify_category(self, cluster: StoryCluster) -> str:
        """Classify a story cluster into its primary editorial domain."""
        # If the canonical article already has research category and is an academic paper
        if cluster.canonical_article.source_id in {"arxiv_ai", "arxiv_cl", "hf_daily_papers"}:
            return "research"

        text = f"{cluster.title.lower()} {cluster.summary.lower()}"
        scores: Dict[str, int] = {cat: 0 for cat in self.CATEGORY_KEYWORDS}

        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[cat] += 1

        best_cat = max(scores, key=scores.get)
        if scores[best_cat] > 0:
            return best_cat

        # Default fallback to the canonical article's source category
        return cluster.canonical_article.category or "industry"

    def rank_and_classify(
        self,
        clusters: List[StoryCluster],
        now: Optional[datetime] = None
    ) -> List[StoryCluster]:
        """Score, classify, and sort all story clusters in descending order."""
        if not clusters:
            return []

        if now is None:
            now = datetime.now(timezone.utc)

        for cluster in clusters:
            self.score_cluster(cluster, now)
            cluster.category = self.classify_category(cluster)

        # Sort descending by score
        ranked = sorted(clusters, key=lambda c: c.score, reverse=True)
        return ranked
