from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
from datetime import datetime, timezone
from uuid import uuid4
import asyncio
import json
import logging
import time

from database import get_database
from middleware import get_current_user
from services.redis_client import get_redis, mark_unhealthy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket Chat"])

# Close code for "policy violation": missing/invalid token or no access to the booking.
WS_POLICY_VIOLATION = 1008
MAX_FRAME_CHARS = 16_000
MAX_MESSAGE_CHARS = 4_000
# Per-connection message budget: MESSAGES_PER_SECOND sustained, MESSAGE_BURST at once.
MESSAGES_PER_SECOND = 5
MESSAGE_BURST = 20

CHANNEL_PREFIX = "chat:booking:"
INSTANCE_ID = str(uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def can_access_booking_chat(db, user: dict, booking: dict) -> bool:
    """Same rule as GET /api/chat/messages: the booking's customer, its operator, or an admin."""
    roles = user.get("roles", [])
    if booking.get("customer_id") == user["id"]:
        return True
    if "operator" in roles:
        operator = await db.operators.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
        if operator and operator["id"] == booking.get("operator_id"):
            return True
    return "admin" in roles


def _chat_identity(user: dict) -> dict:
    roles = user.get("roles", [])
    user_type = "admin" if "admin" in roles else "operator" if "operator" in roles else "customer"
    return {
        "id": user["id"],
        "name": user.get("full_name") or user.get("name") or user.get("email") or "User",
        "type": user_type,
        "connected_at": _now(),
    }


class _MessageBudget:
    """Small token bucket so one socket cannot flood a booking's chat."""

    def __init__(self):
        self.tokens = float(MESSAGE_BURST)
        self.last = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self.tokens = min(MESSAGE_BURST, self.tokens + (now - self.last) * MESSAGES_PER_SECOND)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class ConnectionManager:
    """Chat sockets on this replica, with fan-out to every replica through Redis pub/sub.

    With Redis, a broadcast is published once and each replica (this one included) delivers it to its own
    sockets. Without Redis, or while the subscriber is down, delivery is local to this replica.
    """

    def __init__(self):
        # {booking_id: {connection_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # {connection_id: user_info}
        self.connection_users: Dict[str, dict] = {}
        self._listener: Optional[asyncio.Task] = None
        self._listener_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, booking_id: str, user_info: dict) -> str:
        await self._ensure_listener()
        await websocket.accept()
        connection_id = str(uuid4())
        self.active_connections.setdefault(booking_id, {})[connection_id] = websocket
        self.connection_users[connection_id] = user_info
        logger.info("[WS] user %s connected to booking %s", user_info["id"], booking_id)
        return connection_id

    def disconnect(self, connection_id: str, booking_id: str):
        sockets = self.active_connections.get(booking_id)
        if sockets is not None:
            sockets.pop(connection_id, None)
            if not sockets:
                del self.active_connections[booking_id]
        user = self.connection_users.pop(connection_id, None)
        if user:
            logger.info("[WS] user %s disconnected from booking %s", user["id"], booking_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("[WS] error sending message: %s", e)

    async def broadcast_to_booking(self, booking_id: str, message: dict, exclude: Optional[str] = None):
        """Send message to everyone in a booking's chat, on every replica. `exclude` is a connection id."""
        if self._listener is not None and not self._listener.done():
            redis = await get_redis()
            if redis is not None:
                try:
                    payload = {"origin": INSTANCE_ID, "exclude": exclude, "message": message}
                    await redis.publish(CHANNEL_PREFIX + booking_id, json.dumps(payload, default=str))
                    return
                except Exception as e:
                    logger.warning("[WS] publish failed, delivering locally: %s", e)
                    mark_unhealthy()
        await self._deliver_local(booking_id, message, exclude)

    async def _deliver_local(self, booking_id: str, message: dict, exclude: Optional[str] = None):
        for connection_id, connection in list(self.active_connections.get(booking_id, {}).items()):
            if connection_id == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("[WS] broadcast error: %s", e)

    def get_online_users(self, booking_id: str) -> List[dict]:
        """Users connected to this booking's chat on this replica."""
        return [self.connection_users[cid] for cid in self.active_connections.get(booking_id, {})
                if cid in self.connection_users]

    async def _ensure_listener(self):
        if self._listener is not None and not self._listener.done():
            return
        async with self._listener_lock:
            if self._listener is not None and not self._listener.done():
                return
            redis = await get_redis()
            if redis is None:
                return
            try:
                pubsub = redis.pubsub()
                await pubsub.psubscribe(CHANNEL_PREFIX + "*")
            except Exception as e:
                logger.warning("[WS] cannot subscribe to chat fan-out, delivering locally: %s", e)
                mark_unhealthy()
                return
            self._listener = asyncio.create_task(self._listen(pubsub))

    async def _listen(self, pubsub):
        try:
            async for item in pubsub.listen():
                if item.get("type") != "pmessage":
                    continue
                try:
                    payload = json.loads(item["data"])
                    booking_id = item["channel"][len(CHANNEL_PREFIX):]
                except (ValueError, KeyError, TypeError):
                    continue
                exclude = payload.get("exclude") if payload.get("origin") == INSTANCE_ID else None
                await self._deliver_local(booking_id, payload.get("message", {}), exclude)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[WS] chat fan-out subscriber stopped: %s", e)
            mark_unhealthy()
        finally:
            try:
                await pubsub.aclose()
            except Exception:  # best-effort cleanup of a broken connection
                pass


manager = ConnectionManager()


async def _authenticate(websocket: WebSocket, booking_id: str):
    """The signed-in user and their booking, or (None, None) when the socket must be refused."""
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    if not token:
        return None, None
    try:
        user = await get_current_user(token)
    except HTTPException:
        return None, None
    db = get_database()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0, "id": 1, "customer_id": 1, "operator_id": 1})
    if not booking or not await can_access_booking_chat(db, user, booking):
        return None, None
    return user, booking


@router.websocket("/ws/chat/{booking_id}")
async def websocket_chat(
    websocket: WebSocket,
    booking_id: str
):
    """
    WebSocket endpoint for real-time chat

    Connect with: ws://host/api/ws/chat/{booking_id}?token={jwt_token}
    (the access_token cookie is accepted too). Only the booking's customer, its operator and admins may
    join; sender identity always comes from the token, never from the client.
    """
    user, _ = await _authenticate(websocket, booking_id)
    if user is None:
        await websocket.close(code=WS_POLICY_VIOLATION)
        return

    user_info = _chat_identity(user)
    user_id = user_info["id"]
    budget = _MessageBudget()
    connection_id = None

    try:
        connection_id = await manager.connect(websocket, booking_id, user_info)

        # Send welcome message
        await manager.send_personal_message({
            "type": "system",
            "message": f"Connected to chat for booking {booking_id}",
            "online_users": manager.get_online_users(booking_id),
            "timestamp": _now()
        }, websocket)

        # Notify others that user joined
        await manager.broadcast_to_booking(booking_id, {
            "type": "user_joined",
            "user": user_info,
            "timestamp": _now()
        }, exclude=connection_id)

        # Listen for messages
        while True:
            data = await websocket.receive_text()

            if len(data) > MAX_FRAME_CHARS:
                await manager.send_personal_message(
                    {"type": "error", "message": "Message too large", "timestamp": _now()}, websocket)
                continue
            if not budget.take():
                await manager.send_personal_message(
                    {"type": "error", "message": "Too many messages, slow down", "timestamp": _now()}, websocket)
                continue

            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                message_data = {"text": data}
            if not isinstance(message_data, dict):
                message_data = {"text": str(message_data)}

            # Handle different message types
            msg_type = message_data.get("type", "chat")

            if msg_type == "chat":
                text = str(message_data.get("text", ""))
                if not text.strip() or len(text) > MAX_MESSAGE_CHARS:
                    await manager.send_personal_message(
                        {"type": "error", "message": "Message is empty or too long", "timestamp": _now()},
                        websocket)
                    continue
                # Save message to database
                db = get_database()
                chat_message = {
                    "id": str(uuid4()),
                    "booking_id": booking_id,
                    "sender_id": user_id,
                    "sender_name": user_info["name"],
                    "sender_type": user_info["type"],
                    "message": text,
                    "message_type": message_data.get("message_type", "text"),
                    "attachment_url": message_data.get("attachment_url"),
                    "read": False,
                    "created_at": _now()
                }
                await db.chat_messages.insert_one(chat_message)
                chat_message.pop("_id", None)

                # Broadcast to all participants
                await manager.broadcast_to_booking(booking_id, {
                    "type": "chat",
                    "message": chat_message,
                    "timestamp": _now()
                })

            elif msg_type == "typing":
                # Broadcast typing indicator
                await manager.broadcast_to_booking(booking_id, {
                    "type": "typing",
                    "user": user_info,
                    "is_typing": bool(message_data.get("is_typing", True)),
                    "timestamp": _now()
                }, exclude=connection_id)

            elif msg_type == "read":
                # Mark messages as read (only messages in this booking)
                message_ids = [str(m) for m in message_data.get("message_ids", []) if isinstance(m, (str, int))][:200]
                if message_ids:
                    db = get_database()
                    await db.chat_messages.update_many(
                        {"id": {"$in": message_ids}, "booking_id": booking_id},
                        {"$set": {"read": True, "read_at": _now()}}
                    )
                    await manager.broadcast_to_booking(booking_id, {
                        "type": "read_receipt",
                        "message_ids": message_ids,
                        "read_by": user_info,
                        "timestamp": _now()
                    })

            elif msg_type == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": _now()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(connection_id, booking_id)
        # Notify others that user left
        await manager.broadcast_to_booking(booking_id, {
            "type": "user_left",
            "user": user_info,
            "timestamp": _now()
        })
    except Exception as e:
        logger.warning("[WS] error: %s", e)
        if connection_id:
            manager.disconnect(connection_id, booking_id)
