"""
Brief Generator: Formats the Daily AI Brief into multiple clean output channels:
Markdown, responsive HTML newsletter, JSON feed, and Webhook blocks.
"""

from typing import Dict, Any, List
import json
from datetime import datetime, timezone

from src.models import DailyBrief, StoryCluster


class BriefGenerator:
    """Generates formatted publication briefs from a DailyBrief object."""

    CATEGORY_METADATA = {
        "top_headlines": {
            "title": "🚀 Top Headlines & Breaking News",
            "desc": "The most impactful and widely covered stories in tech & AI today"
        },
        "research": {
            "title": "🔬 Frontier Research & Breakthroughs",
            "desc": "Novel architectures, benchmark discoveries, and academic advances"
        },
        "industry": {
            "title": "💼 Industry, Big Tech & Capital",
            "desc": "Funding rounds, acquisitions, corporate strategy, and commercial rollouts"
        },
        "dev_tools": {
            "title": "🛠️ Open Source, Models & Developer Tools",
            "desc": "New open weights, developer frameworks, inference engines, and tools"
        },
        "policy": {
            "title": "⚖️ Policy, Governance & Society",
            "desc": "Regulatory developments, AI safety, copyright, and global impact"
        }
    }

    @classmethod
    def to_markdown(cls, brief: DailyBrief) -> str:
        """Format the brief into clean, GitHub-flavored Markdown."""
        lines = []

        lines.append(f"# 🧠 AI Daily Intelligence Brief — {brief.date_str}")
        lines.append("")
        lines.append(
            f"> **Generated at:** {brief.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | "
            f"**Window:** Past {brief.time_window_hours} Hours | "
            f"**Sources Monitored:** {len(brief.sources_included)}"
        )
        lines.append("")

        # Metrics bar
        lines.append(
            f"**📊 Ingestion Metrics:** `{brief.total_articles_ingested} articles analyzed` • "
            f"`{brief.total_duplicates_merged} duplicates deduplicated` • "
            f"`{brief.total_stories_selected} stories curated`"
        )
        lines.append("")

        # Executive Summary
        if brief.executive_summary:
            lines.append("## 📌 Executive Summary")
            lines.append("")
            lines.append(brief.executive_summary)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Top Headlines Section
        if brief.top_stories:
            meta = cls.CATEGORY_METADATA["top_headlines"]
            lines.append(f"## {meta['title']}")
            lines.append(f"*{meta['desc']}*")
            lines.append("")

            for story in brief.top_stories:
                lines.extend(cls._format_story_markdown(story))
            lines.append("---")
            lines.append("")

        # Category Sections
        for cat_key, stories in brief.sections.items():
            if not stories:
                continue
            meta = cls.CATEGORY_METADATA.get(cat_key, {"title": f"📁 {cat_key.replace('_', ' ').title()}", "desc": ""})
            lines.append(f"## {meta['title']}")
            if meta["desc"]:
                lines.append(f"*{meta['desc']}*")
            lines.append("")

            for story in stories:
                lines.extend(cls._format_story_markdown(story))
            lines.append("---")
            lines.append("")

        # Sources Footer
        lines.append("### 📡 Sources Monitored Today")
        lines.append(", ".join(sorted(brief.sources_included)))
        lines.append("")
        lines.append("---")
        lines.append("*Automated AI News Brief Generator — Curated with multi-source consensus and algorithmic deduplication.*")

        return "\n".join(lines)

    @classmethod
    def _format_story_markdown(cls, story: StoryCluster) -> List[str]:
        lines = []
        source_badge = f"`{story.canonical_article.source_name}`"

        # Multi-source badge
        if story.source_count > 1:
            sources_str = ", ".join(story.sources)
            multi_badge = f" 🔥 **[Cross-reported by {story.source_count} sources: {sources_str}]**"
        else:
            multi_badge = ""

        # Engagement badge if present
        engagement_badge = ""
        if story.canonical_article.engagement_score > 0:
            engagement_badge = f" • ⭐ `{int(story.canonical_article.engagement_score)} pts`"

        lines.append(f"### [{story.title}]({story.url})")
        lines.append(f"{source_badge}{multi_badge}{engagement_badge} • 🕒 *{story.published_at.strftime('%H:%M UTC')}*")
        lines.append("")
        if story.summary:
            lines.append(f"{story.summary}")
            lines.append("")

        if story.why_it_matters:
            lines.append(f"💡 **Why It Matters:** {story.why_it_matters}")
            lines.append("")

        if story.key_entities:
            entity_tags = " ".join([f"`#{e}`" for e in story.key_entities])
            lines.append(f"🏷️ {entity_tags}")
            lines.append("")

        lines.append("")
        return lines

    @classmethod
    def to_html(cls, brief: DailyBrief) -> str:
        """Format the brief into a modern, responsive HTML newsletter."""
        top_stories_html = "".join([cls._format_story_html(s) for s in brief.top_stories])

        sections_html = ""
        for cat_key, stories in brief.sections.items():
            if not stories:
                continue
            meta = cls.CATEGORY_METADATA.get(cat_key, {"title": cat_key.replace('_', ' ').title(), "desc": ""})
            stories_markup = "".join([cls._format_story_html(s) for s in stories])
            sections_html += f"""
            <div class="category-section">
                <h2 class="category-title">{meta['title']}</h2>
                <p class="category-desc">{meta['desc']}</p>
                {stories_markup}
            </div>
            """

        sources_chips = "".join([f'<span class="source-chip">{s}</span>' for s in sorted(brief.sources_included)])

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Daily Intelligence Brief — {brief.date_str}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            --badge-bg: #0369a1;
            --badge-text: #e0f2fe;
            --consensus-bg: #7c2d12;
            --consensus-text: #ffedd5;
            --tag-bg: #334155;
            --tag-text: #cbd5e1;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 860px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 32px 20px;
            background: var(--card-bg);
            border-radius: 16px;
            border: 1px solid var(--card-border);
            margin-bottom: 24px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 28px;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .meta-bar {{
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .stats-grid {{
            display: flex;
            justify-content: center;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .stat-pill {{
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.2);
            color: var(--accent);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }}
        .exec-summary {{
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
            border-left: 4px solid var(--accent);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 32px;
            font-size: 15px;
            color: #e2e8f0;
        }}
        .category-section {{
            margin-bottom: 36px;
        }}
        .category-title {{
            font-size: 22px;
            margin: 0 0 4px 0;
            color: var(--text-primary);
        }}
        .category-desc {{
            color: var(--text-secondary);
            font-size: 13px;
            margin: 0 0 16px 0;
        }}
        .story-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }}
        .story-card:hover {{
            border-color: #64748b;
        }}
        .story-title {{
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 8px 0;
        }}
        .story-title a {{
            color: var(--text-primary);
            text-decoration: none;
        }}
        .story-title a:hover {{
            color: var(--accent);
            text-decoration: underline;
        }}
        .badge-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 12px;
            font-size: 12px;
        }}
        .source-badge {{
            background: var(--badge-bg);
            color: var(--badge-text);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 500;
        }}
        .consensus-badge {{
            background: var(--consensus-bg);
            color: var(--consensus-text);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 600;
        }}
        .story-summary {{
            color: #cbd5e1;
            font-size: 14.5px;
            margin: 0 0 12px 0;
            line-height: 1.55;
        }}
        .why-it-matters {{
            background: rgba(56, 189, 248, 0.08);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13.5px;
            color: #e0f2fe;
            margin-bottom: 10px;
        }}
        .why-it-matters strong {{
            color: var(--accent);
        }}
        .entities-row {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .entity-tag {{
            background: var(--tag-bg);
            color: var(--tag-text);
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .footer {{
            text-align: center;
            padding: 30px 10px;
            color: var(--text-secondary);
            font-size: 13px;
            border-top: 1px solid var(--card-border);
            margin-top: 40px;
        }}
        .source-chip {{
            display: inline-block;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 12px;
            margin: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>🧠 AI Daily Intelligence Brief</h1>
            <div class="meta-bar">
                <span>📅 {brief.date_str}</span> • 
                <span>🕒 {brief.generated_at.strftime('%H:%M UTC')}</span> • 
                <span>⏱️ Past {brief.time_window_hours} Hours</span>
            </div>
            <div class="stats-grid">
                <span class="stat-pill">📊 {brief.total_articles_ingested} Articles Ingested</span>
                <span class="stat-pill">🔄 {brief.total_duplicates_merged} Duplicates Merged</span>
                <span class="stat-pill">🎯 {brief.total_stories_selected} Curated Stories</span>
            </div>
        </header>

        {f'<div class="exec-summary"><strong>Executive Summary:</strong> {brief.executive_summary}</div>' if brief.executive_summary else ''}

        <div class="category-section">
            <h2 class="category-title">🚀 Top Headlines & Breaking News</h2>
            <p class="category-desc">The most impactful and widely covered stories in tech & AI today</p>
            {top_stories_html}
        </div>

        {sections_html}

        <footer class="footer">
            <p><strong>Sources Monitored Today:</strong></p>
            <div style="margin-bottom: 16px;">{sources_chips}</div>
            <p>Generated by AI News Brief Workflow • Multi-source deduplication & intelligent ranking</p>
        </footer>
    </div>
</body>
</html>
        """
        return html

    @classmethod
    def _format_story_html(cls, story: StoryCluster) -> str:
        consensus_html = ""
        if story.source_count > 1:
            sources_str = ", ".join(story.sources)
            consensus_html = f'<span class="consensus-badge">🔥 {story.source_count} Sources: {sources_str}</span>'

        engagement_html = ""
        if story.canonical_article.engagement_score > 0:
            engagement_html = f'<span style="color: #fbbf24; font-size: 12px;">★ {int(story.canonical_article.engagement_score)}</span>'

        entities_html = "".join([f'<span class="entity-tag">#{e}</span>' for e in story.key_entities])

        return f"""
        <div class="story-card">
            <h3 class="story-title"><a href="{story.url}" target="_blank" rel="noopener">{story.title}</a></h3>
            <div class="badge-row">
                <span class="source-badge">{story.canonical_article.source_name}</span>
                {consensus_html}
                {engagement_html}
                <span style="color: var(--text-secondary); font-size: 12px;">🕒 {story.published_at.strftime('%H:%M UTC')}</span>
            </div>
            <p class="story-summary">{story.summary}</p>
            {f'<div class="why-it-matters"><strong>💡 Why It Matters:</strong> {story.why_it_matters}</div>' if story.why_it_matters else ''}
            {f'<div class="entities-row">{entities_html}</div>' if entities_html else ''}
        </div>
        """

    @classmethod
    def to_slack_payload(cls, brief: DailyBrief) -> Dict[str, Any]:
        """Generate Slack blocks payload for webhook dispatch."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🧠 AI Daily Intelligence Brief — {brief.date_str}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Stats:* `{brief.total_articles_ingested} ingested` | `{brief.total_duplicates_merged} deduplicated` | `{brief.total_stories_selected} curated`"
                }
            },
            {"type": "divider"}
        ]

        if brief.executive_summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📌 Executive Summary:*\n{brief.executive_summary}"
                }
            })
            blocks.append({"type": "divider"})

        # Top 3 stories in Slack
        for story in brief.top_stories[:3]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{story.url}|{story.title}>*\n_{story.canonical_article.source_name}_ • {story.summary[:200]}...\n💡 _{story.why_it_matters}_"
                }
            })

        return {"blocks": blocks}
