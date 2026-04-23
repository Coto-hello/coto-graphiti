#!/usr/bin/env python3
"""
Ingest Slack channel logs into Graphiti knowledge graph.
Splits channels into daily episodes for temporal context.
"""

import json
import os
import re
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

API_URL = os.getenv("GRAPHITI_URL", "http://64.23.168.243:8000")
API_TOKEN = os.getenv("GRAPHITI_TOKEN", "bzWoGLhiRGs4mHXS-pF5urNiMI9X98UDol7FuM8_GWY")
SLACK_ROOT = os.getenv("SLACK_ROOT", "/work/slack_visible/users/slk_u_c1492dcafd9c")

headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

# Channels to ingest in priority order
CHANNELS = [
    "coto-internal",
    "inkout", 
    "lenslock",
    "i-nett",
    "coto-marketing",
    "ask-viktor",
    "legacy-clients",
    "pure-light",
    "masons",
    "social",
    "task-agent",
    "all-coto-collective",
]

def parse_log_to_daily(log_path):
    """Parse a Slack log file into daily message chunks."""
    days = {}
    current_date = None
    
    with open(log_path, 'r') as f:
        for line in f:
            # Extract timestamp [ts] 
            ts_match = re.match(r'\[(\d+\.\d+)\]', line)
            if ts_match:
                ts = float(ts_match.group(1))
                dt = datetime.fromtimestamp(ts)
                date_key = dt.strftime('%Y-%m-%d')
                if date_key not in days:
                    days[date_key] = []
                days[date_key].append(line.strip())
    
    return days

def ingest_episode(name, content, source_desc, ref_time, group_id):
    """Send one episode to Graphiti."""
    if len(content.strip()) < 100:
        return "skipped-too-short"
    
    # Truncate very long episodes to 15K chars to avoid timeouts
    if len(content) > 15000:
        content = content[:15000] + "\n... [truncated]"
    
    episode = {
        "name": name,
        "content": content,
        "source": "slack",
        "source_description": source_desc,
        "reference_time": ref_time,
        "group_id": group_id
    }
    
    try:
        resp = requests.post(f"{API_URL}/episodes", json=episode, headers=headers, timeout=300)
        if resp.status_code == 200:
            return "success"
        else:
            return f"error-{resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        return "timeout"
    except Exception as e:
        return f"exception: {str(e)[:200]}"

def ingest_channel(channel_name, dry_run=False):
    """Ingest all daily episodes from a channel."""
    channel_dir = Path(SLACK_ROOT) / channel_name
    if not channel_dir.exists():
        print(f"  Channel dir not found: {channel_dir}")
        return {"success": 0, "skipped": 0, "error": 0}
    
    # Find all log files
    log_files = sorted(channel_dir.glob("*.log"))
    if not log_files:
        print(f"  No log files in {channel_name}")
        return {"success": 0, "skipped": 0, "error": 0}
    
    # Parse all logs into daily chunks
    all_days = {}
    for log_file in log_files:
        if '/threads/' in str(log_file):
            continue  # Skip thread files
        days = parse_log_to_daily(log_file)
        for date_key, messages in days.items():
            if date_key not in all_days:
                all_days[date_key] = []
            all_days[date_key].extend(messages)
    
    print(f"  {len(all_days)} days of messages across {len(log_files)} log files")
    
    results = {"success": 0, "skipped": 0, "error": 0}
    sorted_days = sorted(all_days.keys())
    
    for i, date_key in enumerate(sorted_days):
        messages = all_days[date_key]
        content = "\n".join(messages)
        
        if len(content.strip()) < 100:
            results["skipped"] += 1
            continue
        
        name = f"slack-{channel_name}-{date_key}"
        ref_time = f"{date_key}T12:00:00-07:00"
        source_desc = f"Slack #{channel_name} messages on {date_key} ({len(messages)} messages)"
        group_id = f"coto-slack-{channel_name}"
        
        if dry_run:
            print(f"    [{i+1}/{len(sorted_days)}] Would ingest: {name} ({len(content)} chars, {len(messages)} msgs)")
            results["skipped"] += 1
            continue
        
        print(f"    [{i+1}/{len(sorted_days)}] {date_key} ({len(content)} chars, {len(messages)} msgs)...", end=" ", flush=True)
        result = ingest_episode(name, content, source_desc, ref_time, group_id)
        print(result)
        
        if result == "success":
            results["success"] += 1
        elif result.startswith("skipped"):
            results["skipped"] += 1
        else:
            results["error"] += 1
        
        # Delay between episodes
        time.sleep(2)
    
    return results

def main():
    dry_run = "--dry-run" in sys.argv
    channels = sys.argv[1:] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else CHANNELS
    # Remove flags from channels
    channels = [c for c in channels if not c.startswith("--")]
    
    if dry_run:
        print("DRY RUN MODE - no data will be ingested\n")
    
    print("=" * 60)
    print(f"SLACK CHANNEL INGESTION - {len(channels)} channels")
    print("=" * 60)
    
    total = {"success": 0, "skipped": 0, "error": 0}
    
    for channel in channels:
        print(f"\n--- #{channel} ---")
        results = ingest_channel(channel, dry_run=dry_run)
        print(f"  Results: {results}")
        for k in total:
            total[k] += results[k]
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total}")
    
    if not dry_run:
        stats = requests.get(f"{API_URL}/stats", headers=headers)
        print(f"Graph stats: {stats.json()}")
    
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
