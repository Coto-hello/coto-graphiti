#!/bin/bash
# Remote deployment script — runs from Viktor's sandbox
# Transfers files to COTO-Apps droplet and starts services

set -euo pipefail

DROPLET_IP="64.23.168.243"
DROPLET_USER="viktor"
SSH_KEY="/work/keys/viktor-coto"
PROJECT_DIR="/work/projects/coto-graphiti"
REMOTE_DIR="/home/viktor/coto-graphiti"

echo "=== COTO Graphiti Remote Deployment ==="
echo "Target: ${DROPLET_USER}@${DROPLET_IP}"
echo "Date: $(date -u)"

# Step 1: Create remote directory structure
echo ""
echo "--- Creating remote directories ---"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "mkdir -p ${REMOTE_DIR}/graphiti-server ${REMOTE_DIR}/scripts/ingest"

# Step 2: Transfer files
echo ""
echo "--- Transferring project files ---"
scp -i "$SSH_KEY" "${PROJECT_DIR}/docker-compose.yml" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/"
scp -i "$SSH_KEY" "${PROJECT_DIR}/.env" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/"
scp -i "$SSH_KEY" "${PROJECT_DIR}/graphiti-server/Dockerfile" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/graphiti-server/"
scp -i "$SSH_KEY" "${PROJECT_DIR}/graphiti-server/requirements.txt" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/graphiti-server/"
scp -i "$SSH_KEY" "${PROJECT_DIR}/graphiti-server/server.py" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/graphiti-server/"
scp -i "$SSH_KEY" "${PROJECT_DIR}/scripts/deploy.sh" "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_DIR}/scripts/"

echo ""
echo "--- Files transferred ---"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "ls -la ${REMOTE_DIR}/ && echo '---' && ls -la ${REMOTE_DIR}/graphiti-server/"

# Step 3: Run deployment
echo ""
echo "--- Starting Docker Compose ---"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "cd ${REMOTE_DIR} && docker compose up -d --build"

# Step 4: Wait for services
echo ""
echo "--- Waiting for services to be healthy ---"
for i in $(seq 1 60); do
    HEALTH=$(ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "cd ${REMOTE_DIR} && docker compose ps --format '{{.Name}} {{.Health}}'" 2>/dev/null || echo "error")
    echo "  [$i/60] $HEALTH"
    if echo "$HEALTH" | grep -q "healthy" && ! echo "$HEALTH" | grep -q "starting"; then
        echo "  All services healthy!"
        break
    fi
    sleep 5
done

# Step 5: Verify
echo ""
echo "--- Verification ---"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "curl -sf http://localhost:8000/healthcheck && echo '' || echo 'Graphiti: NOT READY'"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "curl -sf http://localhost:7474 >/dev/null && echo 'Neo4j: OK' || echo 'Neo4j: NOT READY'"

echo ""
echo "--- Docker Status ---"
ssh -i "$SSH_KEY" "${DROPLET_USER}@${DROPLET_IP}" "cd ${REMOTE_DIR} && docker compose ps"

echo ""
echo "=== Deployment Complete ==="
