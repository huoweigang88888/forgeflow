"""
ForgeFlow AI - Prompt Management API Routes.

Endpoints for managing prompt versions, A/B tests, and rollback.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from forgeflow.db.session import DBSession
from forgeflow.prompts.registry import PromptRegistry

router = APIRouter(prefix="/prompts", tags=["prompts"])


# =============================================================================
# Schemas
# =============================================================================


class PromptRegisterRequest(BaseModel):
    """Register a new prompt version."""

    prompt_name: str = Field(..., min_length=1, max_length=100)
    version: str = Field(..., min_length=1, max_length=20)
    template: str = Field(..., min_length=10)
    description: str = ""
    activate: bool = False


class PromptRollbackRequest(BaseModel):
    """Rollback to a previous version."""

    prompt_name: str
    to_version: str


class ABTestStartRequest(BaseModel):
    """Start an A/B test."""

    prompt_name: str
    control_version: str
    variant_version: str
    traffic_split: float = Field(default=0.5, ge=0.01, le=1.0)


# =============================================================================
# Routes
# =============================================================================


@router.get("/")
async def list_prompt_names(db: DBSession) -> dict[str, Any]:
    """List all prompt names that have registered versions."""
    registry = PromptRegistry(db)
    _ = registry  # Initialized for future use — will query distinct prompt_names
    return {
        "prompts": [
            {"name": "intent_detection", "description": "Intent classification (6-class)"},
            {"name": "decision", "description": "Decision making (action + approval)"},
            {"name": "policy_check", "description": "Policy relevance matching"},
        ]
    }


@router.get("/{prompt_name}/versions")
async def list_versions(
    prompt_name: str,
    db: DBSession,
):
    """List all versions for a given prompt."""
    registry = PromptRegistry(db)
    return await registry.list_versions(prompt_name)


@router.post("/register")
async def register_prompt(
    body: PromptRegisterRequest,
    db: DBSession,
):
    """Register a new prompt version. If activate=True, becomes active."""
    registry = PromptRegistry(db)
    pv = await registry.register(
        prompt_name=body.prompt_name,
        version=body.version,
        template=body.template,
        description=body.description,
        activate=body.activate,
    )
    return {
        "code": 0,
        "message": f"Prompt '{body.prompt_name}' v{body.version} registered",
        "data": {
            "prompt_name": pv.prompt_name,
            "version": pv.version,
            "is_active": pv.is_active,
            "created_at": pv.created_at.isoformat() if pv.created_at else None,
        },
    }


@router.post("/rollback")
async def rollback_prompt(
    body: PromptRollbackRequest,
    db: DBSession,
):
    """Rollback a prompt to a previous version and activate it."""
    registry = PromptRegistry(db)
    try:
        pv = await registry.rollback(body.prompt_name, body.to_version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "code": 0,
        "message": f"Prompt '{body.prompt_name}' rolled back to v{body.to_version}",
        "data": {
            "prompt_name": pv.prompt_name,
            "version": pv.version,
            "is_active": pv.is_active,
        },
    }


@router.post("/ab-test/start")
async def start_ab_test(
    body: ABTestStartRequest,
    db: DBSession,
):
    """Start an A/B test for a prompt with hash-based traffic splitting."""
    registry = PromptRegistry(db)

    # Verify both versions exist
    control = await registry.get_version(body.prompt_name, body.control_version)
    variant = await registry.get_version(body.prompt_name, body.variant_version)
    if control is None:
        raise HTTPException(
            status_code=404,
            detail=f"Control version '{body.control_version}' not found",
        )
    if variant is None:
        raise HTTPException(
            status_code=404,
            detail=f"Variant version '{body.variant_version}' not found",
        )

    config = await registry.start_ab_test(
        prompt_name=body.prompt_name,
        control_version=body.control_version,
        variant_version=body.variant_version,
        traffic_split=body.traffic_split,
    )

    return {
        "code": 0,
        "message": f"A/B test started for '{body.prompt_name}'",
        "data": config,
    }


@router.post("/ab-test/stop")
async def stop_ab_test(
    db: DBSession,
    prompt_name: str = Query(..., description="Prompt name to stop A/B test for"),
):
    """Stop an active A/B test."""
    registry = PromptRegistry(db)
    await registry.stop_ab_test(prompt_name)
    return {
        "code": 0,
        "message": f"A/B test stopped for '{prompt_name}'",
    }


@router.post("/seed")
async def seed_default_prompts(
    db: DBSession,
):
    """Seed the database with default prompt templates from code."""
    registry = PromptRegistry(db)
    created = await registry.seed_default_prompts()
    return {
        "code": 0,
        "message": f"Seeded {len(created)} default prompts",
        "data": [
            {"prompt_name": p.prompt_name, "version": p.version}
            for p in created
        ],
    }


@router.get("/{prompt_name}/preview")
async def preview_prompt(
    db: DBSession,
    prompt_name: str,
    version: str = Query(default="latest", description="Version or 'latest'"),
):
    """Preview a rendered prompt template."""
    registry = PromptRegistry(db)

    if version == "latest":
        rendered = await registry.get_active(prompt_name)
    else:
        rendered = await registry.get_version(prompt_name, version)
        if rendered is None:
            raise HTTPException(
                status_code=404,
                detail=f"Version '{version}' of '{prompt_name}' not found",
            )

    return {
        "code": 0,
        "data": {
            "prompt_name": rendered.prompt_name,
            "version": rendered.version,
            "template": rendered.rendered,
        },
    }
