# SLM Server Review — Round 3: RAG Device Design + Audit Chunking Overhaul

Two focused asks this round: (1) proper RAG device optimization for AGX
Spark (unified memory) vs. a CPU-only server, and (2) a thorough review of
whether multi-chunk audits actually behave like the model reading the whole
policy. The second one turned up the most consequential finding across all
three review rounds — answered directly below.

---

## 1. Does chunked auditing work "the same as the model going through each
line one by one"? **No — and here's exactly why, now fixed.**

Traced the full pipeline chunk-by-chunk. The chunking itself
(`chunk_policy_text`) was already reasonably careful — it doesn't cut mid-
sentence in the common cases. The real problem was two layers away:

### The actual bug: silent coverage loss, not a chunking-mechanics bug

`_run_inference` never evaluated all of a long policy's chunks. It called
`select_operative_chunks(chunks, max_chunks=2 or 4)` — a **top-K filter**
that scores chunks by DPDP-keyword density and **silently discards every
chunk outside the top 2 (CPU) or top 4 (GPU)**, with no log line, no
indication in the response, nothing. Concretely:

- At `max_chunk_chars=3200`, that's a hard ceiling of **~12,800 characters
  (~2,000-2,500 words) evaluated on GPU**, and **~6,400 characters (~1,000
  words) on CPU** — regardless of how long the actual policy is.
- Layered on top: `security.py`'s `MAX_POLICY_CHARS = 32000` already
  truncated the raw input before chunking ever saw it, and the truncation
  point was a blind word-boundary cut, not tied to any document structure.
- Real corporate privacy policies — especially GDPR-era, multi-jurisdiction
  ones — routinely run 3,000-8,000+ words. **A violation stated only in a
  section beyond the top-K cutoff was never seen by the model, and the
  audit reported no indication that anything had been skipped.** This is
  under-detection risk in exactly the place it matters most: a "forensic
  legal audit" product silently sampling instead of reading.

A second, smaller bug compounded it: `_build_audit_prompt` re-sliced
whatever chunk text it was given to `[:3200]` regardless of the chunk's
actual (already-correct) length — redundant most of the time, but it meant
any future attempt to pass slightly-longer, context-enriched chunks (see
overlap, below) would have silently had that context cut back off again by
a blind character slice.

### Fixed: full coverage by default, capped only as a logged, tunable safety net

- `_audit_max_chunks_for_profile()` replaces the hardcoded 2/4 with
  generous defaults — **6 sections on CPU, 20 on GPU** — env-tunable via
  `SSENSE_AUDIT_MAX_CHUNKS_CPU` / `_GPU`. At 3,200 chars/chunk, 20 chunks
  covers **~64,000 characters (~10,000-11,000 words)** — the large majority
  of real-world policies, in full.
- When a policy's chunk count is within the cap (the common case now),
  **every chunk is evaluated, in original document order** — no scoring,
  no silent drop.
- When a policy genuinely exceeds the cap, the keyword-density fallback
  still runs, but now **logs a clear warning naming exactly how many
  sections will not be evaluated** and which env var raises the ceiling —
  turning a silent gap into a visible, deliberate, documented trade-off.
- `MAX_POLICY_CHARS` raised from 32,000 → 64,000 chars (env-tunable via
  `SSENSE_MAX_POLICY_CHARS`) so the upstream truncation isn't the binding
  constraint anymore either.
- `_build_audit_prompt`'s redundant re-slice is now a generous 4,500-char
  backstop instead of a routine 3,200-char truncation, so it no longer
  fights the chunker's own correct bounding.

### Sentence-safe chunking, upgraded

Reviewed the "no sentence cut in half" requirement specifically:

- The old sentence splitter (`re.split(r'(?<=[.!?])\s+', text)`) technically
  never cut a sentence *mid-word*, but it did mis-detect sentence
  boundaries at common abbreviations — "the U.S. Department" was treated as
  two sentences, "e.g." as a sentence end, etc. — which is a semantic
  version of the same problem: a clause gets split from its antecedent even
  though every character is technically preserved somewhere.
- New `_split_into_sentences()` adds an abbreviation-aware merge-back pass
  (standard technique for regex-based sentence splitting without a full NLP
  dependency): recognizes ~30 common abbreviations (`U.S.`, `e.g.`, `Inc.`,
  `Sec.`, `Dept.`, etc.), single-letter initials (`J. Smith`), and decimal
  numbers (`3.5 million`), and only treats `.`/`!`/`?` as a true sentence
  end when none of those apply. Verified against a battery of test cases
  (script run during this review) — 0 false splits on the abbreviation set
  tested, correct splits on genuine sentence boundaries.
- `chunk_policy_text` now uses this splitter both for subdividing oversized
  paragraphs and — new — for a **configurable sentence overlap**
  (`overlap_sentences=2`, default): the last 2 sentences of chunk *i* are
  prepended to chunk *i+1*, clearly labeled `[...continued from previous
  section, for context: "..."]`. This is the literal implementation of
  "properly recombined to receive the complete context" — a violation
  whose meaning depends on the sentence immediately before a chunk boundary
  (e.g. "...as described above. This data is retained indefinitely.") no
  longer loses its antecedent when that chunk is evaluated on its own.
- Verified end-to-end with a synthetic 19,400-char single-blob policy (no
  blank lines — the common shape of scraped HTML→text output): produced 7
  chunks, **zero** ended mid-sentence, overlap correctly prepended to every
  chunk after the first.

### New: a genuine second pass, not just a Python merge

This is the part of your ask that most directly maps to "passed through
the model once more for proper audit." Previously, N chunk reports were
combined with `recombine_audit_reports` — a purely deterministic Python
function (dedup by `(violation_type, statute_reference)`, sum severity
deductions, string-concatenate the top 2 reasoning blurbs). That's a
reasonable *fallback*, but it's not the same as a reviewer who actually
read the whole document reconciling their own notes.

Added `_consolidate_report()`: when more than one chunk was evaluated, the
per-chunk findings (violation type, statute reference, evidence quote,
section-level reasoning) are assembled into a structured evidence bundle
and **handed back to the model as a second generation pass**, explicitly
instructed to synthesize one cohesive final audit "as if you had read the
entire policy in a single continuous pass" — merging violations that
different sections phrased differently but which describe the same
underlying issue, discarding section-boundary artifacts, and writing one
unified reasoning narrative and trust score. This goes through the same
structured-output schema and the same `validate_and_repair_report`
validation as every other generation.

**Safety net, not a single point of failure:** if the consolidation call
throws, doesn't parse, or comes back reporting zero violations despite
every section finding at least one (a strong signal of a generation
glitch, not a genuine "actually it's fine" result), it falls back to the
deterministic `recombine_audit_reports` merge automatically — logged either
way. The pipeline can never fail, or silently under-report, because this
polish step had one bad generation.

**Net pipeline now, for a multi-chunk policy:**
1. Sentence-safe, overlap-aware chunking (all of it, not a truncated
   prefix).
2. Every chunk within the coverage cap evaluated concurrently (fixed last
   round) — this *is* "the model going through the document", chunk by
   chunk, not a sampled top-K subset.
3. A genuine second LLM pass over the combined findings, reading them
   together the way a single reviewer would reconcile their own section
   notes — not just a Python string-merge.
4. Deterministic merge as an always-available fallback if step 3 misfires.

---

## 2. RAG device optimization: AGX Spark (unified memory) vs. CPU-only

Round 2 defaulted the RAG embedder/reranker to CPU unconditionally, to
avoid the VRAM boot-order risk found on a tightly-capped discrete GPU. You
pointed out the actual deployment targets are Jetson-class **unified**
memory (AGX Spark) and a **CPU-only** server — worth designing for
properly rather than reusing the discrete-GPU-shaped default.

**Why a static default is wrong for the Jetson/Spark range specifically:**
unified memory means CPU and GPU share the same physical RAM, so the two
ends of that product line have very different headroom after vLLM claims
its budget:
- A ~32GB Jetson Orin: `engine.py`'s own jetson math
  (`min(TARGET_TOTAL_MEMORY_GB, total*0.6)`) claims up to 32GB, leaving as
  little as ~13GB free — tight.
- An AGX Spark-class board (up to ~128GB unified memory): the same formula
  still self-caps vLLM at `TARGET_TOTAL_MEMORY_GB` (32GB by default),
  leaving **~96GB genuinely free** — the RAG models (a few hundred MB) are
  a rounding error there, and placing them on the GPU is a real latency win
  with essentially no risk.

Always-CPU leaves that Spark-class latency win on the table; always-GPU
reintroduces the Orin-class OOM risk. **Fixed with headroom-aware
auto-selection** (`AsyncHybridRAG._select_device`):

- CPU-only server (no CUDA at all): trivially CPU, no computation needed.
- Any CUDA-capable profile: estimates what vLLM will claim
  (`min(TARGET_TOTAL_MEMORY_GB, total_mem_gb * 0.9)` — a deliberately
  conservative overestimate that's safe for both the discrete-GPU and
  jetson formulas in `engine.py`, since the real jetson claim is always
  `<=` this estimate), computes headroom, and places RAG on GPU only if
  headroom clears a threshold (`SSENSE_RAG_MIN_HEADROOM_GB`, default 8GB).
- **Same image, same compose file, correct behavior on both ends of the
  Jetson/Spark range automatically** — a 32GB Orin auto-selects CPU, an
  AGX Spark-class box auto-selects GPU, with no per-board manual tuning.
- `SSENSE_RAG_DEVICE=cpu|cuda` still available as an explicit override for
  anyone who's benchmarked their specific traffic shape and wants to force
  one or the other regardless of the estimate.

This replaces round 2's blanket CPU default with the properly-designed,
profile-aware version you asked for.

---

## Files changed this round

- `main.py` — abbreviation-aware sentence splitter, sentence-overlap
  chunking, full-coverage chunk evaluation (was silently top-K-limited),
  new `_consolidate_report()` second LLM pass with deterministic fallback,
  fixed the redundant re-truncation in `_build_audit_prompt`.
- `security.py` — `MAX_POLICY_CHARS` raised 32,000 → 64,000 chars,
  env-tunable.
- `rag_engine.py` — `AsyncHybridRAG._select_device()`: headroom-aware
  auto-selection between CPU and GPU/unified-memory placement.
- `docker-compose.yml` — new env vars documented (commented, opt-in):
  `SSENSE_AUDIT_MAX_CHUNKS_CPU/GPU`, `SSENSE_RAG_DEVICE`,
  `SSENSE_RAG_MIN_HEADROOM_GB`.
