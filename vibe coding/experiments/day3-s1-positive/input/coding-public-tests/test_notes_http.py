import asyncio
import json

from main import app


async def _post(path: str, payload: object) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode("utf-8")
    events: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(event: dict[str, object]) -> None:
        events.append(event)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("test", 1),
            "server": ("test", 80),
        },
        receive,
        send,
    )
    start = next(event for event in events if event["type"] == "http.response.start")
    raw = b"".join(event.get("body", b"") for event in events if event["type"] == "http.response.body")
    return int(start["status"]), json.loads(raw.decode("utf-8"))


def test_create_trimmed_note_has_exact_response_shape():
    status, body = asyncio.run(_post("/notes", {"text": "  short note  "}))
    assert status == 201
    assert set(body) == {"id", "text"}
    assert isinstance(body["id"], str) and body["id"]
    assert body["text"] == "short note"


def test_empty_and_overlong_text_are_rejected():
    for text in ("   ", "x" * 141):
        status, _ = asyncio.run(_post("/notes", {"text": text}))
        assert status == 422
