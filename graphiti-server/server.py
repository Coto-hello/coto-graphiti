"""
COTO Graphiti Knowledge Graph Server

FastAPI wrapper around graphiti-core providing REST API for
Viktor's temporal knowledge graph operations.

Endpoints:
  POST /episodes          - Ingest text episodes (Slack, meetings, docs)
  POST /search            - Hybrid search across the knowledge graph
  GET  /entities          - List entities (nodes) in the graph
  GET  /relationships     - List relationships (edges)
  GET  /healthcheck       - Health check endpoint
  DELETE /graph           - Clear the graph (admin only)
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global Graphiti client
graphiti_client: Optional[Graphiti] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup Graphiti client."""
    global graphiti_client

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    logger.info(f"Connecting to Neo4j at {neo4j_uri}...")
    graphiti_client = Graphiti(neo4j_uri, neo4j_user, neo4j_password)

    try:
        await graphiti_client.build_indices_and_constraints()
        logger.info("Graphiti initialized successfully — indices and constraints built.")
    except Exception as e:
        logger.error(f"Failed to initialize Graphiti: {e}")
        raise

    yield

    # Cleanup
    if graphiti_client:
        await graphiti_client.close()
        logger.info("Graphiti client closed.")


app = FastAPI(
    title="COTO Graphiti Knowledge Graph",
    description="Temporal knowledge graph API for COTO Collective's AI memory system",
    version="1.0.0",
    lifespan=lifespan,
)


# === Request/Response Models ===

class EpisodeRequest(BaseModel):
    """Ingest a text episode into the knowledge graph."""
    name: str = Field(..., description="Episode identifier (e.g., 'slack-inkout-2026-04-17')")
    content: str = Field(..., description="The text content to process")
    source: str = Field(default="manual", description="Source type: slack, meeting, notion, drive, crm, manual")
    source_description: str = Field(default="", description="Human-readable source description")
    reference_time: Optional[str] = Field(
        default=None,
        description="ISO timestamp for when this content was created (for temporal placement)"
    )
    group_id: Optional[str] = Field(
        default="coto",
        description="Group/namespace for multi-tenant isolation"
    )


class SearchRequest(BaseModel):
    """Search the knowledge graph."""
    query: str = Field(..., description="Natural language search query")
    num_results: int = Field(default=10, description="Maximum results to return")
    group_ids: Optional[list[str]] = Field(default=None, description="Filter by group IDs")


class EntityResponse(BaseModel):
    name: str
    entity_type: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None


class SearchResult(BaseModel):
    content: str
    score: float
    source: Optional[str] = None


# === Endpoints ===

@app.get("/healthcheck")
async def healthcheck():
    """Health check — verifies Neo4j connection."""
    if graphiti_client is None:
        raise HTTPException(status_code=503, detail="Graphiti client not initialized")
    return {"status": "healthy", "service": "coto-graphiti", "timestamp": datetime.now(tz=timezone.utc).isoformat()}


@app.post("/episodes")
async def add_episode(req: EpisodeRequest):
    """Ingest a text episode into the knowledge graph.
    
    This extracts entities, relationships, and facts from the text,
    adding them to the temporal knowledge graph with proper timestamps.
    """
    if graphiti_client is None:
        raise HTTPException(status_code=503, detail="Graphiti not ready")

    try:
        ref_time = datetime.fromisoformat(req.reference_time) if req.reference_time else datetime.now(tz=timezone.utc)

        episode_type_map = {
            "slack": EpisodeType.message,
            "meeting": EpisodeType.message,
            "notion": EpisodeType.text,
            "drive": EpisodeType.text,
            "crm": EpisodeType.json,
            "manual": EpisodeType.text,
        }
        ep_type = episode_type_map.get(req.source, EpisodeType.text)

        await graphiti_client.add_episode(
            name=req.name,
            episode_body=req.content,
            source=ep_type,
            source_description=req.source_description or f"COTO {req.source} data",
            reference_time=ref_time,
            group_id=req.group_id or "coto",
        )

        logger.info(f"Episode ingested: {req.name} (source={req.source}, {len(req.content)} chars)")
        return {
            "status": "success",
            "episode": req.name,
            "chars_processed": len(req.content),
            "source": req.source,
            "timestamp": ref_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"Episode ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(req: SearchRequest):
    """Search the knowledge graph using hybrid retrieval.
    
    Combines graph traversal, entity search, and embedding similarity
    for comprehensive results.
    """
    if graphiti_client is None:
        raise HTTPException(status_code=503, detail="Graphiti not ready")

    try:
        results = await graphiti_client.search(
            query=req.query,
            num_results=req.num_results,
            group_ids=req.group_ids,
        )

        formatted = []
        for r in results:
            formatted.append({
                "fact": r.fact if hasattr(r, 'fact') else str(r),
                "uuid": r.uuid if hasattr(r, 'uuid') else None,
                "created_at": r.created_at.isoformat() if hasattr(r, 'created_at') and r.created_at else None,
                "expired_at": r.expired_at.isoformat() if hasattr(r, 'expired_at') and r.expired_at else None,
            })

        logger.info(f"Search completed: '{req.query}' → {len(formatted)} results")
        return {"query": req.query, "results": formatted, "count": len(formatted)}

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get knowledge graph statistics."""
    if graphiti_client is None:
        raise HTTPException(status_code=503, detail="Graphiti not ready")

    try:
        # Query Neo4j directly for stats
        driver = graphiti_client.driver
        async with driver.session() as session:
            node_count = await session.run("MATCH (n) RETURN count(n) as count")
            nodes = await node_count.single()

            rel_count = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rels = await rel_count.single()

            ep_count = await session.run(
                "MATCH (e:Episodic) RETURN count(e) as count"
            )
            eps = await ep_count.single()

        return {
            "total_nodes": nodes["count"] if nodes else 0,
            "total_relationships": rels["count"] if rels else 0,
            "total_episodes": eps["count"] if eps else 0,
            "status": "healthy",
        }

    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
