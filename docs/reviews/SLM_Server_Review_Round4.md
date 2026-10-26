# SLM Server Review — Round 4: Audit Pipeline Corrected to Match How the Model Was Trained

You were right to push back on round 3's second LLM pass. Removed it and
rebuilt the combination logic as pure, deterministic aggregation — this is
a correction, not just an alternative design, and the reasoning is worth
being explicit about.

---

## Why the second LLM pass was actually wrong (not just unnecessary)

The audit LoRA adapter was fine-tuned for exactly one task shape: **one
policy chunk of text in → one probabilistic trust score + chain-of-thought
out.** That's what its training data looked like, and it's the only task
shape it has any real calibration for.

Round 3's consolidation pass asked the model to do something categorically
different: take its own prior JSON outputs from N chunks, formatted as a
synthetic "[SECTION 1/5] ... [SECTION 2/5] ..." evidence bundle, and
produce a reconciled summary. **That input format never appeared in
training.** Setting `temperature=0.0` (already the default, unchanged)
makes that specific generation deterministic, but deterministic and
in-distribution are two different properties — greedy decoding on an
out-of-distribution prompt still produces an unreliable output, it just
fails the same unreliable way every time instead of randomly. For a
forensic legal audit product, adding a step whose reliability the base
training data says nothing about is a real regression, not a polish
feature. Correctly identified and removed.

## New design: model used exactly as trained, combination is pure Python

`_run_inference` now:

1. Chunks the policy (unchanged from round 3 — sentence-safe splitting,
   small overlap for cross-boundary context, full coverage within the
   per-profile cap).
2. Runs **every chunk independently and concurrently** through the model —
   each call is a clean, single-chunk (policy text) → (score, CoT)
   generation, precisely the shape the LoRA was trained on. No chunk's
   output is ever shown to the model as input to another call.
3. **Discards every chunk that came back clean** (`dpdp_trust_score == 100`
   and no violations) — "the good portions are removed," exactly as
   specified. A clean chunk's boilerplate reasoning contributes nothing and
   would only dilute the final report's reasoning text.
4. If nothing was flagged, returns a clean report directly — no further
   model calls, no merge step.
5. If one or more chunks scored below 100, their violations are
   **deterministically congregated** — Python-level dedup on
   `(violation_type, statute_reference)`, then a combined trust score
   recomputed from the full merged violation set using the existing
   severity-deduction table. This is `recombine_audit_reports`, unchanged
   in its internals from round 2, now called only on the pre-filtered
   flagged subset instead of on every chunk (previously it saw every
   chunk's boilerplate "no issues" reasoning mixed in too — cleaner now).

No LLM call is made to merge or reconcile anything. Verified with a mock
test (5 synthetic chunk reports, 3 clean + 2 flagged): the filter correctly
kept only the 2 flagged chunks, congregated their two distinct violations,
and computed the combined score from just those — and a fully-clean batch
correctly produces zero flagged chunks with no merge step invoked at all.

## Consistency fix while in there

`recombine_audit_reports`'s own internal "ended up with zero violations"
fallback used to return `dpdp_trust_score = 95` — an arbitrary different
number from the `100` the model itself uses for a genuine clean result
(confirmed against the existing test suite, `tests/test_server_security.py`,
which asserts exactly `100` for a clean report). Aligned to `100` so a
"clean" result means the same score everywhere in the pipeline, however it
was arrived at.

---

## Concurrency isolation: bounding audit's fan-out against the 10k+ chat surface

This is the part of "proper size for proper concurrent processing... alongside
the chatbot concurrent 10k+ support" that needed a real fix, not just chunk
sizing. Chunk size itself (3,200 chars/chunk, ~800-1,000 input tokens +
up to 1,024 output tokens) was already reasonably set and is unchanged.
The actual gap was upstream of chunk size:

**The problem:** `memory_orchestrator.py`'s `InferenceQueue` gates
*requests* — one admitted audit request occupies one queue slot, regardless
of how much work happens inside it. But a single audit request can now fan
out to up to `_audit_max_chunks_for_profile()` (20 on GPU) concurrent
`generate_audit()` calls via `asyncio.gather`. If the queue has admitted,
say, several audit requests concurrently, the total number of vLLM
sequences requested by audit work alone could spike well past
`max_num_seqs` (256 on GPU) — and that burst competes for the same batch
slots as chat's decode steps. The request-level admission queue has no
visibility into this internal fan-out at all.

**Fix:** a new `asyncio.Semaphore` (`_get_audit_chunk_semaphore`), separate
from the `InferenceQueue`, that caps the **total number of audit
chunk-generations in flight globally, across all audit requests at once** —
independent of how many top-level requests are admitted. Default 32 on
GPU/Jetson (8 on CPU, where the `transformers` backend's own lock serializes
everything anyway, so this mostly documents intent there), env-tunable via
`SSENSE_AUDIT_MAX_CONCURRENT_CHUNKS`. This leaves the rest of vLLM's
`max_num_seqs` budget consistently available for chat regardless of how
many long policies are being audited at once, instead of audit bursts being
able to transiently crowd it out.

Both the per-request coverage cap and this global concurrency cap are
env-tunable per profile (`SSENSE_AUDIT_MAX_CHUNKS_GPU/CPU`,
`SSENSE_AUDIT_MAX_CONCURRENT_CHUNKS`), documented in `docker-compose.yml`
for both the gpu and jetson profiles — Jetson's much smaller
`max_num_seqs=16` (engine.py) makes this bound matter proportionally more
there, so its default is tighter (8) than GPU's (32).

---

## Net effect on hallucination risk

Two independent things now reduce it, together:
1. **No more out-of-distribution generation** — every model call is the
   exact task shape it was trained for; the unreliable "reconcile your own
   JSON outputs" step is gone entirely.
2. **Combination logic is now fully auditable** — `recombine_audit_reports`
   is plain Python: dedup by key, sum a fixed severity table, no generative
   step where an error could be introduced silently. Anyone can read
   exactly how a final score was derived from the flagged chunks' raw
   model outputs.

---

## Files changed this round

- `main.py` — removed `_consolidate_report` / `_build_consolidation_prompt`
  entirely; `_run_inference` now filters to flagged chunks and calls
  `recombine_audit_reports` deterministically; added the audit-chunk
  concurrency semaphore; `recombine_audit_reports`'s clean-score fallback
  aligned to 100.
- `docker-compose.yml` — new env vars documented (commented, opt-in) on gpu
  and jetson profiles: `SSENSE_AUDIT_MAX_CONCURRENT_CHUNKS`,
  `SSENSE_AUDIT_MAX_CHUNKS_GPU`.
