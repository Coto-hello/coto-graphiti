"""
Ingest Notion pages into Graphiti Knowledge Graph.

Usage:
    python ingest_notion.py --all
    python ingest_notion.py --database <database_id>

Fetches Notion pages via the MCP API and sends them to Graphiti
for entity extraction and graph building.
"""

import argparse
import os
import sys

import httpx

GRAPHITI_URL = os.getenv("GRAPHITI_URL", "http://localhost:8000")

# Priority Notion databases to ingest
PRIORITY_DATABASES = {
    "knowledge_index": "1f230523-e632-80b7-af50-d62bfefbf26d",
    "clients": "18f30523-e632-80f5-9764-000b95058920",
    "tasks": "32c30523-e632-80dd-9d25-00928b6e6fd1",
    "credentials": "43acce30-e785-40eb-a6b7-0c3479d631bc",
    "content_by_viktor": "33530523-e632-8065-83f1-c1f2e8f30c3d",
}


def ingest_page(page_id: str, title: str, content: str, source_desc: str):
    """Send a single Notion page to Graphiti."""
    episode_name = f"notion-{page_id[:8]}-{title[:40].replace(' ', '-')}"

    try:
        resp = httpx.post(
            f"{GRAPHITI_URL}/episodes",
            json={
                "name": episode_name,
                "content": content,
                "source": "notion",
                "source_description": source_desc,
                "group_id": "coto",
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        print(f"  ✓ {title} ({len(content)} chars)")
        return True
    except Exception as e:
        print(f"  ✗ {title}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ingest Notion into Graphiti")
    parser.add_argument("--all", action="store_true", help="Ingest all priority databases")
    parser.add_argument("--database", type=str, help="Specific database ID to ingest")
    args = parser.parse_args()

    print("Notion ingestion script ready.")
    print("This script requires the Viktor SDK — run from the Viktor sandbox.")
    print(f"Graphiti endpoint: {GRAPHITI_URL}")

    # Note: Actual Notion fetching uses the Viktor SDK (async)
    # This script provides the framework; actual execution happens via
    # a wrapper that imports sdk.tools.mcp_notion
    print("\nTo run: use the async wrapper in the Viktor sandbox.")


if __name__ == "__main__":
    main()
