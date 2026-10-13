"""LLM adapter: same LlmChat interface on Emergent and Azure OpenAI (keyless)."""
import types

import pytest

from services import llm_provider
from services.llm_provider import LlmChat, StreamDone, TextDelta, UserMessage, llm_configured


class FakeAzureBackend:
    def __init__(self, replies=("Namaste!",), pieces=("Hel", "lo")):
        self.replies, self.pieces, self.calls = list(replies), pieces, []

    async def complete(self, messages):
        self.calls.append(messages)
        return self.replies.pop(0)

    async def stream(self, messages):
        self.calls.append(messages)
        for piece in self.pieces:
            yield piece


async def test_send_message_includes_system_prompt_and_keeps_dialogue():
    backend = FakeAzureBackend(replies=["first", "second"])
    chat = LlmChat(api_key="ignored", session_id="s1", system_message="You are AirYatra.", backend=backend)
    assert chat.with_model("openai", "gpt-5.4") is chat
    assert await chat.send_message(UserMessage(text="Hi")) == "first"
    assert await chat.send_message(UserMessage(text="Fare to Shirdi?")) == "second"
    assert backend.calls[1] == [
        {"role": "system", "content": "You are AirYatra."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "first"},
        {"role": "user", "content": "Fare to Shirdi?"},
    ]


async def test_stream_yields_text_deltas_then_done():
    chat = LlmChat(system_message="", backend=FakeAzureBackend())
    events = [event async for event in chat.stream_message(UserMessage(text="Hi"))]
    assert events == [TextDelta(content="Hel"), TextDelta(content="lo"), StreamDone()]
    assert chat.history[-1] == {"role": "assistant", "content": "Hello"}


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("stream"):
            async def gen():
                for text in ("a", None, "b"):
                    delta = types.SimpleNamespace(content=text)
                    yield types.SimpleNamespace(choices=[types.SimpleNamespace(delta=delta)])
                yield types.SimpleNamespace(choices=[])
            return gen()
        message = types.SimpleNamespace(content="ok")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


async def test_azure_backend_uses_the_deployment_as_model():
    completions = FakeCompletions()
    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))
    backend = llm_provider._AzureOpenAIBackend(client=client, deployment="airyatra-chat")
    assert await backend.complete([{"role": "user", "content": "x"}]) == "ok"
    assert completions.kwargs["model"] == "airyatra-chat"
    assert [p async for p in backend.stream([])] == ["a", "b"]


def test_configuration_checks(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    assert not llm_configured()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://oai.example.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "airyatra-chat")
    assert llm_configured()
    monkeypatch.setenv("LLM_PROVIDER", "emergent")
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    assert not llm_configured()
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert not llm_configured()
    with pytest.raises(llm_provider.LlmNotConfiguredError):
        LlmChat()


def test_azure_client_needs_endpoint(monkeypatch):
    monkeypatch.setattr(llm_provider._AzureOpenAIBackend, "_client", None)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    with pytest.raises(llm_provider.LlmNotConfiguredError):
        llm_provider._AzureOpenAIBackend()
