"""
Summarizer and Synthesis Engine: Generates key takeaways, 'Why It Matters' insights,
entity detection, and executive briefings.
Supports both zero-dependency heuristic NLP and optional LLM synthesis (Gemini/OpenAI).
"""

from typing import List, Dict, Any, Optional
import os
import re
from src.models import StoryCluster


class SummarizerEngine:
    """Generates analytical summaries, entities, and why-it-matters insights."""

    KNOWN_ENTITIES = {
        "Companies": [
            "OpenAI", "Google", "DeepMind", "Anthropic", "Meta", "Microsoft",
            "NVIDIA", "Apple", "Amazon", "Mistral", "Hugging Face", "xAI",
            "Perplexity", "Midjourney", "Scale AI", "Databricks", "Snowflake"
        ],
        "Models & Tech": [
            "GPT-4o", "GPT-5", "o1", "o3", "Claude 3.5", "Claude 3", "Gemini 1.5",
            "Gemini 2", "Llama 3", "Llama 3.1", "DeepSeek", "Mistral", "Sora",
            "Flux", "Stable Diffusion", "Whisper", "Chinchilla", "Transformers",
            "CUDA", "Blackwell", "H100", "B200"
        ],
        "Domains": [
            "Reasoning Models", "Autonomous Agents", "Robotics", "Open Weights",
            "Multimodal AI", "AI Safety", "Copyright", "Antitrust", "Synthetic Data"
        ]
    }

    IMPACT_INDICATORS = [
        "represents a major shift",
        "lowers the barrier for developers",
        "accelerates the transition toward autonomous agents",
        "highlights escalating competition in frontier model reasoning",
        "signals intensifying regulatory scrutiny over tech monopolies",
        "sets a new efficiency benchmark for open source deployments",
        "could disrupt traditional enterprise software workflows",
        "underlines the growing compute demands of next-generation training"
    ]

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self.gemini_client = None
        self._init_llm_if_available()

    def _init_llm_if_available(self) -> None:
        """Attempt to initialize Gemini client if API key exists."""
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key and self.use_llm:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=api_key)
            except Exception:
                self.gemini_client = None

    def extract_entities(self, text: str) -> List[str]:
        """Detect known tech companies, models, and domains mentioned in text."""
        detected = []
        lower_text = text.lower()
        for category, entities in self.KNOWN_ENTITIES.items():
            for entity in entities:
                pattern = r"\b" + re.escape(entity.lower()) + r"\b"
                if re.search(pattern, lower_text):
                    if entity not in detected:
                        detected.append(entity)
        return detected[:6]

    def generate_heuristic_takeaway(self, cluster: StoryCluster) -> str:
        """Synthesize a sharp, context-aware 'Why It Matters' insight using heuristic salience."""
        full_text = f"{cluster.title}. {cluster.summary}"
        entities = self.extract_entities(full_text)
        cluster.key_entities = entities

        # Split summary into distinct sentences
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", cluster.summary) if len(s.strip()) > 25]

        # Look for quantitative or impact sentences
        metric_sentence = None
        for s in sentences:
            if re.search(r"(\d+%|\$\d+|\bbenchmarks?\b|\boutperforms?\b|\bfaster\b|\bcheaper\b|\bmillion\b|\bbillion\b)", s, re.IGNORECASE):
                metric_sentence = s
                break

        entity_phrase = f" for {', '.join(entities[:2])}" if entities else ""

        # Category specific template
        if cluster.category == "research":
            if metric_sentence:
                takeaway = f"Advances theoretical capabilities{entity_phrase}: {metric_sentence.rstrip('.')}."
            else:
                takeaway = f"Expands the frontier of AI capabilities, demonstrating novel architectural and empirical findings{entity_phrase}."
        elif cluster.category == "dev_tools":
            if metric_sentence:
                takeaway = f"Empowers developers with improved tooling{entity_phrase}: {metric_sentence.rstrip('.')}."
            else:
                takeaway = f"Streamlines developer productivity and open-source infrastructure{entity_phrase}."
        elif cluster.category == "policy":
            takeaway = f"Signals pivotal legal and regulatory precedents that will shape AI deployment and compliance boundaries."
        elif cluster.category == "industry":
            if metric_sentence:
                takeaway = f"Key commercial development{entity_phrase}: {metric_sentence.rstrip('.')}."
            else:
                takeaway = f"Reflects strategic capital allocation and enterprise adoption momentum across the tech ecosystem."
        else:
            if metric_sentence:
                takeaway = f"Key development: {metric_sentence.rstrip('.')}."
            else:
                takeaway = f"Important signal reflecting current momentum in the broader artificial intelligence landscape."

        return takeaway

    def synthesize_executive_summary(
        self,
        top_stories: List[StoryCluster],
        date_str: str,
        total_ingested: int
    ) -> str:
        """Generate a high-level executive briefing paragraph covering the day's dominant themes."""
        if not top_stories:
            return f"AI Daily Brief for {date_str}: No breaking developments recorded in the monitoring window."

        # Collect top entities and themes
        all_entities = []
        for s in top_stories:
            all_entities.extend(s.key_entities)

        # Deduplicate entities preserving order
        unique_entities = []
        for e in all_entities:
            if e not in unique_entities:
                unique_entities.append(e)

        top_story = top_stories[0]
        entity_summary = f", driven by moves from {', '.join(unique_entities[:3])}" if unique_entities else ""

        summary_para = (
            f"Today's AI brief highlights pivotal developments across {len(top_stories)} leading stories{entity_summary}. "
            f"Headlining today: **{top_story.title}**, leading coverage across independent outlets. "
            f"Key themes today span breakthroughs in model capabilities, commercial acceleration, and ongoing developer ecosystem expansion."
        )
        return summary_para

    def enrich_clusters(self, clusters: List[StoryCluster]) -> None:
        """Enrich all story clusters with 'Why It Matters' insights and key entities."""
        for cluster in clusters:
            if not cluster.why_it_matters:
                cluster.why_it_matters = self.generate_heuristic_takeaway(cluster)
            if not cluster.key_entities:
                cluster.key_entities = self.extract_entities(f"{cluster.title} {cluster.summary}")
