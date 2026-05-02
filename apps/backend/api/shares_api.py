"""
Share Permissions API

Granular permission system for managing who can access what from whom.
Completely generic for all resource types - calendar, github, notes, agents etc.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.backend.infrastructure.auth import get_current_user
from apps.backend.infrastructure.db.share_permissions_db import (
    share_permission_set,
    share_permission_check,
    list_shares_by_owner,
    list_shares_by_grantee,
    list_shares_between
)

router = APIRouter(prefix="/v1/shares", tags=["shares"])


class ShareSetBody(BaseModel):
    grantee_user_id: str = Field(..., min_length=36, max_length=36)
    resource_type: str = Field(..., min_length=2, max_length=50)
    resource_identifier: str = Field(..., min_length=1, max_length=100)
    is_allowed: bool = Field(...)


@router.post("/set")
async def set_share_permission(request: Request, body: ShareSetBody):
    """Set or revoke a specific share permission."""
    user = await get_current_user(request)
    
    try:
        grantee_uuid = uuid.UUID(body.grantee_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid grantee_user_id")
    
    ok = share_permission_set(
        owner_user_id=user.id,
        grantee_user_id=grantee_uuid,
        resource_type=body.resource_type,
        resource_identifier=body.resource_identifier,
        allowed=body.is_allowed
    )
    
    if not ok:
        raise HTTPException(status_code=500, detail="could not update share permission")
    
    return {"ok": True}


@router.get("/check")
async def check_share_permission(
    request: Request,
    owner_user_id: str,
    grantee_user_id: str,
    resource_type: str,
    resource_identifier: str
):
    """Check if a specific share permission is active."""
    user = await get_current_user(request)
    
    try:
        owner_uuid = uuid.UUID(owner_user_id)
        grantee_uuid = uuid.UUID(grantee_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user id format")
    
    # Allow check only for own permissions or if user is either party
    if user.id != owner_uuid and user.id != grantee_uuid:
        raise HTTPException(status_code=403, detail="not allowed to check this permission")
    
    allowed = share_permission_check(
        owner_user_id=owner_uuid,
        grantee_user_id=grantee_uuid,
        resource_type=resource_type,
        resource_identifier=resource_identifier
    )
    
    return {"ok": True, "allowed": allowed}


@router.get("/outgoing")
async def get_outgoing_shares(request: Request):
    """List all permissions that the current user has granted to others."""
    user = await get_current_user(request)
    
    shares = list_shares_by_owner(user.id)
    
    return {
        "ok": True,
        "shares": shares
    }


@router.get("/incoming")
async def get_incoming_shares(request: Request):
    """List all permissions that others have granted to the current user."""
    user = await get_current_user(request)
    
    shares = list_shares_by_grantee(user.id)
    
    return {
        "ok": True,
        "shares": shares
    }


@router.get("/friend/{friend_user_id}")
async def get_shares_between_friends(request: Request, friend_user_id: str):
    """Get bidirectional share status between current user and another user."""
    user = await get_current_user(request)
    
    try:
        friend_uuid = uuid.UUID(friend_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid friend user id")
    
    shares = list_shares_between(user.id, friend_uuid)
    
    return {
        "ok": True,
        **shares
    }