"""Personalization data, ``/me/personal`` (phase 3): the person's own habits, under row-level security.

What the web app learns from a person's own lists and finished shopping trips (the items bought
often, how often, the quantity usually taken, how many times an exact brand was kept or a
substitute turned down in a category) and two preferences (learning on or off, prefer value
packs). It lives on the device first. A signed-in browser also keeps one copy here, so a second
device shows the same "my usual" list and "buy again" suggestions; an anonymous visitor never
reaches this route and nothing leaves their device.

* ``GET /me/personal`` returns the stored document, or the defaults with ``exists = false``.
* ``PUT /me/personal`` replaces it. The document is typed and bounded (see ``schemas.PersonalData``
  and the 256 KB body limit); there is no free text beyond the product names the person's own
  list already carried.
* ``DELETE /me/personal`` erases it ("clear what you learned", and a step of "delete my data").
  ``DELETE /me`` erases it too, with the rest of the ``preferences`` row.

It is stored in ``preferences.data -> 'personal'``, a table that was already owner-only under RLS
and already removed by ``DELETE /me``; there is no migration. Nothing reads it but its owner: it is
never used for ranking, never joined to another table, never exported to analytics (the
``personalization`` event carries a kind and an action, no product and no category), and never sold.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Response
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from smartcart_api import schemas
from smartcart_api.auth import User, user_conn

router = APIRouter(prefix="/me/personal", tags=["me"])
UserConn = Annotated[tuple[User, psycopg.Connection], Depends(user_conn, scope="function")]


def _state(data: object) -> schemas.PersonalState:
    if isinstance(data, dict):
        try:
            return schemas.PersonalState(exists=True, **data)
        except ValidationError:
            pass  # a document an older or newer client wrote: treated as not stored
    return schemas.PersonalState(exists=False)


@router.get("", response_model=schemas.PersonalState)
def get_personal(uc: UserConn) -> schemas.PersonalState:
    user, conn = uc
    row = conn.execute(
        "SELECT data -> 'personal' FROM preferences WHERE user_id = %s", (user.id,)
    ).fetchone()
    return _state(row[0] if row else None)


@router.put("", response_model=schemas.PersonalState)
def put_personal(body: schemas.PersonalData, uc: UserConn) -> schemas.PersonalState:
    user, conn = uc
    doc = body.model_dump(mode="json")
    row = conn.execute(
        "INSERT INTO preferences (user_id, data)"
        " VALUES (%(uid)s, jsonb_build_object('personal', %(doc)s::jsonb))"
        " ON CONFLICT (user_id) DO UPDATE SET"
        " data = preferences.data || jsonb_build_object('personal', EXCLUDED.data -> 'personal'),"
        " updated_at = now() RETURNING data -> 'personal'",
        {"uid": user.id, "doc": Jsonb(doc)},
    ).fetchone()
    return _state(row[0] if row else None)


@router.delete("", status_code=204)
def delete_personal(uc: UserConn) -> Response:
    user, conn = uc
    conn.execute(
        "UPDATE preferences SET data = data - 'personal', updated_at = now() WHERE user_id = %s",
        (user.id,),
    )
    return Response(status_code=204)
