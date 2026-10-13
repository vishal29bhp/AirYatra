"""Booking chat socket: only the booking's customer, operator or an admin may join, and identity comes from the
token (threat model L13, abuse case 10). Fan-out reaches sockets on every replica through Redis pub/sub."""
import asyncio

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import middleware
from auth import create_access_token
from routes import websocket_chat_routes as ws_routes
from services import redis_client

CUSTOMER = {"id": "cust-1", "email": "c@example.com", "full_name": "Asha Rao", "roles": ["customer"]}
OTHER_CUSTOMER = {"id": "cust-2", "email": "o@example.com", "full_name": "Other", "roles": ["customer"]}
OPERATOR_USER = {"id": "op-user-1", "email": "op@example.com", "full_name": "Sky Ops", "roles": ["operator"]}
ADMIN = {"id": "admin-1", "email": "a@example.com", "full_name": "Admin", "roles": ["admin"]}
BOOKING = {"id": "bk-1", "customer_id": "cust-1", "operator_id": "op-1"}


def token_for(user):
    return create_access_token({"sub": user["id"], "roles": user["roles"]})


@pytest.fixture
def chat(mock_db, monkeypatch):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(mock_db.users.insert_many([dict(u) for u in (CUSTOMER, OTHER_CUSTOMER, OPERATOR_USER, ADMIN)]))
    loop.run_until_complete(mock_db.operators.insert_one({"id": "op-1", "user_id": "op-user-1"}))
    loop.run_until_complete(mock_db.bookings.insert_one(dict(BOOKING)))
    loop.close()
    monkeypatch.setattr(middleware, "get_database", lambda: mock_db)
    monkeypatch.setattr(ws_routes, "get_database", lambda: mock_db)
    monkeypatch.setattr(ws_routes, "manager", ws_routes.ConnectionManager())
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    redis_client.set_client_for_tests(None)

    app = FastAPI()
    app.include_router(ws_routes.router, prefix="/api")
    return TestClient(app), mock_db


def _refused(client, url):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(url) as ws:
            ws.receive_json()
    return exc.value.code


def test_socket_without_token_is_refused(chat):
    client, _ = chat
    assert _refused(client, "/api/ws/chat/bk-1") == ws_routes.WS_POLICY_VIOLATION


def test_socket_with_invalid_token_is_refused(chat):
    client, _ = chat
    assert _refused(client, "/api/ws/chat/bk-1?token=not-a-jwt") == ws_routes.WS_POLICY_VIOLATION


def test_other_customers_booking_is_refused(chat):
    client, _ = chat
    assert _refused(client, f"/api/ws/chat/bk-1?token={token_for(OTHER_CUSTOMER)}") == ws_routes.WS_POLICY_VIOLATION


def test_unknown_booking_is_refused(chat):
    client, _ = chat
    assert _refused(client, f"/api/ws/chat/missing?token={token_for(CUSTOMER)}") == ws_routes.WS_POLICY_VIOLATION


@pytest.mark.parametrize("user", [CUSTOMER, OPERATOR_USER, ADMIN])
def test_booking_participants_can_join(chat, user):
    client, _ = chat
    with client.websocket_connect(f"/api/ws/chat/bk-1?token={token_for(user)}") as ws:
        welcome = ws.receive_json()
    assert welcome["type"] == "system"
    assert welcome["online_users"][0]["id"] == user["id"]


def test_sender_identity_comes_from_the_token_not_the_query(chat):
    client, db = chat
    url = f"/api/ws/chat/bk-1?token={token_for(CUSTOMER)}&user_id=admin-1&name=Admin&type=admin"
    with client.websocket_connect(url) as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "text": "hello"})
        event = ws.receive_json()
    assert event["type"] == "chat"
    message = event["message"]
    assert (message["sender_id"], message["sender_name"], message["sender_type"]) == ("cust-1", "Asha Rao", "customer")
    saved = asyncio.new_event_loop().run_until_complete(db.chat_messages.find_one({"id": message["id"]}))
    assert saved["sender_id"] == "cust-1" and saved["message"] == "hello"


def test_cookie_token_is_accepted(chat):
    client, _ = chat
    client.cookies.set("access_token", token_for(CUSTOMER))
    with client.websocket_connect("/api/ws/chat/bk-1") as ws:
        assert ws.receive_json()["type"] == "system"


def test_oversized_and_empty_messages_are_rejected(chat):
    client, _ = chat
    with client.websocket_connect(f"/api/ws/chat/bk-1?token={token_for(CUSTOMER)}") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "text": "x" * (ws_routes.MAX_MESSAGE_CHARS + 1)})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "chat", "text": "   "})
        assert ws.receive_json()["type"] == "error"


def test_read_receipts_only_touch_this_bookings_messages(chat):
    client, db = chat
    loop = asyncio.new_event_loop()
    loop.run_until_complete(db.chat_messages.insert_many([
        {"id": "m-mine", "booking_id": "bk-1", "read": False},
        {"id": "m-other", "booking_id": "bk-2", "read": False},
    ]))
    with client.websocket_connect(f"/api/ws/chat/bk-1?token={token_for(CUSTOMER)}") as ws:
        ws.receive_json()
        ws.send_json({"type": "read", "message_ids": ["m-mine", "m-other"]})
        assert ws.receive_json()["type"] == "read_receipt"
    assert loop.run_until_complete(db.chat_messages.find_one({"id": "m-mine"}))["read"] is True
    assert loop.run_until_complete(db.chat_messages.find_one({"id": "m-other"}))["read"] is False
    loop.close()


def test_message_flood_is_throttled():
    budget = ws_routes._MessageBudget()
    results = [budget.take() for _ in range(ws_routes.MESSAGE_BURST + 5)]
    assert results[:ws_routes.MESSAGE_BURST] == [True] * ws_routes.MESSAGE_BURST
    assert results[-1] is False


# ---------------- fan-out across replicas ----------------

class FakeSocket:
    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, message):
        self.sent.append(message)


async def _wait_for(predicate, timeout=2.0):
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return False


async def test_broadcast_reaches_sockets_on_every_replica():
    redis_client.set_client_for_tests(fakeredis.FakeAsyncRedis(decode_responses=True))
    replica_a, replica_b = ws_routes.ConnectionManager(), ws_routes.ConnectionManager()
    sender, other_on_a, on_b = FakeSocket(), FakeSocket(), FakeSocket()
    try:
        sender_id = await replica_a.connect(sender, "bk-1", {"id": "cust-1"})
        await replica_a.connect(other_on_a, "bk-1", {"id": "admin-1"})
        await replica_b.connect(on_b, "bk-1", {"id": "op-user-1"})

        await replica_a.broadcast_to_booking("bk-1", {"type": "typing"}, exclude=sender_id)

        assert await _wait_for(lambda: on_b.sent and other_on_a.sent)
        assert on_b.sent == [{"type": "typing"}] and other_on_a.sent == [{"type": "typing"}]
        assert sender.sent == []  # excluded on its own replica
    finally:
        for manager in (replica_a, replica_b):
            manager._listener.cancel()
        redis_client.set_client_for_tests(None)


async def test_without_redis_broadcast_is_local():
    redis_client.set_client_for_tests(None)
    manager = ws_routes.ConnectionManager()
    socket = FakeSocket()
    await manager.connect(socket, "bk-1", {"id": "cust-1"})
    await manager.broadcast_to_booking("bk-1", {"type": "chat"})
    assert socket.sent == [{"type": "chat"}]
    assert manager._listener is None
