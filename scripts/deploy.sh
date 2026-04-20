#!/bin/bash
# COTO Graphiti Deployment Script
# Run on the COTO-Apps droplet (64.23.168.243)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== COTO Graphiti Deployment ==="
echo "Project dir: $PROJECT_DIR"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker not installed"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "ERROR: Docker Compose not available"; exit 1; }

# Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and configure."
    exit 1
fi

# Validate required env vars
source "$PROJECT_DIR/.env"
if [ -z "${OPENAI_API_KEY:-}" ] || [ "$OPENAI_API_KEY" = "sk-CHANGE_ME" ]; then
    echo "ERROR: OPENAI_API_KEY not configured in .env"
    exit 1
fi
if [ -z "${NEO4J_PASSWORD:-}" ] || [ "$NEO4J_PASSWORD" = "CHANGE_ME_strong_password_here" ]; then
    echo "ERROR: NEO4J_PASSWORD not configured in .env"
    exit 1
fi

cd "$PROJECT_DIR"

echo ""
echo "--- Pulling/building images ---"
docker compose build --no-cache graphiti
docker compose pull neo4j

echo ""
echo "--- Starting services ---"
docker compose up -d

echo ""
echo "--- Waiting for health checks ---"
for i in $(seq 1 60); do
    if docker compose ps --format json | python3 -c "import sys,json; data=[json.loads(l) for l in sys.stdin]; healthy=[d for d in data if d.get('Health','')=='healthy']; print(f'{len(healthy)}/{len(data)} healthy'); exit(0 if len(healthy)==len(data) else 1)" 2>/dev/null; then
        echo "All services healthy!"
        break
    fi
    echo "  Waiting... ($i/60)"
    sleep 5
done

echo ""
echo "--- Service Status ---"
docker compose ps

echo ""
echo "--- Quick Health Check ---"
curl -sf http://localhost:8000/healthcheck && echo "" || echo "WARNING: Graphiti healthcheck failed"
curl -sf http://localhost:7474 >/dev/null && echo "Neo4j: OK" || echo "WARNING: Neo4j not responding"

echo ""
echo "=== Deployment complete ==="
echo "Graphiti API: http://localhost:8000"
echo "Neo4j Browser: http://localhost:7474"
