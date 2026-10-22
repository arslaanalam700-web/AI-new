"""
Deduplication Engine: Identifies and clusters duplicate articles across multiple sources.
Supports exact URL matching, token Jaccard similarity, sequence matching, and entity containment.
"""

from typing import List, Set, Tuple, Dict, Any, Optional
import difflib
import re
from src.models import Article, StoryCluster


class DeduplicationEngine:
    """Detects and clusters duplicate stories across diverse sources."""

    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "over", "after",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "it", "its", "this", "that", "these", "those", "how", "what", "why", "when",
        "new", "says", "launches", "releases", "announces", "unveils", "introduces"
    }

    def __init__(
        self,
        similarity_threshold: float = 0.58,
        jaccard_weight: float = 0.45,
        sequence_weight: float = 0.55
    ):
        self.similarity_threshold = similarity_threshold
        self.jaccard_weight = jaccard_weight
        self.sequence_weight = sequence_weight

    @classmethod
    def tokenize(cls, text: str) -> Set[str]:
        """Convert text into normalized alphanumeric tokens without stop words (preserving 2-char tokens like o1, o3, ai)."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = {word for word in cleaned.split() if (len(word) >= 2 or word.isdigit()) and word not in cls.STOP_WORDS}
        return tokens

    @classmethod
    def normalize_for_comparison(cls, text: str) -> str:
        """Strip non-alphanumeric characters and lowercase."""
        return re.sub(r"[^\w\s]", "", text.lower()).strip()

    def calculate_similarity(self, title_a: str, title_b: str) -> float:
        """
        Calculate a composite similarity score between two article titles.
        Combines SequenceMatcher ratio and Token Jaccard index with containment bonus.
        """
        norm_a = self.normalize_for_comparison(title_a)
        norm_b = self.normalize_for_comparison(title_b)

        if not norm_a or not norm_b:
            return 0.0

        if norm_a == norm_b:
            return 1.0

        # Sequence Matcher
        seq_ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

        # Token Jaccard
        tokens_a = self.tokenize(title_a)
        tokens_b = self.tokenize(title_b)

        if not tokens_a or not tokens_b:
            return seq_ratio

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union) if union else 0.0

        # Token containment check (e.g. short title contained in longer title, or high entity overlap)
        containment_a = len(intersection) / len(tokens_a)
        containment_b = len(intersection) / len(tokens_b)
        max_containment = max(containment_a, containment_b)

        composite = (self.sequence_weight * seq_ratio) + (self.jaccard_weight * jaccard)

        # If key terms have >= 60% containment and sequence ratio >= 0.45,
        # or if 3+ informative tokens match and sequence ratio is >= 0.50, boost
        if (max_containment >= 0.60 and seq_ratio >= 0.45) or (len(intersection) >= 3 and seq_ratio >= 0.50):
            composite = max(composite, 0.70)

        return min(composite, 1.0)

    def is_duplicate(self, art1: Article, art2: Article) -> bool:
        """Determine if two articles refer to the same event or story."""
        # 1. Exact canonical URL match
        if art1.canonical_url and art2.canonical_url:
            if art1.canonical_url.lower() == art2.canonical_url.lower():
                return True

        # 2. ArXiv ID match in URL
        arxiv_match_1 = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", art1.canonical_url)
        arxiv_match_2 = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", art2.canonical_url)
        if arxiv_match_1 and arxiv_match_2 and arxiv_match_1.group(1) == arxiv_match_2.group(1):
            return True

        # 3. Fuzzy title similarity
        similarity = self.calculate_similarity(art1.title, art2.title)
        return similarity >= self.similarity_threshold

    def _select_canonical_article(self, cluster_articles: List[Article]) -> Article:
        """
        Select the best canonical representation from a cluster of duplicates.
        Prefers articles with longer informative summaries and higher engagement.
        """
        def article_quality(a: Article) -> float:
            score = 0.0
            # Informative summary length bonus
            summary_len = len(a.summary)
            score += min(summary_len / 200.0, 5.0)
            # Engagement bonus
            score += min(a.engagement_score / 50.0, 3.0)
            # Prefer research/reputable sources
            if a.source_id in {"arxiv_ai", "arxiv_cl", "hf_daily_papers", "techcrunch_ai", "mit_tech_review"}:
                score += 1.5
            return score

        return max(cluster_articles, key=article_quality)

    def cluster_articles(self, articles: List[Article]) -> List[StoryCluster]:
        """
        Group a list of articles into deduplicated StoryClusters.
        """
        if not articles:
            return []

        clusters: List[StoryCluster] = []

        for article in articles:
            matched_cluster: Optional[StoryCluster] = None

            for cluster in clusters:
                # Check against the canonical article of the cluster
                if self.is_duplicate(article, cluster.canonical_article):
                    matched_cluster = cluster
                    break
                # Or check against any article in the cluster if canonical didn't trigger
                for existing_art in cluster.articles:
                    if self.is_duplicate(article, existing_art):
                        matched_cluster = cluster
                        break
                if matched_cluster:
                    break

            if matched_cluster:
                # Add article to existing cluster
                matched_cluster.articles.append(article)
                if article.source_name not in matched_cluster.sources:
                    matched_cluster.sources.append(article.source_name)
                # Re-evaluate canonical article
                matched_cluster.canonical_article = self._select_canonical_article(matched_cluster.articles)
            else:
                # Create a new cluster
                new_cluster = StoryCluster(
                    id=f"cluster_{article.id}",
                    canonical_article=article,
                    articles=[article],
                    sources=[article.source_name],
                    category=article.category
                )
                clusters.append(new_cluster)

        return clusters
