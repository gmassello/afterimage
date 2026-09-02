import os
from dataclasses import dataclass
from functools import lru_cache


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
        response = _client().models.generate_content(
            model=self.model,
            contents=[_content(entry) for entry in history],
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(function_declarations=declarations)],
            ),
        )
        parts = response.candidates[0].content.parts or []
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
