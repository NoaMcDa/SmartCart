"""Shared lists (issue #34). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(tags=["shares"])


@router.post("/me/lists/{list_id}/share", response_model=schemas.ShareInvite, status_code=201)
def share_list(list_id: int, body: schemas.ShareRequest) -> schemas.ShareInvite:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.get("/me/lists/{list_id}/members", response_model=list[schemas.ListMember])
def list_members(list_id: int) -> list[schemas.ListMember]:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/lists/accept/{token}", response_model=schemas.ShoppingList)
def accept_share(token: str) -> schemas.ShoppingList:
    raise HTTPException(status_code=501, detail="not implemented yet")
