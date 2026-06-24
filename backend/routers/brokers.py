"""
Broker connections router — per-user BYO-broker API key management.

Keys are write-only from the client's perspective:
  POST /api/brokers      — add/update a connection (sends key once, encrypted at rest)
  GET  /api/brokers      — list connections (metadata only, never returns keys)
  DELETE /api/brokers/{id} — remove a connection
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from routers.auth import get_current_user
from services.broker_service import (
    save_broker_connection,
    list_broker_connections,
    delete_broker_connection,
)

router = APIRouter(prefix="/api/brokers", tags=["brokers"])

VALID_BROKERS = {"oanda", "binance", "coinbase"}
VALID_ENVIRONMENTS = {"practice", "live"}


class BrokerConnectionRequest(BaseModel):
    broker: str
    environment: str = "practice"
    api_key: str
    api_secret: Optional[str] = None
    account_id: Optional[str] = None

    @field_validator("broker")
    @classmethod
    def broker_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_BROKERS:
            raise ValueError(f"broker must be one of: {', '.join(sorted(VALID_BROKERS))}")
        return v

    @field_validator("environment")
    @classmethod
    def env_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_ENVIRONMENTS:
            raise ValueError(f"environment must be 'practice' or 'live'")
        return v

    @field_validator("api_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("api_key must not be empty")
        return v.strip()


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_broker_connection(
    req: BrokerConnectionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    connection_id = await save_broker_connection(
        db=db,
        user_id=str(current_user["id"]),
        broker=req.broker,
        environment=req.environment,
        api_key=req.api_key,
        api_secret=req.api_secret,
        account_id=req.account_id,
    )
    return {
        "id": connection_id,
        "broker": req.broker,
        "environment": req.environment,
        "status": "saved",
    }


@router.get("")
async def get_broker_connections(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    connections = await list_broker_connections(db, str(current_user["id"]))
    # Stringify UUIDs and datetimes for JSON serialisation
    return [
        {**c, "id": str(c["id"]),
         "created_at": c["created_at"].isoformat() if c["created_at"] else None,
         "updated_at": c["updated_at"].isoformat() if c["updated_at"] else None}
        for c in connections
    ]


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_broker_connection(
    connection_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_broker_connection(db, connection_id, str(current_user["id"]))
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
