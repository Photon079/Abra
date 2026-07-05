# PRD: Abra v2 - Graph Memory Second Brain

**Product:** Abra - Personal Life OS
**Version:** 2.0 (Cognee Memory Upgrade)
**Author:** Anish Udupa
**Hackathon:** Cognee x WeMakeDevs "The Hangover Part AI"
**Track:** Cloud Track (Cognee Cloud)
**Deadline:** July 5, 2026
**Repo:** github.com/Photon079/Abra

---

## 1. One-Line Pitch

Abra v1 could read your life. Abra v2 remembers it. Cognee turns Abra's flat context dumps into a persistent knowledge graph, so the assistant reasons over relationships and history instead of re-reading raw text on every request.

---

## 2. Problem: Why v1's Memory Is Broken

1. **Flat context, no structure.** `memory_loader.py` scans Notion sub-pages by title keyword and dumps raw text into the prompt on every single request.
2. **No persistence of derived knowledge.** Every insight the LLM produces is generated, shown once, and thrown away. Abra never gets smarter.
3. **Token waste and latency.** Full Notion brain plus diary history plus live Coral stats on every chat call.
4. **No temporal or relational reasoning.** Abra cannot answer "how has my relationship with running changed since exam season" because nothing links diary entries, goals, and telemetry across time.

## 3. Solution: Cognee as the Memory Engine

Replace the flat Notion-scan memory with a Cognee knowledge graph hosted on **Cognee Cloud**.

```
Speak / log / query
      |
      v
Coral SQL (live facts)  +  Notion (tasks, diary storage)
      |
      v
cognee.add() -> cognee.cognify()        <- ingestion pipeline
      |
      v
Knowledge graph: entities (goals, habits, people,
projects, races, chess patterns) + relationships + time
      |
      v
cognee.search(GRAPH_COMPLETION) on every chat/briefing
      |
      v
LLM answers with retrieved graph context, not raw dumps
```

Coral stays the live-data plane. Cognee becomes the memory plane. Notion remains the human-editable storage and task surface.

---

## 4. Goals and Non-Goals

### Goals (must ship by July 5)

- G1: Diary entries are cognified into the graph on save.
- G2: Chat and morning briefing retrieve context via `cognee.search()` instead of raw Notion dumps.
- G3: Daily Coral telemetry snapshot is ingested into the graph so trends persist as memory.
- G4: Runs on Cognee Cloud with API key auth. Zero local Cognee infra.
- G5: One demo-able "graph memory" moment: a question v1 could not answer that v2 answers from relationships.

### Non-Goals

- No custom ontology authoring UI.
- No graph visualization frontend beyond what Cognee Cloud provides.
- No new Coral sources (Chess.com and Strava stay as-is).
- No rewrite of intent_router, diary structuring, or the LLM cascade.
- No multi-user support.

---

## 5. Features

| # | Feature | v2 Behavior |
|---|---|---|
| F1 | Memory ingestion | Diary entries, goals, and daily telemetry summaries pushed through `add()` + `cognify()` into a persistent graph |
| F2 | Context retrieval | `search(query, GRAPH_COMPLETION)` returns ranked, relationship-aware context per query |
| F3 | Morning briefing | Briefing also queries graph for week-over-week entity trends |
| F4 | Insight persistence | Generated insights are written back into the graph as first-class nodes |
| F5 | Node set tagging | Node sets per domain: `diary`, `fitness`, `chess`, `goals`, `insights` |
| F6 | Notion fallback | Demoted to storage + human editing surface. Graph is the retrieval source of truth |

---

## 6. Architecture Changes

### Module: `app/memory/graph_memory.py`

- `ingest_diary(entry)`: add structured diary JSON to Cognee with node set `diary`, trigger cognify.
- `ingest_telemetry(text)`: daily Coral SQL summary into node set `fitness` / `chess`.
- `ingest_insight(text)`: write LLM-generated insights into node set `insights`.
- `ingest_batch(items)`: backfill helper — add many, cognify once.
- `retrieve(query, node_sets=None)`: wrapper over `cognee.search()` with GRAPH_COMPLETION.
- `connect_check()`: verify Cognee Cloud connectivity at startup.

### Modified modules

| File | Change |
|---|---|
| `app/features/diary.py` | After Notion write, call `graph_memory.ingest_diary()` (fire-and-forget) |
| `app/features/qa.py` | Add `graph_memory.retrieve(user_query)` alongside Coral live facts |
| `app/features/briefing.py` | Graph retrieval for trend context; write final briefing via `ingest_insight()` |
| `app/memory/notion_loader.py` | Kept as fallback (feature flag `USE_GRAPH_MEMORY`) |
| `.env.example` | Add `COGNEE_API_KEY`, `COGNEE_CLOUD_URL`, `USE_GRAPH_MEMORY` |
| `app/main.py` | Startup Cognee connectivity check; `/memory/backfill` endpoint; `/api/memory` status |

### Backfill

`POST /memory/backfill`: pulls existing Notion diary entries + a 30-day Coral telemetry snapshot, ingests them in one batch. Run once before demo recording.

---

## 7. Cloud Track Compliance

- All cognify and search calls hit the hosted Cognee Cloud API, authenticated via `COGNEE_API_KEY`. No local Cognee database.
- Verified SDK surface (cognee 1.2.2): `cognee.serve(url, api_key)` → `cognee.add(data, dataset_name, node_set=[...])` → `cognee.cognify(datasets=[...])` → `cognee.search(query_text, query_type=SearchType.GRAPH_COMPLETION, datasets=[...], node_name=[...])`. Validate for your tenant with `scripts/cognee_spike.py`.

---

## 8. Demo Script (the judging moment)

1. Ask v1-style question: "How many km did I run this week?" (Coral answers).
2. Ask the graph question: "What usually happens to my chess accuracy in weeks where my diary mentions low sleep or exam stress?" v2 retrieves linked diary + telemetry nodes and answers with specifics.
3. Show the morning briefing referencing an insight generated two days earlier (F4).
4. Optional: show the Cognee Cloud graph view of the `diary` node set.

Record demo only after backfill has run on real data.

---

## 9. Success Metrics

- Demo question in §8 step 2 answered correctly from graph retrieval.
- Chat context payload size reduced vs v1 flat dump.
- Zero manual steps after `.env` setup: startup connects to Cognee Cloud automatically.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Cognee Cloud API differs from local SDK docs | `scripts/cognee_spike.py` spike before trusting app wiring |
| Cognify latency on diary save blocks UI | Ingestion fires in a background thread, never blocks the voice flow |
| Backfill produces noisy graph | Ingest compact daily summaries, not raw SQL rows |
