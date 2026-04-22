from __future__ import annotations

import asyncio
import contextlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.services.chat_stream_service import stream_chat_events
from schemas.ws_schema import (
    CancelWebSocketRequest,
    ChatWebSocketRequest,
    ErrorEvent,
    ToolCallEvent,
)
from utils.auth_utils import decode_access_token

router = APIRouter(tags=["WebSocket Chat"])


async def _send_error(
    websocket: WebSocket,
    message: str,
    *,
    code: str,
    request_id: str | None = None,
    details: dict | None = None,
) -> None:
    error_payload = ErrorEvent(
        message=message,
        code=code,
        request_id=request_id,
        details=details,
    )
    await websocket.send_json(error_payload.model_dump(exclude_none=True))


async def _run_stream_task(
    websocket: WebSocket,
    request: ChatWebSocketRequest,
    user_email: str,
    request_id: str,
) -> None:
    try:
        async for event in stream_chat_events(request, user_email):
            event["request_id"] = request_id
            await websocket.send_json(event)
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        await _send_error(
            websocket,
            str(exc),
            code="stream_error",
            request_id=request_id,
        )


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token", "")
    try:
        user_email = decode_access_token(token)
    except HTTPException:
        await _send_error(
            websocket,
            "Invalid or expired token.",
            code="unauthorized",
        )
        await websocket.close(code=4401)
        return

    active_task: asyncio.Task | None = None
    active_request_id: str | None = None

    while True:
        if active_task and active_task.done():
            try:
                active_task.result()
            except asyncio.CancelledError:
                pass
            except WebSocketDisconnect:
                break
            except Exception as exc:
                await _send_error(
                    websocket,
                    str(exc),
                    code="stream_error",
                    request_id=active_request_id,
                )
            finally:
                active_task = None
                active_request_id = None

        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            if active_task and not active_task.done():
                active_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await active_task
            break
        except Exception as exc:
            await _send_error(
                websocket,
                f"Invalid JSON payload: {exc}",
                code="invalid_payload",
            )
            continue

        message_type = payload.get("type", "start")

        if message_type == "cancel":
            try:
                cancel = CancelWebSocketRequest.model_validate(payload)
            except ValidationError as exc:
                await _send_error(
                    websocket,
                    "Cancel request validation failed.",
                    code="validation_error",
                    details={"errors": exc.errors()},
                )
                continue

            if not active_task or active_task.done():
                await _send_error(
                    websocket,
                    "No active generation to cancel.",
                    code="no_active_generation",
                    request_id=cancel.request_id,
                )
                continue

            if cancel.request_id and active_request_id != cancel.request_id:
                await _send_error(
                    websocket,
                    "Request ID does not match active generation.",
                    code="request_mismatch",
                    request_id=cancel.request_id,
                )
                continue

            active_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await active_task

            cancelled_event = ToolCallEvent(
                request_id=active_request_id,
                name="generation",
                status="cancelled",
                payload={"request_id": active_request_id},
            )
            await websocket.send_json(cancelled_event.model_dump(exclude_none=True))
            active_task = None
            active_request_id = None
            continue

        if message_type != "start":
            await _send_error(
                websocket,
                f"Unsupported message type: {message_type}",
                code="unsupported_message_type",
            )
            continue

        if active_task and not active_task.done():
            await _send_error(
                websocket,
                "Another generation is already running.",
                code="generation_in_progress",
            )
            continue

        try:
            request = ChatWebSocketRequest.model_validate(payload)
        except ValidationError as exc:
            await _send_error(
                websocket,
                "Request validation failed.",
                code="validation_error",
                details={"errors": exc.errors()},
            )
            continue

        active_request_id = request.request_id or str(uuid4())
        active_task = asyncio.create_task(
            _run_stream_task(
                websocket=websocket,
                request=request,
                user_email=user_email,
                request_id=active_request_id,
            )
        )

