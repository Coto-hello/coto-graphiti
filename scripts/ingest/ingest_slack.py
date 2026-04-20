"""
Ingest Slack channel logs into Graphiti Knowledge Graph.

Usage:
    python ingest_slack.py --channel inkout --days 30
    python ingest_slack.py --all --days 90

Reads from Viktor's local Slack sync directory and sends episodes
to the Graphiti API for entity extraction and graph building.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

GRAPHITI_URL = os.getenv("GRAPHITI_URL", "http://localhost:8000")
SLACK_ROOT = os.getenv("SLACK_ROOT", "/work/slack_visible/users/slk_u_5a9290775000")

# Channels to ingest (in priority order)
PRIORITY_CHANNELS = [
    "inkout",
    "ask-viktor",
    "coto-internal",
    "management",
    "i-nett",
    "lenslock",
    "masons",
    "sales",
    "coto-marketing",
    "meeting-reports",
    "inkout-cmo",
    "copywriting",
]


def parse_slack_log(filepath: str) -> list[dict]:
    """Parse a Slack log file into individual messages."""
    messages = []
    with open(filepath, "r") as f:
        for line in f:
            match = re.match(r'\[(\d+\.\d+)\] @([^:]+): (.+)', line.strip())
            if match:
                ts, user, content = match.groups()
                # Skip bot messages and join/leave messages
                if "has joined the channel" in content or "has left the channel" in content:
                    continue
                messages.append({
                    "timestamp": ts,
                    "user": user,
                    "content": content,
                })
    return messages


def chunk_messages(messages: list[dict], chunk_size: int = 20) -> list[str]:
    """Group messages into chunks for episode ingestion."""
    chunks = []
    for i in range(0, len(messages), chunk_size):
        batch = messages[i:i + chunk_size]
        text = "\n".join(
            f"[{m['user']}]: {m['content']}" for m in batch
        )
        chunks.append(text)
    return chunks


def ingest_channel(channel: str, days: int = 30):
    """Ingest a single channel's messages."""
    channel_dir = Path(SLACK_ROOT) / channel
    if not channel_dir.exists():
        print(f"  ⚠ Channel directory not found: {channel}")
        return 0

    cutoff = datetime.utcnow() - timedelta(days=days)
    total_episodes = 0

    # Find relevant log files
    log_files = sorted(channel_dir.glob("*.log"))
    for log_file in log_files:
        # Parse year-month from filename
        match = re.match(r"(\d{4})-(\d{2})\.log", log_file.name)
        if not match:
            continue

        year, month = int(match.group(1)), int(match.group(2))
        file_date = datetime(year, month, 1)
        if file_date < cutoff.replace(day=1):
            continue

        messages = parse_slack_log(str(log_file))
        if not messages:
            continue

        chunks = chunk_messages(messages)
        for j, chunk in enumerate(chunks):
            episode_name = f"slack-{channel}-{log_file.stem}-chunk{j}"

            try:
                resp = httpx.post(
                    f"{GRAPHITI_URL}/episodes",
                    json={
                        "name": episode_name,
                        "content": chunk,
                        "source": "slack",
                        "source_description": f"Slack #{channel} channel messages",
                        "reference_time": f"{year}-{month:02d}-15T12:00:00Z",
                        "group_id": "coto",
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                total_episodes += 1
                print(f"  ✓ {episode_name} ({len(chunk)} chars)")
            except Exception as e:
                print(f"  ✗ {episode_name}: {e}")

    return total_episodes


def main():
    parser = argparse.ArgumentParser(description="Ingest Slack into Graphiti")
    parser.add_argument("--channel", type=str, help="Specific channel to ingest")
    parser.add_argument("--all", action="store_true", help="Ingest all priority channels")
    parser.add_argument("--days", type=int, default=30, help="Days of history to ingest")
    args = parser.parse_args()

    if not args.channel and not args.all:
        parser.print_help()
        sys.exit(1)

    channels = PRIORITY_CHANNELS if args.all else [args.channel]
    total = 0

    for ch in channels:
        print(f"\n📝 Ingesting #{ch} (last {args.days} days)...")
        count = ingest_channel(ch, args.days)
        total += count
        print(f"  → {count} episodes ingested")

    print(f"\n✅ Total: {total} episodes ingested across {len(channels)} channels")


if __name__ == "__main__":
    main()
