"""Price-drop alerts and push subscriptions (issue #23). Implemented by workstream P2-A."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from smartcart_api import schemas

router = APIRouter(prefix="/me", tags=["alerts"])


@router.get("/alerts", response_model=list[schemas.PriceAlert])
def list_alerts() -> list[schemas.PriceAlert]:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/alerts", response_model=schemas.PriceAlert, status_code=201)
def create_alert(body: schemas.PriceAlertIn) -> schemas.PriceAlert:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int) -> None:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/push-subscriptions", response_model=schemas.Ack, status_code=201)
def add_push_subscription(body: schemas.PushSubscriptionIn) -> schemas.Ack:
    raise HTTPException(status_code=501, detail="not implemented yet")
