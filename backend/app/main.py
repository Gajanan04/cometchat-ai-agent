"""Small standard-library WSGI API for the support agent."""
from __future__ import annotations
import json
import mimetypes
from pathlib import Path
from typing import Callable
from wsgiref.simple_server import make_server
from .agent.agent import SupportAgent

agent = SupportAgent()
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

def health() -> dict[str, str]:
    return {"status": "ok"}

def chat(payload: dict) -> dict:
    session_id, message = str(payload.get("session_id", "")).strip(), str(payload.get("message", "")).strip()
    if not session_id or not message:
        raise ValueError("session_id and message are required")
    return agent.chat(session_id, message, bool(payload.get("debug", False))).customer_payload()

def application(environ: dict, start_response: Callable) -> list[bytes]:
    try:
        if environ["REQUEST_METHOD"] == "GET" and environ["PATH_INFO"] == "/health": status, payload = "200 OK", health()
        elif environ["REQUEST_METHOD"] == "POST" and environ["PATH_INFO"] == "/api/chat":
            length = int(environ.get("CONTENT_LENGTH") or 0); status, payload = "200 OK", chat(json.loads(environ["wsgi.input"].read(length) or b"{}"))
        elif environ["REQUEST_METHOD"] == "GET":
            requested = environ["PATH_INFO"].lstrip("/") or "index.html"
            file_path = (FRONTEND / requested).resolve()
            if FRONTEND in file_path.parents and file_path.is_file():
                body = file_path.read_bytes(); start_response("200 OK", [("Content-Type", mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"), ("Content-Length", str(len(body)))]); return [body]
            status, payload = "404 Not Found", {"error": "not found"}
        else: status, payload = "404 Not Found", {"error": "not found"}
    except (ValueError, json.JSONDecodeError) as error: status, payload = "400 Bad Request", {"error": str(error)}
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]

if __name__ == "__main__": make_server("127.0.0.1", 8000, application).serve_forever()
