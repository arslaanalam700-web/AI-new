"""
Interactive Streamlit Web Dashboard for the AI News Brief Generator.
"""

import streamlit as st
import os
import sys
from datetime import datetime, timezone
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workflow import BriefWorkflow
from src.generator import BriefGenerator
from src.models import SourceConfig, DailyBrief

# Page configuration
st.set_page_config(
    page_title="AI News Brief Generator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .story-card-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .source-tag {
        background-color: #0369a1;
        color: #e0f2fe;
        padding: 3px 8px;
        border-radius: 5px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .consensus-tag {
        background-color: #7c2d12;
        color: #ffedd5;
        padding: 3px 8px;
        border-radius: 5px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .why-box {
        background-color: rgba(56, 189, 248, 0.08);
        border-left: 3px solid #38bdf8;
        padding: 8px 12px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_workflow():
    return BriefWorkflow()


def main():
    workflow = get_workflow()

    # Sidebar
    st.sidebar.title("⚙️ Workflow Controls")
    st.sidebar.markdown("Configure ingestion, deduplication, and ranking parameters.")

    lookback_hours = st.sidebar.slider("⏱️ Lookback Window (Hours)", min_value=6, max_value=72, value=24, step=6)
    similarity_thresh = st.sidebar.slider("🔍 Deduplication Sensitivity", min_value=0.40, max_value=0.85, value=0.58, step=0.02,
                                         help="Lower values merge more aggressively; higher values require closer wording.")
    top_n = st.sidebar.slider("🚀 Top Headlines Count", min_value=3, max_value=10, value=5)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📡 News & Research Sources")

    all_sources = workflow.ingestion.sources
    selected_source_ids = []
    
    col_a, col_b = st.sidebar.columns(2)
    select_all = col_a.button("Select All", use_container_width=True)
    unselect_all = col_b.button("Deselect All", use_container_width=True)

    for src in all_sources:
        default_val = False if unselect_all else (True if select_all else src.enabled)
        is_checked = st.sidebar.checkbox(f"{src.name} ({src.category})", value=default_val, key=f"src_{src.id}")
        if is_checked:
            selected_source_ids.append(src.id)

    # Custom RSS Expander
    with st.sidebar.expander("➕ Add Custom RSS Source"):
        custom_name = st.text_input("Source Name", placeholder="e.g. OpenAI Research Blog")
        custom_url = st.text_input("RSS Feed URL", placeholder="https://.../rss.xml")
        custom_cat = st.selectbox("Category", ["research", "industry", "dev_tools", "policy"], index=0)
        custom_weight = st.slider("Source Authority Weight", 0.5, 2.0, 1.0, 0.1)
        add_custom = st.button("Add Feed to Active Session")
        
        if add_custom and custom_name and custom_url:
            new_source = SourceConfig(
                id=f"custom_{len(workflow.ingestion.sources) + 1}",
                name=custom_name,
                type="rss",
                url=custom_url,
                category=custom_cat,
                weight=custom_weight,
                enabled=True
            )
            workflow.ingestion.sources.append(new_source)
            st.sidebar.success(f"Added {custom_name}!")
            st.rerun()

    st.sidebar.markdown("---")
    run_button = st.sidebar.button("🚀 Generate Today's Brief", type="primary", use_container_width=True)

    # Main Area
    st.markdown('<div class="main-header">🧠 AI Daily Intelligence Brief Generator</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">Multi-source ingestion • Fuzzy deduplication • Consensus ranking • Multi-channel export</div>',
        unsafe_allow_html=True
    )

    # Manage session state for generated brief
    if "current_brief" not in st.session_state:
        st.session_state.current_brief = None

    if run_button or st.session_state.current_brief is None:
        with st.spinner("Fetching from multi-source network, deduplicating stories, and computing ranking scores..."):
            brief = workflow.run(
                lookback_hours=lookback_hours,
                source_ids=selected_source_ids,
                top_n=top_n,
                similarity_threshold=similarity_thresh
            )
            st.session_state.current_brief = brief
            workflow.save_brief(brief)

    brief = st.session_state.current_brief

    if not brief:
        st.warning("No brief generated yet. Click 'Generate Today's Brief' in the sidebar.")
        return

    # Ingestion Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📊 Ingested Articles", brief.total_articles_ingested)
    m2.metric("🔄 Duplicates Merged", brief.total_duplicates_merged)
    m3.metric("🎯 Curated Stories", brief.total_stories_selected)
    m4.metric("📡 Active Sources", len(brief.sources_included))

    # Executive Summary Box
    if brief.executive_summary:
        st.info(f"**📌 Executive Overview:** {brief.executive_summary}")

    # Tabs
    tab_brief, tab_markdown, tab_html, tab_json, tab_archive = st.tabs([
        "📰 Curated Stories",
        "📝 Markdown Brief",
        "🌐 HTML Newsletter",
        "🔌 JSON & Webhook",
        "📚 Briefs Archive"
    ])

    # Tab 1: Interactive Story Cards
    with tab_brief:
        # Category Filter & Search
        col_search, col_filter = st.columns([2, 1])
        search_query = col_search.text_input("🔍 Search stories by keyword, entity, or title...", "").lower()
        selected_category = col_filter.selectbox(
            "Filter Category",
            ["All Stories", "🚀 Top Headlines", "🔬 Research", "💼 Industry", "🛠️ Dev Tools", "⚖️ Policy"]
        )

        # Collect stories based on category filter
        all_clusters = []
        if selected_category == "All Stories":
            all_clusters = brief.top_stories + [s for stories in brief.sections.values() for s in stories]
        elif selected_category == "🚀 Top Headlines":
            all_clusters = brief.top_stories
        elif selected_category == "🔬 Research":
            all_clusters = brief.sections.get("research", [])
        elif selected_category == "💼 Industry":
            all_clusters = brief.sections.get("industry", [])
        elif selected_category == "🛠️ Dev Tools":
            all_clusters = brief.sections.get("dev_tools", [])
        elif selected_category == "⚖️ Policy":
            all_clusters = brief.sections.get("policy", [])

        # Filter by search
        if search_query:
            all_clusters = [
                c for c in all_clusters
                if search_query in c.title.lower()
                or search_query in c.summary.lower()
                or any(search_query in e.lower() for e in c.key_entities)
            ]

        if not all_clusters:
            st.info("No stories match the active filters.")
        else:
            for cluster in all_clusters:
                with st.container():
                    st.markdown(f"### [{cluster.title}]({cluster.url})")
                    
                    # Badges line
                    badges = [f"<span class='source-tag'>{cluster.canonical_article.source_name}</span>"]
                    if cluster.source_count > 1:
                        badges.append(f"<span class='consensus-tag'>🔥 {cluster.source_count} Sources: {', '.join(cluster.sources)}</span>")
                    if cluster.canonical_article.engagement_score > 0:
                        badges.append(f"⭐ **{int(cluster.canonical_article.engagement_score)} pts**")
                    badges.append(f"🕒 *{cluster.published_at.strftime('%Y-%m-%d %H:%M UTC')}*")
                    badges.append(f"📈 Score: `{cluster.score}`")

                    st.markdown(" • ".join(badges), unsafe_allow_html=True)
                    st.write(cluster.summary)

                    if cluster.why_it_matters:
                        st.markdown(f"<div class='why-box'><strong>💡 Why It Matters:</strong> {cluster.why_it_matters}</div>", unsafe_allow_html=True)

                    if cluster.key_entities:
                        st.caption("🏷️ " + " ".join([f"`#{e}`" for e in cluster.key_entities]))

                    # If multiple articles in cluster, show expander
                    if len(cluster.articles) > 1:
                        with st.expander(f"📑 View {len(cluster.articles) - 1} Corroborating / Syndicated Coverage Reports"):
                            for related in cluster.articles:
                                if related.id != cluster.canonical_article.id:
                                    st.markdown(f"- **[{related.title}]({related.url})** — *{related.source_name}*")
                                    if related.summary:
                                        st.caption(f"  {related.summary[:200]}...")
                    st.markdown("---")

    # Tab 2: Markdown
    with tab_markdown:
        md_text = BriefGenerator.to_markdown(brief)
        st.download_button(
            label="📥 Download Markdown Brief (.md)",
            data=md_text,
            file_name=f"ai_news_brief_{brief.date_str}.md",
            mime="text/markdown",
            use_container_width=True
        )
        st.text_area("Markdown Source", md_text, height=500)

    # Tab 3: HTML Newsletter
    with tab_html:
        html_content = BriefGenerator.to_html(brief)
        st.download_button(
            label="📥 Download HTML Newsletter (.html)",
            data=html_content,
            file_name=f"ai_news_brief_{brief.date_str}.html",
            mime="text/html",
            use_container_width=True
        )
        st.components.v1.html(html_content, height=800, scrolling=True)

    # Tab 4: JSON & Webhook
    with tab_json:
        json_str = brief.to_json(indent=2)
        st.download_button(
            label="📥 Download JSON Feed (.json)",
            data=json_str,
            file_name=f"ai_news_brief_{brief.date_str}.json",
            mime="application/json",
            use_container_width=True
        )

        st.subheader("📡 Slack / Discord Webhook Dispatch")
        webhook_input = st.text_input("Enter Webhook URL (Slack or Discord compatible)", "")
        if st.button("Send Brief via Webhook"):
            if not webhook_input:
                st.error("Please provide a valid webhook URL.")
            else:
                success = workflow.send_webhook(brief, webhook_input)
                if success:
                    st.success("Successfully delivered brief to webhook!")
                else:
                    st.error("Failed to deliver to webhook. Please verify URL.")

        with st.expander("View Raw JSON Schema"):
            st.code(json_str, language="json")

    # Tab 5: Briefs Archive
    with tab_archive:
        st.subheader("📚 Saved Briefs Archive")
        briefs_dir = "output/briefs"
        if os.path.exists(briefs_dir):
            files = [f for f in os.listdir(briefs_dir) if f.endswith(".md")]
            if files:
                selected_file = st.selectbox("Select Archived Brief", sorted(files, reverse=True))
                if selected_file:
                    with open(os.path.join(briefs_dir, selected_file), "r", encoding="utf-8") as af:
                        st.markdown(af.read())
            else:
                st.info("No saved briefs in output directory yet.")
        else:
            st.info("Archive directory does not exist yet.")


if __name__ == "__main__":
    main()
