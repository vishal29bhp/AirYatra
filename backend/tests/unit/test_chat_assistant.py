"""Website chat assistant: open to visitors, Maharashtra only, no made-up fares, own history only."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.llm_provider as llm_provider
from database import get_database
from middleware import get_optional_user
from routes import ai_routes
from security_middleware import limiter
from services.chat_assistant import history_text, system_prompt


class FakeChat:
    """Stands in for LlmChat and records what the route sent."""
    last = None

    def __init__(self, api_key=None, session_id=None, system_message=""):
        self.system_message = system_message
        self.sent = None
        FakeChat.last = self

    def with_model(self, provider, model):
        return self

    async def stream_message(self, message):
        self.sent = message.text
        yield llm_provider.TextDelta(content="Namaskar! ")
        yield llm_provider.TextDelta(content="We fly within Maharashtra.")
        yield llm_provider.StreamDone()


@pytest.fixture
def client(mock_db, monkeypatch):
    monkeypatch.setattr(llm_provider, "LlmChat", FakeChat)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(ai_routes.router, prefix="/api")
    app.dependency_overrides[get_database] = lambda: mock_db
    return app


def stream(app, user=None, **body):
    app.dependency_overrides[get_optional_user] = lambda: user
    response = TestClient(app).post("/api/ai/chat/stream", json=body)
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    return response, events


def test_prompt_limits_service_to_maharashtra_and_forbids_quoting_fares():
    prompt = system_prompt("Asha", "")
    assert "only within Maharashtra" in prompt
    assert "Do not quote prices" in prompt
    assert "Customer name: Asha" in prompt


def test_history_text_keeps_the_last_ten_turns():
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(14)]
    text = history_text(messages)
    assert text.splitlines()[0] == "Customer: m4" and text.splitlines()[-1] == "Assistant: m13"


def test_visitor_without_sign_in_gets_an_answer(client, mock_db):
    response, events = stream(client, message="Mumbai to Shirdi?")

    assert response.status_code == 200
    assert "".join(e.get("delta", "") for e in events) == "Namaskar! We fly within Maharashtra."
    assert events[-1]["done"] is True
    assert "Customer name: Guest" in FakeChat.last.system_message


async def test_conversation_is_saved_for_the_caller(client, mock_db):
    _, events = stream(client, user={"id": "u1", "full_name": "Asha"}, message="Hello")
    conversation_id = events[-1]["conversation_id"]

    saved = await mock_db.ai_chat_history.find({"conversation_id": conversation_id}).to_list(10)
    assert [(m["role"], m["user_id"]) for m in saved] == [("user", "u1"), ("assistant", "u1")]


async def test_someone_elses_conversation_never_reaches_the_prompt(client, mock_db):
    await mock_db.ai_chat_history.insert_one(
        {"conversation_id": "c1", "user_id": "u1", "role": "user", "content": "my secret PNR", "created_at": "1"})

    stream(client, user={"id": "u2", "full_name": "Ravi"}, message="Hi", conversation_id="c1")

    assert "my secret PNR" not in FakeChat.last.system_message


def test_long_messages_are_trimmed(client):
    stream(client, message="x" * 5000)
    assert len(FakeChat.last.sent) == 2000
