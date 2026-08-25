# Aster & Row Reliable Support Agent

Small deterministic RAG support agent for the CometChat take-home. It loads Markdown sources, ranks current customer-facing authority above legacy/internal content, performs a sanitized order lookup, preserves bounded sessions, and hands off when sources conflict or information is missing.

## Run

```powershell
python -m unittest discover -s tests -v
python evaluation/run_eval.py
python -m backend.app.main
```

The API serves `GET /health` and `POST /api/chat` at `http://127.0.0.1:8000`. Request: `{"session_id":"demo","message":"Where is ORD-1007?","debug":false}`. The Stitch-aligned static UI is in `frontend/`.

## Architecture

`loader → chunker → lexical retriever → authority ranking/conflict check → agent → safe order tool`. No vector database or credentials are required: lexical retrieval is deterministic for this small corpus. In-memory session storage keeps eight turns. The WSGI API returns only customer-safe answer, citations, safe order fields, handoff state, and trace ID.

## Evaluation

`python evaluation/run_eval.py` runs 15 supplied cases and 5 original cases. Final result: **20/20** across retrieval, groundedness, tool use, privacy, multi-turn, safety, abstention, and source conflict.

## Bug diary

1. Legacy policy could compete with current policy. Cause: no precedence. Fix: authority scoring; regression: ranking test.
2. Cancelled orders exposed stale delivery dates. Cause: unsafe field projection. Fix: status-aware sanitization; regression: order test.
3. Product-care conflict could be silently answered. Cause: choosing a top result. Fix: conflict handoff; regression: conflict test.

## Limitations

This exercise uses lexical retrieval and in-memory sessions. Production would add semantic embeddings, durable storage, authenticated order access, rate limits, and real handoff integration. Codex was used for scaffolding and testing; an early suggestion to require every metadata field was rejected because optional metadata must remain loadable.

## Demo

Record a 2–4 minute capture showing a cited policy answer, `ORD-1007` lookup, Canada follow-up, Breeze conflict handoff, and the evaluation command. Add the GIF or video link before submission.
