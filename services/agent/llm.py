import os
import time
from dataclasses import dataclass
from functools import lru_cache

RETRY_CODES = (429, 500, 503)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict
    thought_signature: bytes | None = None


@dataclass(frozen=True)
class Turn:
    text: str | None = None
    calls: tuple[ToolCall, ...] = ()


@lru_cache(maxsize=1)
def _client():
    from google import genai

    return genai.Client()


def _with_retry(call):
    for attempt in range(RETRY_ATTEMPTS - 1):
        try:
            return call()
        except Exception as error:
            if getattr(error, "code", None) not in RETRY_CODES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * 2 ** attempt)
    return call()


def _turn(response) -> Turn:
    candidates = response.candidates or []
    content = candidates[0].content if candidates else None
    parts = (content.parts if content is not None else None) or []
    text = " ".join(part.text for part in parts if part.text) or None
    calls = tuple(
        ToolCall(
            part.function_call.name,
            dict(part.function_call.args or {}),
            part.thought_signature,
        )
        for part in parts
        if part.function_call
    )
    return Turn(text=text, calls=calls)


def _content(entry: dict):
    from google.genai import types

    if entry["role"] == "tool":
        return types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(name=name, response=response)
                for name, response in entry["responses"]
            ],
        )
    parts = []
    if entry.get("text"):
        parts.append(types.Part.from_text(text=entry["text"]))
    for call in entry.get("calls", ()):
        part = types.Part.from_function_call(name=call.name, args=call.args)
        part.thought_signature = call.thought_signature
        parts.append(part)
    return types.Content(role=entry["role"], parts=parts)


class GeminiLLM:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("AFTERIMAGE_GEMINI_MODEL", "gemini-3.6-flash")

    def generate(self, system: str, history: list[dict], tools: list[dict]) -> Turn:
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description"),
                parameters_json_schema=tool["input_schema"],
            )
            for tool in tools
        ]
        return _turn(_with_retry(lambda: _client().models.generate_content(
            model=self.model,
            contents=[_content(entry) for entry in history],
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(function_declarations=declarations)],
            ),
        )))
