"""Chat-completion provider behind the interface the app already uses.

The routes were written against ``emergentintegrations.llm.chat`` (``LlmChat``, ``UserMessage``,
``TextDelta``, ``StreamDone``). This module offers the same shapes so call sites only change their
import, and ``LLM_PROVIDER`` picks where requests go:

* ``emergent`` (default): the Emergent LLM gateway with ``EMERGENT_LLM_KEY``, exactly as today.
* ``azure_openai``: Azure OpenAI in Central India with the app's managed identity (no API key);
  ``AZURE_OPENAI_ENDPOINT`` and ``AZURE_OPENAI_DEPLOYMENT`` come from Terraform. The model name a
  caller asks for is ignored here: the deployment decides the model.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

PROVIDERS = ("emergent", "azure_openai")
AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"
DEFAULT_AZURE_OPENAI_API_VERSION = "2025-04-01-preview"


@dataclass
class UserMessage:
    text: str


@dataclass
class TextDelta:
    content: str


@dataclass
class StreamDone:
    pass


class LlmNotConfiguredError(RuntimeError):
    """The selected provider is missing its settings."""


def llm_provider() -> str:
    provider = os.environ.get("LLM_PROVIDER", "emergent")
    if provider not in PROVIDERS:
        raise LlmNotConfiguredError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    return provider


def llm_configured() -> bool:
    """True when the selected provider has what it needs to answer a request."""
    try:
        provider = llm_provider()
    except LlmNotConfiguredError:
        return False
    if provider == "azure_openai":
        return bool(os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_DEPLOYMENT"))
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return False
    try:
        import emergentintegrations.llm.chat  # noqa: F401
    except ImportError:
        return False
    return True


class _AzureOpenAIBackend:
    """Azure OpenAI chat completions, authenticated with Entra ID (managed identity)."""

    _client = None

    def __init__(self, client=None, deployment: Optional[str] = None):
        self.client = client or self._shared_client()
        self.deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")

    @classmethod
    def _shared_client(cls):
        if cls._client is None:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            from openai import AsyncAzureOpenAI

            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            if not endpoint:
                raise LlmNotConfiguredError("AZURE_OPENAI_ENDPOINT is not set")
            cls._client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_OPENAI_API_VERSION),
                azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), AZURE_OPENAI_SCOPE),
            )
        return cls._client

    async def complete(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(model=self.deployment, messages=messages)
        return response.choices[0].message.content or ""

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(model=self.deployment, messages=messages, stream=True)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class _EmergentBackend:
    """Today's behaviour: the Emergent gateway via the emergentintegrations SDK."""

    def __init__(self, api_key: Optional[str], session_id: Optional[str], system_message: str):
        import emergentintegrations.llm.chat as sdk

        self._sdk = sdk
        self._chat = sdk.LlmChat(
            api_key=api_key or os.environ.get("EMERGENT_LLM_KEY"),
            session_id=session_id,
            system_message=system_message,
        )

    def with_model(self, provider: str, model: str) -> None:
        self._chat = self._chat.with_model(provider, model)

    async def send(self, text: str) -> str:
        return await self._chat.send_message(self._sdk.UserMessage(text=text))

    async def stream(self, text: str) -> AsyncIterator[Any]:
        async for event in self._chat.stream_message(self._sdk.UserMessage(text=text)):
            if isinstance(event, self._sdk.TextDelta):
                yield TextDelta(content=event.content)
            elif isinstance(event, self._sdk.StreamDone):
                yield StreamDone()
                return


class LlmChat:
    """Drop-in for ``emergentintegrations.llm.chat.LlmChat`` (same constructor and methods).

    Keeps the conversation of this instance, so several ``send_message`` calls form one dialogue.
    """

    def __init__(self, api_key: Optional[str] = None, session_id: Optional[str] = None,
                 system_message: str = "", backend=None):
        self.session_id = session_id
        self.system_message = system_message
        self.history: List[Dict[str, str]] = []
        if backend is not None:
            self._backend = backend
        elif llm_provider() == "azure_openai":
            self._backend = _AzureOpenAIBackend()
        else:
            self._backend = _EmergentBackend(api_key, session_id, system_message)

    def with_model(self, provider: str, model: str) -> "LlmChat":
        if isinstance(self._backend, _EmergentBackend):
            self._backend.with_model(provider, model)
        return self

    def _messages(self, text: str) -> List[Dict[str, str]]:
        system = [{"role": "system", "content": self.system_message}] if self.system_message else []
        return system + self.history + [{"role": "user", "content": text}]

    async def send_message(self, message: UserMessage) -> str:
        if isinstance(self._backend, _EmergentBackend):
            return await self._backend.send(message.text)
        reply = await self._backend.complete(self._messages(message.text))
        self.history += [{"role": "user", "content": message.text}, {"role": "assistant", "content": reply}]
        return reply

    async def stream_message(self, message: UserMessage) -> AsyncIterator[Any]:
        if isinstance(self._backend, _EmergentBackend):
            async for event in self._backend.stream(message.text):
                yield event
            return
        parts: List[str] = []
        async for piece in self._backend.stream(self._messages(message.text)):
            parts.append(piece)
            yield TextDelta(content=piece)
        self.history += [{"role": "user", "content": message.text}, {"role": "assistant", "content": "".join(parts)}]
        yield StreamDone()
