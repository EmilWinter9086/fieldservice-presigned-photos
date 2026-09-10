from __future__ import annotations

from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Iterator
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .infrai_storage import InfraiError, InfraiStorage

BUCKET = "fieldservice-work-order-assets"
MAX_PHOTO_BYTES = 12 * 1024 * 1024


class DispatchStatus(StrEnum):
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    COMPLETED = "completed"


class FollowUp(StrEnum):
    ARRIVAL_CONFIRMATION = "arrival_confirmation"
    COMPLETION_REVIEW = "completion_review"


class PhotoUploadRequest(BaseModel):
    work_order_id: UUID
    technician_id: UUID
    dispatch_status: DispatchStatus
    filename: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    content_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    size_bytes: int = Field(gt=0, le=MAX_PHOTO_BYTES)


class PhotoUploadTicket(BaseModel):
    upload_url: str
    method: str
    object_key: str
    expires_seconds: int
    follow_up: FollowUp


def upload_policy(status: DispatchStatus) -> FollowUp:
    if status == DispatchStatus.EN_ROUTE:
        return FollowUp.ARRIVAL_CONFIRMATION
    if status == DispatchStatus.ON_SITE:
        return FollowUp.COMPLETION_REVIEW
    raise HTTPException(status_code=409, detail="Photos require an en_route or on_site dispatch")


def storage_from(request: Request) -> Iterator[InfraiStorage]:
    yield request.app.state.storage


def build_app(storage: InfraiStorage | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_storage = storage or InfraiStorage()
        try:
            active_storage.create_bucket(BUCKET)
        except InfraiError as exc:
            if exc.code != "STORAGE_BUCKET_EXISTS":
                raise
        app.state.storage = active_storage
        yield
        if storage is None:
            active_storage.close()

    app = FastAPI(title="Field-service photo uploads", lifespan=lifespan)

    @app.exception_handler(InfraiError)
    async def infrai_error_handler(_request: Request, exc: InfraiError):
        from fastapi.responses import JSONResponse

        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        return JSONResponse(status_code=status, content={"detail": exc.detail, "code": exc.code})

    @app.post("/work-orders/photo-upload", response_model=PhotoUploadTicket)
    def issue_photo_upload(
        payload: PhotoUploadRequest,
        client: InfraiStorage = Depends(storage_from),
    ) -> PhotoUploadTicket:
        follow_up = upload_policy(payload.dispatch_status)
        request_id = uuid4()
        object_key = f"work-orders/{payload.work_order_id}/{request_id}-{payload.filename}"
        signed = client.presign_put(
            BUCKET,
            object_key,
            content_type=payload.content_type,
            max_bytes=payload.size_bytes,
            idempotency_key=str(request_id),
        )
        return PhotoUploadTicket(
            upload_url=str(signed["url"]),
            method="PUT",
            object_key=object_key,
            expires_seconds=600,
            follow_up=follow_up,
        )

    return app


app = build_app()


def run() -> None:
    import uvicorn

    uvicorn.run("fieldservice_uploads.upload_service:app", host="127.0.0.1", port=8000)
