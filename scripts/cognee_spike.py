"""
cognee_spike.py — PRD Task 1: hello-world add / cognify / search against Cognee Cloud.

Run this ONCE with your real key before trusting the app wiring, to confirm the
exact Cloud SDK surface for your account/tenant (this is the highest-risk unknown
in the v2 build — see PRD §7 / §11).

    export COGNEE_API_KEY=...           # from https://platform.cognee.ai
    export COGNEE_CLOUD_URL=https://your-tenant.aws.cognee.ai
    python scripts/cognee_spike.py

It ingests two facts into a 'diary' node set, then asks a relational question.
If the printed answer references the sleep/chess link, graph memory works and you
can flip USE_GRAPH_MEMORY=true in .env.
"""
import os
import asyncio

from dotenv import load_dotenv

load_dotenv()


async def main():
    import cognee
    from cognee import SearchType

    api_key = os.getenv("COGNEE_API_KEY")
    url = os.getenv("COGNEE_CLOUD_URL") or os.getenv("COGNEE_SERVICE_URL")
    if not api_key:
        raise SystemExit("Set COGNEE_API_KEY (and COGNEE_CLOUD_URL) first.")

    print(f"→ Connecting to Cognee Cloud: {url or '<default>'}")
    serve_kwargs = {"api_key": api_key}
    if url:
        serve_kwargs["url"] = url
    await cognee.serve(**serve_kwargs)
    print("✓ Connected")

    # HARDCODED throwaway dataset — NEVER the real COGNEE_DATASET. The facts below
    # are FABRICATED sample data used only to prove the pipeline connects. Keeping
    # them in a disposable dataset means running this spike can never pollute your
    # real memory. Delete it after with: cognee.forget(dataset="abra_spike_demo").
    dataset = "abra_spike_demo"
    print(f"⚠️  Using disposable dataset '{dataset}' with FAKE sample facts (not your real data).")

    facts = [
        "Diary entry for 2026-06-30. Mood: Low Energy. Summary: barely slept, exam "
        "stress kept me up. Played blitz chess late and my accuracy tanked to 71%.",
        "Diary entry for 2026-07-02. Mood: Focused. Summary: slept 8 hours, calm. "
        "Chess accuracy was 89% in blitz and I ran 8km in the morning.",
    ]

    print("→ add() into node_set=['diary']")
    await cognee.add(facts, dataset_name=dataset, node_set=["diary"])

    print("→ cognify() (building the knowledge graph)...")
    try:
        await cognee.cognify(datasets=[dataset])
    except TypeError:
        await cognee.cognify()
    print("✓ cognified")

    q = "What happens to my chess accuracy in weeks where my diary mentions low sleep or exam stress?"
    print(f"→ search(GRAPH_COMPLETION): {q}")
    results = await cognee.search(
        query_text=q,
        query_type=SearchType.GRAPH_COMPLETION,
        datasets=[dataset],
        node_name=["diary"],
    )
    print("\n===== GRAPH ANSWER =====")
    print(results)
    print("========================\n")
    print("If the answer links low sleep/exam stress to lower chess accuracy, "
          "graph memory is working. Flip USE_GRAPH_MEMORY=true in .env.")


if __name__ == "__main__":
    asyncio.run(main())
