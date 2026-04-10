"""Server-synced chat conversations (GET/PUT/POST/DELETE /v1/user/conversations)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.infrastructure.auth import get_current_user
from src.infrastructure.conversations_db import (
    conversation_create,
    conversation_delete,
    conversation_get,
    conversation_replace,
    conversations_list,
)

router = APIRouter(prefix="/v1/user/conversations", tags=["conversations"])


class MessageItem(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: Any = ""  # str or OpenAI multimodal list


class ConversationCreateBody(BaseModel):
    title: str = Field(default="", max_length=500)
    mode: Literal["chat", "agent"] = "chat"
    model: str = Field(default="", max_length=512)
    messages: list[MessageItem] = Field(default_factory=list)
    agent_log: list[Any] = Field(default_factory=list)


class ConversationUpdateBody(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    mode: Literal["chat", "agent"] | None = None
    model: str | None = Field(default=None, max_length=512)
    messages: list[MessageItem] | None = None
    agent_log: list[Any] | None = None


@router.get("")
async def list_conversations(request: Request):
    user = await get_current_user(request)
    return {"ok": True, "conversations": conversations_list(user.id)}


@router.post("")
async def create_conversation(request: Request, body: ConversationCreateBody):
    user = await get_current_user(request)
    data = conversation_create(
        user.id,
        title=body.title,
        mode=body.mode,
        model=body.model,
        messages=[m.model_dump() for m in body.messages],
        agent_log=body.agent_log,
    )
    return {"ok": True, "conversation": data}


@router.get("/{conversation_id}")
async def get_conversation(request: Request, conversation_id: uuid.UUID):
    user = await get_current_user(request)
    data = conversation_get(user.id, conversation_id)
    if not data:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "conversation": data}


@router.put("/{conversation_id}")
async def put_conversation(
    request: Request, conversation_id: uuid.UUID, body: ConversationUpdateBody
):
    user = await get_current_user(request)
    msgs = None
    if body.messages is not None:
        msgs = [m.model_dump() for m in body.messages]
    data = conversation_replace(
        user.id,
        conversation_id,
        title=body.title,
        mode=body.mode,
        model=body.model,
        messages=msgs,
        agent_log=body.agent_log,
    )
    if not data:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "conversation": data}


@router.delete("/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: uuid.UUID):
    user = await get_current_user(request)
    if not conversation_delete(user.id, conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "deleted": True}
