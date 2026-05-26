"""
Anthropic SDK → OpenAI 兼容接口适配器。

当模型名以 'claude-' 开头时，本适配器透明地将
  client.chat.completions.create(model, messages, ...)
翻译为 Anthropic Messages API，并返回与 OpenAI 响应结构兼容的对象。

这样，路由层和 AI 模块无需感知底层 SDK 差异。

来源：AI
"""
from __future__ import annotations

from typing import Any, Generator, Iterator


# ── 响应包装器（非流式）────────────────────────────────────

class _Delta:
    def __init__(self, content: str) -> None:
        self.content = content


class _ChunkChoice:
    def __init__(self, content: str) -> None:
        self.delta = _Delta(content)


class _StreamChunk:
    """模拟 OpenAI 流式 chunk：chunk.choices[0].delta.content"""
    def __init__(self, content: str) -> None:
        self.choices = [_ChunkChoice(content)]


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    """模拟 OpenAI ChatCompletion 对象：resp.choices[0].message.content"""
    def __init__(self, content: str, model: str) -> None:
        self.choices = [_Choice(content)]
        self.model   = model


# ── 流式包装迭代器 ─────────────────────────────────────────

class _StreamWrapper:
    """
    懒惰迭代 Anthropic stream，对外暴露 OpenAI 流式接口：
      for chunk in stream:
          delta = chunk.choices[0].delta.content
    """
    def __init__(
        self,
        client: Any,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> None:
        self._client      = client
        self._model       = model
        self._system      = system
        self._messages    = messages
        self._max_tokens  = max_tokens
        self._temperature = temperature
        self._timeout     = timeout

    def __iter__(self) -> Iterator[_StreamChunk]:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=self._messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        if self._system:
            kwargs["system"] = self._system

        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if text:
                    yield _StreamChunk(text)


# ── completions 命名空间 ───────────────────────────────────

class _Completions:
    def __init__(self, client: Any) -> None:
        self._client = client

    def create(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 1.0,
        stream: bool = False,
        timeout: float = 60.0,
        **_kwargs: Any,
    ) -> Any:
        # 拆分 system 消息（Anthropic API 独立传递）
        system      = ""
        user_msgs   = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
            else:
                user_msgs.append({"role": msg["role"], "content": msg.get("content", "")})

        # Anthropic temperature 范围 0-1；clamp 防止越界
        temperature = max(0.0, min(float(temperature), 1.0))

        if stream:
            return _StreamWrapper(
                self._client, model, system, user_msgs,
                max_tokens, temperature, timeout,
            )

        # 非流式调用
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=user_msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            kwargs["system"] = system

        resp    = self._client.messages.create(**kwargs)
        content = resp.content[0].text if resp.content else ""
        return _Response(content, getattr(resp, "model", model))


class _Chat:
    def __init__(self, client: Any) -> None:
        self.completions = _Completions(client)


# ── 公开适配器类 ───────────────────────────────────────────

class AnthropicAdapter:
    """
    使用方式与 openai.OpenAI() 完全一致：
        client = AnthropicAdapter(api_key="sk-...", base_url="https://...")
        resp   = client.chat.completions.create(model="claude-sonnet-4-6", messages=[...])
    """

    def __init__(self, api_key: str, base_url: str) -> None:
        import anthropic  # 懒导入，仅在使用 Claude 模型时引入
        self._client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.chat = _Chat(self._client)
