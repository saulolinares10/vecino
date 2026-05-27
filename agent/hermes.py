"""
Hermes — lightweight agent framework.

Handles tool registration, WhatsApp gateway integration, skill loading
from markdown files, and an event hook system. The framework itself has
no direct dependency on any application-specific storage — memory hooks
are registered by the host application (main.py).
"""
from __future__ import annotations

import inspect
import json
import os
import types as _types
from pathlib import Path
from typing import Any, Callable, get_type_hints

import anthropic
from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


class HermesAgent:
    def __init__(
        self,
        name: str,
        model: str = "claude-sonnet-4-6",
        skills_dir: str | None = None,
        system_file: str | None = None,
    ):
        self.name = name
        self.model = model
        self._tools: list[dict] = []
        self._tool_fns: dict[str, Callable] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._interaction_counts: dict[str, int] = {}
        self._skills_context = _load_skills(skills_dir) if skills_dir else ""
        self._system = (
            Path(system_file).read_text(encoding="utf-8")
            if system_file and Path(system_file).exists()
            else ""
        )

    # ── Tool registration ──────────────────────────────────────────────────

    def tool(self, fn: Callable) -> Callable:
        """Decorator: register a Python function as a Claude tool."""
        self._tools.append(_fn_to_tool_schema(fn))
        self._tool_fns[fn.__name__] = fn
        return fn

    # ── Event hooks ────────────────────────────────────────────────────────

    def on(self, event: str):
        """Decorator: register a hook function for a named event."""
        def decorator(fn: Callable) -> Callable:
            self._hooks.setdefault(event, []).append(fn)
            return fn
        return decorator

    def fire(self, event: str, **kwargs) -> None:
        """Dispatch an event to all registered hooks. Exceptions are swallowed."""
        for fn in self._hooks.get(event, []):
            try:
                fn(**kwargs)
            except Exception:
                pass

    # ── Agentic loop ───────────────────────────────────────────────────────

    def run(self, message: str, sender: str) -> str:
        """
        Process one WhatsApp message through the agentic tool-use loop.
        Returns the final reply text.
        """
        count = self._interaction_counts.get(sender, 0) + 1
        self._interaction_counts[sender] = count
        if count % 15 == 0:
            self.fire("skill:accumulate", sender=sender, count=count)

        self.fire("message:received", sender=sender, body=message)

        system = self._build_system()
        messages: list[dict] = [{"role": "user", "content": message}]

        while True:
            response = _get_client().messages.create(
                model=self.model,
                max_tokens=512,
                system=system,
                tools=self._tools or anthropic.NOT_GIVEN,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text = _extract_text(response)
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._invoke(block.name, block.input)
                        common = dict(tool=block.name, input=block.input, result=result)
                        self.fire("tool:called", **common)
                        self.fire(f"after:{block.name}", **common)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            text = _extract_text(response)
            break

        self.fire("message:sent", sender=sender, body=text)
        return text

    def _invoke(self, name: str, inputs: dict) -> Any:
        fn = self._tool_fns.get(name)
        if not fn:
            return {"error": f"unknown tool: {name}"}
        try:
            return fn(**inputs)
        except Exception as exc:
            return {"error": str(exc)}

    def _build_system(self) -> str:
        parts = []
        if self._system:
            parts.append(self._system)
        if self._skills_context:
            parts.append("## Habilidades disponibles\n\n" + self._skills_context)
        return "\n\n".join(parts)

    # ── WhatsApp gateway ───────────────────────────────────────────────────

    def mount(self, app: FastAPI) -> None:
        """Mount the WhatsApp webhook onto an existing FastAPI app."""
        import asyncio
        agent = self

        @app.post("/webhook")
        async def whatsapp_webhook(
            Body: str = Form(default=""),
            From: str = Form(default=""),
        ):
            reply = await asyncio.to_thread(agent.run, Body.strip(), From.strip())
            resp = MessagingResponse()
            resp.message(reply)
            return Response(content=str(resp), media_type="application/xml")


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_skills(skills_dir: str) -> str:
    """Load all *.md files from skills_dir, strip YAML frontmatter, join with separators."""
    path = Path(skills_dir)
    if not path.exists():
        return ""
    texts = []
    for md in sorted(path.glob("*.md")):
        content = md.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            texts.append(parts[2].strip() if len(parts) > 2 else content)
        else:
            texts.append(content)
    return "\n\n---\n\n".join(texts)


def _extract_text(response: anthropic.types.Message) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text.strip()
    return ""


def _fn_to_tool_schema(fn: Callable) -> dict:
    """Build a Claude tool JSON schema from a Python function's type hints and docstring."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    sig = inspect.signature(fn)
    props: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        props[pname] = {"type": _hint_to_json_type(hints.get(pname, Any))}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "name": fn.__name__,
        "description": (fn.__doc__ or "").strip(),
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


def _hint_to_json_type(hint: Any) -> str:
    import typing
    # Python 3.10+ union syntax: X | Y
    if hasattr(_types, "UnionType") and isinstance(hint, _types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return _hint_to_json_type(args[0]) if args else "string"
    # typing.Union / typing.Optional
    if typing.get_origin(hint) is typing.Union:
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return _hint_to_json_type(args[0]) if args else "string"
    return {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }.get(hint, "string")
