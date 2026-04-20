# COTO Graphiti Knowledge Graph

Temporal knowledge graph engine for COTO Collective's AI memory system, powered by [Graphiti](https://github.com/getzep/graphiti) and Neo4j.

## Overview

Graphiti provides Viktor (COTO's AI coworker) with a persistent, temporal knowledge graph that:

- **Extracts entities and relationships** from unstructured text (Slack, meetings, Notion, CRM)
- **Tracks temporal changes** — knows when facts were true and when they changed
- **Enables sub-second queries** across 200M+ chars of organizational data
- **Supports multi-hop reasoning** — finds connections humans would miss

## Architecture

```
┌──────────────────┐     ┌──────────────────┐
│  Viktor Agent     │────▶│  Graphiti API     │
│  (scripts/SDK)    │◀────│  (FastAPI :8000)  │
└──────────────────┘     └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │  Neo4j Graph DB   │
                         │  (:7474 / :7687)  │
                         └──────────────────┘
```

## Data Sources

| Source | Type | Estimated Size | Status |
|--------|------|---------------|--------|
| Viktor Skills/Knowledge | text | ~1M chars | Queued |
| Notion (312+ pages) | text | 1-2M chars | Queued |
| Read AI Meetings (94+) | message | 1.5-2.5M chars | Queued |
| Google Drive Docs | text | 0.5-1.5M chars | Queued |
| Slack (22+ channels) | message | ~1M+ chars | Queued |
| Claude Chat Export | text | 80-120M chars | Queued |
| Google Chat (258+ spaces) | text | 5-65M chars | Queued |
| GHL CRM Data | json | 2-5M chars | Queued |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key (for entity extraction)

### Deploy

```bash
# Clone
git clone https://github.com/Coto-hello/coto-graphiti.git
cd coto-graphiti

# Configure
cp .env.example .env
# Edit .env with your values

# Launch
docker compose up -d

# Verify
curl http://localhost:8000/healthcheck
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthcheck` | Service health check |
| POST | `/episodes` | Ingest text episode |
| POST | `/search` | Search knowledge graph |
| GET | `/stats` | Graph statistics |

### Example: Ingest an Episode

```bash
curl -X POST http://localhost:8000/episodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "slack-inkout-2026-04-17",
    "content": "Discussion about new campaign launch...",
    "source": "slack",
    "source_description": "inkOUT Slack channel",
    "reference_time": "2026-04-17T10:00:00Z"
  }'
```

### Example: Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What CRM issues have clients reported?",
    "num_results": 10
  }'
```

## Infrastructure

| Component | Spec | Notes |
|-----------|------|-------|
| Droplet | COTO-Apps (DigitalOcean SFO3) | Ubuntu 24.04 |
| Neo4j | 5.26 Community Edition | ~512MB heap |
| Graphiti | v0.28.2 (graphiti-core) | FastAPI server |
| LLM | OpenAI GPT-4o-mini | Entity extraction |

## Repository Structure

```
coto-graphiti/
├── docker-compose.yml          # Service orchestration
├── .env.example                # Environment template
├── graphiti-server/
│   ├── Dockerfile              # Graphiti API server image
│   ├── server.py               # FastAPI application
│   └── requirements.txt        # Python dependencies
├── scripts/
│   ├── deploy.sh               # Deployment script
│   └── ingest/                 # Data ingestion scripts
├── CHANGELOG.md                # Change log
└── README.md                   # This file
```

## Deployment

Managed by Viktor. All changes go through GitHub Flow:
- `main` = production (protected)
- Feature branches → PR → review → merge

## License

Internal COTO Collective project. Not for redistribution.
