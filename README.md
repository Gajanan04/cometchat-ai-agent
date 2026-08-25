# Aster & Row Reliable Support Agent

A reliability-focused customer-support RAG agent built for the CometChat AI Engineering Internship take-home. It answers questions from a Markdown knowledge base, ranks current customer-facing policy above legacy or internal content, performs a sanitized order lookup, keeps bounded multi-turn session state, and hands off to a human instead of guessing when sources conflict or evidence is missing.

The system is built for reliability, not just the happy-path demo: source ranking, order sanitization, and conflict handoff each exist because an earlier, simpler baseline got them wrong, and each fix is backed by a regression test.

## Key Capabilities

- Deterministic lexical retrieval over the supplied Markdown knowledge base
- Markdown knowledge-base loading with chunking
- Source authority ranking — current customer-facing content is preferred over legacy, internal, or draft content
- Source citations returned alongside every grounded answer
- Source conflict detection, with handoff instead of silently picking a side
- Sanitized order lookup by order ID, with safe field projection
- Stale and cancelled-order handling in order responses
- Bounded session memory — in-memory conversation state capped at 8 turns
- Abstention when the knowledge base doesn't support an answer
- Safety and privacy handling as dedicated evaluation categories
- Human handoff state returned by the agent
- Customer-facing frontend for demoing the agent
- Deterministic, repeatable evaluation suite

## Architecture

```
User
  → API (POST /api/chat)
  → Session / Agent
  → RAG Retrieval
  → Authority Ranking / Conflict Detection
  → Order Tool (when relevant)
  → Safety Handling
  → Customer-safe Response
```

Pipeline: **loader → chunker → lexical retriever → authority ranking → conflict detection → agent → safe order tool**.

No vector database and no external credentials are required. Session storage is in-memory and holds up to 8 turns per session. The API returns only customer-safe fields: answer, citations, safe order fields, handoff state, and a trace ID.

## RAG Pipeline

The retrieval flow is: document loading → chunking → lexical retrieval → authority ranking → conflict detection → citations.

The current implementation uses deterministic lexical retrieval because the supplied corpus is small and fixed. This keeps behavior reproducible and straightforward to test and debug, without adding an external embedding-model dependency for the scope of this assignment.

## Knowledge Source Handling

Knowledge-base documents carry metadata that distinguishes current, customer-facing content from legacy/superseded or internal/draft content. Authority metadata influences ranking directly, so an outdated or internal-only source cannot outrank current customer-facing policy purely because it matches more keywords. Every grounded answer includes citations back to the source passages it was built from.

## Conflict Handling

When two authoritative, customer-facing sources genuinely disagree, the system does not silently choose one. Silently selecting a source in that situation risks giving the customer confidently wrong information with no indication that a real conflict exists. Instead, the agent detects the conflict and recommends handoff to human support rather than guessing — for example, in the Breeze Tumbler product-care case in the bug diary below.

## Order Tool / Tool Calling

The agent supports looking up order status by order ID, for example `ORD-1007`. Lookups return a sanitized response with safe field projection rather than the full internal order record, and cancelled or stale orders are handled so outdated delivery information is not presented as current.

## Conversation / Session Memory

Sessions are kept in memory and bounded to the last 8 turns, which is enough to support natural follow-up questions — for example, asking about an order and then following up about shipping to a specific country — without unbounded memory growth. Session state does not survive a process restart.

## Safety & Reliability

Implemented safeguards:

- **Source-conflict handoff** — disagreement between authoritative sources triggers handoff instead of a guessed answer
- **Sanitized order data** — safe field projection and stale/cancelled-order handling in order responses
- **Abstention** — the agent declines rather than fabricates when the knowledge base doesn't support an answer
- **Privacy-aware responses** — evaluated as a dedicated test category
- **Human handoff state** — returned explicitly by the agent when it cannot safely answer

The evaluation suite scores the system directly against safety, abstention, privacy, and source-conflict cases, rather than only happy-path retrieval accuracy.

## API

```
GET  /health
POST /api/chat
```

### Request Example

```json
{
  "session_id": "demo",
  "message": "Where is ORD-1007?",
  "debug": false
}
```

The server runs at `http://127.0.0.1:8000` after starting with `python -m backend.app.main`. Customer-facing responses contain only safe information: the answer, citations, safe order fields, handoff state, and a trace ID.

### cURL Example

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Where is ORD-1007?","debug":false}'
```

## Frontend / Demo

A static frontend, aligned to a Stitch design, provides the customer-facing chat experience used to demo the agent end to end.

## Evaluation

The evaluation suite covers 15 supplied cases plus 5 original cases, for 20 total cases.

### Baseline

An early, intentionally simple extractive baseline was measured against the same 20 evaluation cases used for the final system:

- One raw lexical top-passage match
- The existing sanitized order lookup when an order ID is present
- No session memory
- No policy-specific authority handling
- No conflict handling
- No final safety orchestration

**2/20 passed — 10%**

This is an internal comparison baseline, not an official CometChat baseline.

### Final System

The final agent — with deterministic lexical retrieval, authority ranking, conflict detection, sanitized order lookup, bounded session memory, abstention, and safety/privacy handling — was evaluated against the same 20 cases.

**20/20 passed — 100%**

| System | Passed | Total | Rate |
|---|---:|---:|---:|
| Early/simple baseline | 2 | 20 | 10% |
| Final reliable agent | 20 | 20 | 100% |

**Improvement: +18 cases / +90 percentage points**

## Evaluation Categories

The 20 evaluation cases span: retrieval, groundedness, tool use, privacy, multi-turn, safety, abstention, and source conflict.

## Bug Diary / Engineering Lessons

**1. Legacy policy competing with current policy**
- Cause: No authority precedence between source types.
- Fix: Authority scoring in the ranking step.
- Regression: ranking test.

**2. Cancelled orders exposing stale delivery dates**
- Cause: Unsafe field projection in the order lookup.
- Fix: Status-aware sanitization of returned fields.
- Regression: order test.

**3. Genuine product-care source conflict**
- Cause: The top-ranked result could be selected without checking for disagreement.
- Fix: Explicit conflict detection and handoff.
- Regression: conflict test.

## AI Coding Tools

AI coding tools were used as development assistants for scaffolding, repository exploration, test-writing support, debugging, and implementation suggestions. Suggestions were reviewed, tested, and adapted rather than used as-is. For example, an early suggestion treated every knowledge-base metadata field as mandatory; this was rejected because optional metadata needed to remain loadable.

## Limitations

- Deterministic lexical retrieval rather than semantic retrieval. For a larger or fast-changing knowledge base, production could extend this approach with semantic or hybrid retrieval.
- In-memory sessions that do not survive a process restart; production would need durable session storage.
- Supplied/mock order data rather than a live order system.
- No production authentication on the API or the order lookup.
- No production rate limiting.
- No production deployment configuration.
- No real ticketing/handoff integration — handoff is a state the agent returns, not a live escalation to a human queue.

These are take-home scope decisions, not failures, each with a clear path to what production would add.

## Running Locally

```bash
python -m unittest discover -s tests -v
python evaluation/run_baseline.py
python evaluation/run_eval.py
python -m backend.app.main
```

- `python -m unittest discover -s tests -v` runs the regression test suite.
- `python evaluation/run_baseline.py` runs the early/simple baseline against the 20 evaluation cases.
- `python evaluation/run_eval.py` runs the final agent against the same 20 evaluation cases.
- `python -m backend.app.main` starts the API at `http://127.0.0.1:8000`.

## Demo Video

A 2–4 minute walkthrough demonstrating the key reliability and agent behaviors.

**Watch the demo:** https://drive.google.com/file/d/1RtP3vuvjt8O-lPwD-1vsevDNjOiNM8Qi/view?usp=sharing

The demo covers:

1. Grounded RAG answer with citation
2. ORD-1007 order lookup
3. Canada multi-turn follow-up
4. Breeze Tumbler source conflict and human handoff
5. Final 20/20 evaluation

## Submission Checklist

- [x] Source code
- [x] Tests
- [x] Evaluation suite
- [x] Baseline comparison
- [x] README
- [x] `.env.example`
- [x] Architecture documentation
- [x] Bug diary
- [x] Limitations documented
- [x] AI coding tools disclosed
- [ ] Demo video link added
- [ ] Final submission link checked
