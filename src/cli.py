"""
Command Line Interface for the AI News Brief Generator.
Supports on-demand brief generation, source inspection, health testing, scheduler, and web server.
"""

import argparse
import sys
import os
import subprocess
from datetime import datetime, timezone

# Ensure stdout and stderr handle utf-8 on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.workflow import BriefWorkflow
from src.generator import BriefGenerator
from src.scheduler import DailyScheduler


def parse_args():
    parser = argparse.ArgumentParser(
        prog="ai-brief",
        description="AI News Brief Generator — Multi-source ingestion, deduplication, and ranked daily intelligence."
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Generate today's AI news brief")
    run_parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours (default: 24)")
    run_parser.add_argument("--top", type=int, default=5, help="Number of top headlines (default: 5)")
    run_parser.add_argument("--format", choices=["markdown", "html", "json", "all"], default="all", help="Output format")
    run_parser.add_argument("--output-dir", default="output/briefs", help="Output directory")
    run_parser.add_argument("--sources", type=str, default=None, help="Comma-separated list of source IDs")
    run_parser.add_argument("--similarity", type=float, default=0.58, help="Deduplication similarity threshold (0.0 to 1.0)")
    run_parser.add_argument("--preview", action="store_true", help="Print markdown preview to console")
    run_parser.add_argument("--webhook", type=str, default=None, help="Slack webhook URL to post to")

    # Command: sources
    subparsers.add_parser("sources", help="List all configured news & research sources")

    # Command: test
    subparsers.add_parser("test", help="Test connectivity and live response of all news sources")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch the interactive Streamlit web dashboard")
    serve_parser.add_argument("--port", type=int, default=8501, help="Port to run Streamlit on (default: 8501)")

    # Command: schedule
    sched_parser = subparsers.add_parser("schedule", help="Start the automated daily scheduler daemon")
    sched_parser.add_argument("--hour", type=int, default=8, help="Hour to run (UTC, 0-23)")
    sched_parser.add_argument("--minute", type=int, default=0, help="Minute to run (0-59)")

    return parser.parse_args()


def cmd_run(args):
    print("=" * 65)
    print("🧠 AI NEWS BRIEF GENERATOR — RUNNING WORKFLOW")
    print("=" * 65)
    print(f"⏱️ Lookback Window: {args.hours} hours")
    print(f"🔍 Similarity Threshold: {args.similarity}")

    source_ids = [s.strip() for s in args.sources.split(",")] if args.sources else None
    workflow = BriefWorkflow()

    print("\n📡 Fetching stories from multi-source network...")
    brief = workflow.run(
        lookback_hours=args.hours,
        source_ids=source_ids,
        top_n=args.top,
        similarity_threshold=args.similarity
    )

    print(f"\n📊 Ingestion Results:")
    print(f"  • Total Articles Ingested: {brief.total_articles_ingested}")
    print(f"  • Duplicates Merged:       {brief.total_duplicates_merged}")
    print(f"  • Unique Curated Stories:  {brief.total_stories_selected}")
    print(f"  • Active Sources:          {len(brief.sources_included)}")

    # Determine formats
    if args.format == "all":
        formats = ["markdown", "html", "json"]
    else:
        formats = [args.format]

    saved_files = workflow.save_brief(brief, output_dir=args.output_dir, formats=formats)

    print("\n💾 Saved Brief Artifacts:")
    for fmt, path in saved_files.items():
        print(f"  • {fmt.upper()}: {os.path.abspath(path)}")

    if args.webhook:
        print(f"\n📡 Sending Slack Webhook...")
        success = workflow.send_webhook(brief, args.webhook)
        print(f"  Webhook status: {'SUCCESS' if success else 'FAILED'}")

    if args.preview:
        print("\n" + "=" * 65)
        print("PREVIEW:")
        print("=" * 65)
        print(BriefGenerator.to_markdown(brief))


def cmd_sources():
    workflow = BriefWorkflow()
    print("=" * 70)
    print("CONFIGURED NEWS & RESEARCH SOURCES")
    print("=" * 70)
    print(f"{'ID':<18} | {'Type':<8} | {'Cat':<10} | {'Weight':<6} | Name")
    print("-" * 70)
    for src in workflow.ingestion.sources:
        status = "✓" if src.enabled else "✗"
        print(f"{src.id:<18} | {src.type:<8} | {src.category:<10} | {src.weight:<6.1f} | [{status}] {src.name}")
    print("-" * 70)


def cmd_test():
    print("=" * 70)
    print("TESTING SOURCE CONNECTIVITY & LATENCY")
    print("=" * 70)
    workflow = BriefWorkflow()
    cutoff = datetime.now(timezone.utc)

    for src in workflow.ingestion.sources:
        if not src.enabled:
            print(f"⊘ [DISABLED] {src.name}")
            continue

        fetcher = workflow.ingestion._get_fetcher(src)
        start = datetime.now()
        try:
            # Test fetch with 7-day lookback to verify entries exist
            from datetime import timedelta
            items = fetcher.fetch(cutoff - timedelta(days=7))
            duration = (datetime.now() - start).total_seconds()
            print(f"✓ [OK] {src.name:<25} ({duration:.2f}s) — {len(items)} entries found")
        except Exception as e:
            print(f"✗ [FAIL] {src.name:<25} — Error: {e}")


def cmd_serve(args):
    print("🚀 Launching AI News Brief Web Dashboard (Streamlit)...")
    app_path = os.path.join(os.path.dirname(__file__), "..", "web", "app.py")
    subprocess.run(["streamlit", "run", app_path, "--server.port", str(args.port)])


def cmd_schedule(args):
    print(f"⏰ Starting AI News Brief Daily Scheduler (Scheduled for {args.hour:02d}:{args.minute:02d} UTC)...")
    scheduler = DailyScheduler(run_at_hour=args.hour, run_at_minute=args.minute)
    scheduler.start_background()
    print("Scheduler is active in background. Press Ctrl+C to exit.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()


def main():
    args = parse_args()
    if not args.command or args.command == "run":
        if not args.command:
            # Default to running with default args
            parser = argparse.ArgumentParser()
            parser.add_argument("--hours", type=int, default=24)
            parser.add_argument("--top", type=int, default=5)
            parser.add_argument("--format", default="all")
            parser.add_argument("--output-dir", default="output/briefs")
            parser.add_argument("--sources", default=None)
            parser.add_argument("--similarity", type=float, default=0.58)
            parser.add_argument("--preview", action="store_true")
            parser.add_argument("--webhook", default=None)
            args = parser.parse_args(sys.argv[1:])
        cmd_run(args)
    elif args.command == "sources":
        cmd_sources()
    elif args.command == "test":
        cmd_test()
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "schedule":
        cmd_schedule(args)


if __name__ == "__main__":
    main()
