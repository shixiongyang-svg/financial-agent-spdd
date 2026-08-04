# Week 4 - Prompts and Conversation Compression (Context Engineering, Stage 1)

Week 3 shipped a working `POST /agent/query` with a four-node graph. The problem now is that every prompt is still embedded as an unmaintainable string inside Python code. This week fixes that and introduces the first piece of vocabulary the industry calls Context Engineering.

> **Reminder.** This is the first of two Context Engineering injections in the curriculum. Stage 1 this week is tactical: add a LangGraph node that compresses long conversation history. Stage 2, in Week 8 Sub-Task D, is the mature intent-driven version that closes the curriculum's largest loop. Do not try to force Stage 2 vocabulary into this week.

> **This week's Scenario rule.** `scenario_phase` is not about "guessing a scenario as best as possible". Its job is to decide whether `product_type` is clear enough to support complaints retrieval. If `product_type` is unclear, do not query complaints. That avoids mixing non-product complaints into downstream retrieval. Only when the complaints source itself has no usable mapping do we allow `scenario=None` as a silent fallback. All other scenario-identification failures must go through feedback so the user can provide enough information to produce a correct `Scenario`.

## What you get this week

- `.spdd_specs/tasks/Task_4_Prompts.trainee.md` - your Monday brief.
- On Sunday: `Task_4_Prompts.md`, the destination.

## What this week introduces

Three things, in priority order:

1. **Versioned prompt templates** in `src/financial_agent_api/core/prompts/*.j2`, loaded through a single `PromptService` with strict-undefined Jinja. Replace the inline strings from Week 3.
2. **`Scenario` extraction** - a new node, `scenario_phase`, that runs before retrieval and extracts a `Scenario` JSON object with `product_type`, `issue_type`, and `confidence`. The extracted result drives prompt rendering and retrieval filtering. `product_type` is the key field that decides whether complaints retrieval should happen. If `product_type` is unclear, skip complaints retrieval. Only when the complaints source has no usable mapping do we allow `scenario=None` as a silent fallback. All other failure paths should go to feedback. The docs vector index still stays on the parallel path for coverage and robustness (see the retrieval section below).
3. **Stage-1 conversation compression** - a `compress_history` helper that `ingest_input` calls when `len(conversation_history) > N`. It uses the `compress_history.j2` template to call a small LLM, folds earlier messages into a single summary string, keeps the last few turns verbatim, and writes the compressed list back into `AgentState.conversation_history`.

A fourth concept, the `SafetyDecision` Pydantic shape, is defined this week but not yet enforced in the graph. Week 7 enforces it.

## Why we do it this way

### On prompts

- **Why Jinja with strict-undefined?** Because a missing variable should fail the build, not become an empty string. This catches template and data-shape drift before production.
- **Why version prompts under `src/financial_agent_api/core/prompts/`?** Because in Week 5 the eval pipeline regression-tests prompts the same way unit tests regression-test code. Untracked prompts cannot be tested.
- **Why skip complaints when `product_type` is unclear?** Because the value of complaints retrieval is in narrowing the search to the relevant product. Without a product constraint, the retrieval result becomes a large pile of non-product complaints, which weakens `scenario_phase` and makes downstream analysis noisier.
- **Why allow `scenario=None` only when the complaints mapping is empty?** Because that means the data source itself cannot support scenario extraction. It is an infrastructure-level fallback. In every other case, scenario failure should go through feedback and bring the user back to a state where the scenario can be determined.

### On `compress_history`

- **What problem does it solve?** Conversation history grows linearly per turn. By the 10th turn, the LLM is reading 9 prior turns of context. That increases token cost, lowers prompt-cache hit rate, and pushes the model beyond its effective attention window. This is the tax that turns a working agent into something too expensive for production.
- **Why threshold at 5?** It is a practical heuristic. The first ~5 turns are usually inside a model's coherent attention window. Degradation becomes measurable around turn 6. Treat 5 as configurable in `Settings`.
- **Why keep the last two turns verbatim?** Because the immediate context is the most information-dense. Summarizing the last turn breaks grounded follow-up answers.
- **Why use a small ops model for the summary?** Because the summary itself is an LLM call. Using `gemma3:27b` to summarize for `gemma3:27b` doubles the cost. The ops model, such as `qwen3.5:4b`, is fast enough to compress five messages into a short summary.
- **OpenRouter note:** use `Settings.compress_ops_model` for compression even when the provider is OpenRouter. Do not fall back to the provider's default chat model for compression.
- **Why compress before rendering the synthesis prompt?** Because the prompt template renders against `state["conversation_history"]`. Compress first, render second. The order matters for prompt-cache stability, and we revisit this exact property in Week 8.

A common question: "Could we cache the system-prompt prefix and skip compression?" No. Caching and compression are complementary, not competing. Week 8 Sub-Task D covers the cache side of the story. The pieces compose better when you arrive at Week 8 with this week's `compress_history` already shipped.

## Common Week-4 pitfalls

| Pitfall | What it looks like | Fix |
|---|---|---|
| Compressing the last turn too | The summary swallows "I just bought a house in California", so the next answer loses jurisdiction. | Keep the last two turns verbatim. The summary only covers older messages. |
| Using the synthesis model for compression | Expensive and slow. | Use the ops model from `Settings`. |
| Compressing on every turn | A 3-turn conversation gets a useless one-line summary like "user said hi". | Set the threshold to 5; below that, no-op. |
| Forgetting strict-undefined on the new template | A missing `messages` variable renders as `""`. | The constitution sets `StrictUndefined` as the default for every Jinja template, including new ones. |
| Leaving inline prompt strings in tools | A test file or tool keeps a copy of a prompt. | `src/financial_agent_api/core/prompts/` is the prompt registry. Everything else is a copy that must be deleted. |

## Wednesday self-check

- [ ] *Risks noticed* covers Jinja undefined errors, JSON parsing failures on the Scenario shape, and the conversation-history growth problem addressed by `compress_history`.
- [ ] *Trade-offs accepted* names Jinja vs f-strings vs PEP 750 templates, schema-in-prompt vs JSON mode, retry budget vs latency, and threshold-at-N compression vs always-compress vs never-compress.
- [ ] *Class diagram* shows `PromptService -> templates`, the new `compress_history` helper as a separate function called from `ingest_input`, and the Scenario extraction tool with bounded retry.
- [ ] *Operations* are numbered. The compression step is its own pinned step in the Operations list. The destination canvas pins its position explicitly on Sunday.

## What Sunday will reveal

The destination canvas pins:

- The four prompt-template names and their input variables.
- The `Scenario` and `SafetyDecision` Pydantic shapes, colocated in `src/financial_agent_api/core/safety_policy.py`.
- The `ScenarioExtractionTool`, with one bounded retry and feedback fallback on second failure. The retry should only cover recoverable errors, for example `LLMOutputValidationError`, network errors, and `5xx`. `LLMProviderError` `400/429` should not continue retrying the same request.
- The `compress_history` helper signature, threshold, and verbatim-tail policy.

Compare your Friday work against Sunday, then file a reconciliation PR before Monday.

## Going further (optional reading)

- Anthropic's article on context window engineering, the term that explains why this week matters.
- Token counting (`tiktoken` or the Anthropic tokenizer endpoint), so you can measure savings in tokens rather than characters.
- The LangGraph memory and checkpointing tutorial. It under-explains the real problem, which is part of why this curriculum exists.
- Jinja StrictUndefined documentation.
- Forward link: when you reach Week 8 Sub-Task D, come back to this canvas's `compress_history` section. The two stages compose. Reading them together is the moment you stop being an Agent Developer and start being a Context Engineer.

---

## Implementation Guide

### Trade-offs

#### Schema-in-prompt vs JSON mode

This has already been decided: use JSON mode so parsing is deterministic and failures are explicit instead of ambiguous.

#### Compress threshold: 5 or 10

Use 5 for now. Whether the right number is 5 or 10 is a data question, but the immediate requirement is to support environment configuration and logging.

#### Ops model selection: fast, accurate, or cheap?

The model quality still needs empirical validation. At this stage, if we stay within free models, prioritize accuracy.

#### On failure: default Scenario or raise?

Do not default Scenario. After a bounded number of retries, raise an exception or return an error so the user knows exactly what information is missing.

### Operations

#### Write template files first so they can be checked at compile time

1. Follow the selected template rendering tool's documentation and make sure templates can be checked at compile time or during startup.

#### `PromptService` should be initialized before any tool nodes

The practical requirement is not "initialize it for its own sake". The requirement is that any method that needs to render a prompt can call `PromptService` successfully. If the technology requires warmup or eager loading because first render is slow, do it at startup.

#### Insert `scenario_phase` before `retrieve`, but do not replace `ingest_input`

That is required. `ingest_input` still handles basic user-input validation, and only after validation should the graph proceed to later nodes.

#### Put the `compress_history` threshold in `Settings`

Yes. That value will need to be tuned later.

## Questions

Answer each question below. The user approves the answers.

1. From the perspective of the existing and new nodes, which prompts need to be added, and what parameters does each template require?

- `scenario_extraction.j2` (required)
  - inputs: `messages` (recent turns, required), `allowed_product_issue_map` (required, non-empty object with product -> issues mapping, for example `{"Credit": ["Getting a credit card", "xxxx"]}`)
  - output: Scenario JSON with `product_type`, `issue_type`, `confidence`
  - note: the prompt asks the LLM to optionally return `product_type` and `issue_type` if they can be determined, plus `confidence`. This week's implementation keeps only those three fields and does not ask for audit fragments.
    - `allowed_product_issue_map` usage and constraints:
      - usage: give the LLM the allowed product values and the allowed issue values for each product, so the extraction output stays inside the real complaint-database range.
      - constraint: `allowed_product_issue_map` must come from the complaints data source and contain at least one product. Each product's issue list must also be non-empty. If the object is empty or missing, the previous stage should skip `scenario_extraction`, and this week `scenario=None` is allowed as a silent fallback.
    - `product_type` generation rules:
      - `product_type` should be selected from the keys of `allowed_product_issue_map`, or returned as `null`.
      - If the LLM confidently decides that the user's problem does not match any allowed product, it should return `product_type = null` with high `confidence`. That means "the complaints data has no target product worth referencing", not "the model cannot decide".
      - Once the backend accepts that result, if `product_type = null`, skip Retrieve Complaints and do not open complaints retrieval.
      - The server only validates membership: a non-null `product_type` must be a key in `allowed_product_issue_map`. Otherwise the result is invalid.
    - `issue_type` usage and generation rules:
      - usage: further filter the complaints query within the selected product by the `issue` field.
      - generation: when `product_type` is known, `issue_type` should be selected from the issue list for that `product_type`, or returned as `null`. If the LLM confidently decides there is no suitable issue match for that product, it may return `issue_type = null` and keep high `confidence`.
      - the server only validates membership: non-null `issue_type` must belong to `allowed_product_issue_map[product_type]`.
    - `confidence` usage and rules:
      - usage: indicate how trustworthy the extraction is, so the backend can decide whether to accept the result or trigger feedback.
      - rule: the backend checks whether `confidence` crosses the threshold first. If it does, accept the extraction. If `product_type = null`, that means skip Retrieve Complaints. If `product_type` is non-null, use `issue_type` to filter complaints.
      - failure handling: if `confidence` is below threshold or member validation fails, do not use the Scenario as a definite result. Enter bounded retry, then trigger feedback if it still fails, until the user can provide enough information to obtain an acceptable Scenario.
  - purpose: build retrieval filters and choose template variables, while retrieval still queries structured complaints and docs vector data in parallel for coverage and robustness.
  - AI review: the explanation of scenario_extraction input/output and membership validation is sufficient and actionable. Suggested additions: 1) provide example input/output JSON for development and testing; 2) clarify system behavior when `allowed_product_issue_map` is empty or missing; 3) add unit tests for boundary and error cases.

- `compress_history.j2` (required)
  - inputs:
    - `messages_to_compress` (required): the old messages to compress. This includes only the history that will be folded, not the recent messages that are kept verbatim.
    - additional note: whether compression runs, how many tail messages are retained, which model is used, and how `confidence` is checked are all outside `compress_history.j2`. They are handled by the helper function and runtime configuration.
  - output: `{summary_text, confidence: float}`
    - `summary_text` contains only the compressed result of `messages_to_compress`, not the verbatim tail.
    - when writing back to `conversation_history`, the helper function outside the template should do the concatenation: `[compressed summary] + [recent raw tail]`.
    - template rule: keep the main language of the input messages, do not translate terms unless necessary, keep only facts needed for downstream reasoning, and stay concise.
  - purpose: fold early messages into a summary while preserving verbatim tail messages, so context length drops without losing recent interaction details.
  - AI review: the template and output definition are clear, and keeping tail retention and trigger conditions outside the template is the right engineering choice. Suggested additions: 1) an example template input/output; 2) a clear default and fallback path for incremental vs full recompression; 3) record compression version and source for traceability.

- `summarization.j2` (required)
  - inputs: `user_query` (required), `conversation_history` (required), `retrieved_complaints` (optional), `retrieved_docs` (optional)
  - output: `summarization` for the synthesise node
  - AI review: the input and output contract is appropriate for an intermediate layer. Suggested addition: provide a typical `conversation_history` and retrieval result example with expected `summarization` text for evaluation and test writing.

- `synthesise.j2` (required)
  - inputs: `user_query` (required), `summarization` (required)
  - output: final response

- `feedback_prompt.j2` (extensible, optional this week)
  - inputs: `user_query` (required), `failure_reason` (required), `scenario` (optional), `guidance` (optional)
  - output: `feedback_message`
  - AI review: `feedback_prompt` is necessary and reasonable. Suggested additions: 1) define the tone and style of the feedback (for example friendly, concise, guided); 2) provide at least two template examples (missing-field prompt, low-confidence clarification); 3) record whether the user follows the guidance to assess template quality.

2. What environment variables should be added?

- `COMPRESS_THRESHOLD` - optional - the turn count that triggers compression - default `5`
- `COMPRESS_OPS_MODEL` - optional - the ops/lightweight model used for compression - default `qwen3.5:4b`
- `COMPRESS_CONFIDENCE_THRESHOLD` - optional - the minimum acceptable compression confidence - default `0.70`

3. What is the right strategy for passing history?

- Conclusion: the client should only send the current `query` and `session_id` by default. The backend should load conversation history automatically. Client-provided `conversation_history` should only be accepted for compatibility, not treated as the source of truth, and it must not overwrite server history.
- Session identifier: use `session_id` consistently. The first request may omit `session_id`, in which case the backend creates one and returns it. Later requests should send that `session_id` back.
- History storage: history should live in backend storage, not only in memory, so compression, retrieval, debugging, and tracing all work reliably.
- History loading: every request should load the full history for the `session_id`, then pass it through `compress_history`. Do not truncate client-side first.
- Concurrency: queries for the same `session_id` should be handled serially so turn order, compression results, and retrieval context do not drift.
- Write-back: write the user message first, then write the assistant message after the final reply is generated. That way the user's input is preserved even if something fails mid-request.
- Trade-off: this sacrifices some client flexibility, but it gives a single source of truth for history, unified compression logic, a simpler API, and a more stable path for later evolution.

4. What should we use for conversation compression model selection, quality judgment, and onboarding?

- Selection principle: prefer a model that is fast, low-cost, and supports JSON mode, so the output is reliably machine-parseable as `{summary, confidence}`.
- Evaluation dimensions: latency, cost, JSON parse stability, and summary fidelity (whether it preserves facts needed for later reasoning).
- Onboarding steps: collect a representative conversation set, run offline fidelity evaluation, set the confidence threshold, then do A/B testing in preproduction with metrics such as user satisfaction, downstream retrieval hit rate, token consumption, and latency.
- Runtime strategy: compress first and check `confidence`. If it is below threshold, retry once more. If it still does not pass, abandon compression and log it for analysis.
- Note: this question is only about model selection and quality judgment. Whether compression state is maintained incrementally is covered in question 6.

5. Where should `allowed_product_issue_map` come from, and how should it be refreshed and stored?

- Source: `allowed_product_issue_map` should come directly from complaints data, not from handwritten enums. Specifically, derive unique `product` values and unique `issue` values per product from complaints and build a `product -> issues[]` map.
- Refresh timing: do not compute it on every request or during ordinary app startup. Refresh it immediately after complaints ingestion or refresh is complete. In this project, the best place is after the complaints ingestion step that runs during Docker service startup.
- Storage location: the mapping should not live only in memory or a temp file. Store it as complaints-derived data, ideally in the database.
- Storage form: a dedicated database table is recommended, with one row per valid `product` / `issue` combination. The runtime can read that table and assemble `allowed_product_issue_map`. Compared with a single JSON blob, this is easier to debug, validate, and extend.
- Runtime use: when the API needs to run `scenario_extraction`, it reads the derived table and assembles `allowed_product_issue_map`. If the mapping does not exist or is empty, skip `scenario_extraction` and continue with docs retrieval and later flow.

6. Should `compress_history` use full recompression every turn or incremental compression?

- Recommendation: use incremental compression by default, not a full recompression of the original history on every turn.
- Example: if turn 1-4 are already compressed into one summary and turns 5-6 remain raw, then at turn 7 we should not recompress turn 1-4 again. Instead, we should generate a new summary from the previous compression summary plus the new message that just entered the compression window.
- Benefits: lower cost, more stable behavior, and less risk that earlier history keeps changing because of later turns.
- Risk: incremental compression can accumulate error, so details may be lost over time.
- Compromise: use incremental compression for normal turns, and trigger a full rebuild when compression has been applied too many times, the summary grows too long, or quality drops significantly.
  - Full rebuild triggers:
    - Too many compression levels: compression depth for a session reaches 3 or more.
    - Summary too long: `summary_text` token count exceeds 80 percent of the original message token count.
    - Quality clearly drops: the average `confidence` of the last 2 compressions is below `COMPRESS_CONFIDENCE_THRESHOLD * 0.8`.
    - Session runs too long: the number of turns exceeds `COMPRESS_THRESHOLD * 2`.
  - Full rebuild flow:
    - Recompress the full session history from scratch, not from the previous incremental summary.
    - Write the new `{summary_text, confidence, compressed_rounds: [1..N-2]}` into the `(N-1)`th turn's `compression_metadata`, replacing the old value.
    - Reset `compression_depth = 1`.
    - Log the trigger reason, token comparison between old and new summaries, and confidence delta.
- Compression result write-back strategy:
  - When turn N reaches the compression threshold, compress turns 1 through N-2 and keep the most recent 2 turns raw.
  - After compression succeeds, store `{summary_text, confidence, compressed_rounds: [1, 2, ..., N-2]}` in a field on the `(N-1)`th message, such as `compressed_state` or `compression_metadata`, instead of storing it only in runtime memory.
  - On the next turn, loading history should automatically recover the `(N-1)`th turn's compression state. Use that compression summary plus the raw `(N-1)`th and Nth turns to compress incrementally again. Write the new result into turn N.
  - Retry protection: if turn N fails and is retried, the previous compression state should still be recoverable, instead of recomputing from scratch or losing earlier compression work.
  - Example:
    ```text
    Turn 5: load history [1, 2, 3, 4, 5] (no compression metadata)
    Turn 6: trigger compression, compress [1-4], keep [5], store {summary, confidence} in turn 5's compression_metadata
    Turn 7: load [5(with compression_metadata), 6], recompress from turn 5's summary + turn 6, store result in turn 6
    If turn 6 response fails and is retried: recover using turn 5 (with compression state) + turn 6, instead of recompressing [1-4] again
    ```

This response can be used as the implementation draft for code, templates, and tests. After confirmation, refine it into concrete template examples, a `PromptService` draft, and a CI compile-time validation script.

## Implementation Plan

### Spec alignment and deviation decisions

This implementation plan intentionally diverges from the constitution in five places. Each deviation has already been reviewed and decided.

#### Decision 1: Scenario field scope [Deviation | Medium risk | Decided]

- Constitution: `Scenario` has 5 fields: `product_type`, `issue_type`, `amount`, `jurisdiction`, `confidence`
- This week's decision: implement only 3 fields, `product_type: Optional[str]`, `issue_type: Optional[str]`, and `confidence: float`; do not implement `amount` or `jurisdiction` yet
- Reason: the current user problem and retrieval layer do not need amount or jurisdiction filtering. If needed later, it can be proposed separately.
- Impact:
  - `models/scenario.py` declares only three fields
  - `scenario_extraction.j2` outputs only three fields
  - `manifest.yaml` is updated accordingly
  - tests are updated to remove assertions about `amount` and `jurisdiction`
- Compatibility: runtime should safely ignore legacy data that still contains removed fields
- Acceptance: Scenario Pydantic schema has only three fields, render tests cover null and non-null values, and the PR clearly explains the scope reduction and future expansion path

#### Decision 2: Conversation history persistence [Deviation | High risk | Decided | migration needed]

- Constitution: the graph is stateless, and the caller passes the full `conversation_history`
- This week's decision: the backend persistently stores and loads `conversation_history`, so sessions can continue across requests
- Reason: it supports a better experience for multi-turn Q and A and lowers integration cost
- New API contract:
  ```python
  POST /analyze
  Request:  { "user_query": "...", "session_id": "opt_abc123" }
  Response: { "session_id": "abc123", "conversation_history": [..., new_turn], "result": {...} }
  ```
- Impact:
  - add a session table with `session_id`, `conversation_history` blob, `last_updated`, and so on
  - add session management code in `session_store.py`
  - update router, request and response schemas, and database migrations
  - update graph execution to support auto load and save
- Compatibility:
  1. If the request includes `session_id`, load the backend session first. If it also includes `conversation_history`, ignore that field or treat it only as debug compatibility, and never overwrite backend state.
  2. If the request does not include `session_id`, create a new session and return it.
  3. Both modes can coexist, but the server database remains the single source of truth for history. The client only returns `session_id`.
- Acceptance: the session table exists, migrations pass, compatibility tests cover the four combinations of session_id and history presence, persistence/load/concurrency have unit tests, and the PR documents migration and rollback steps

#### Decision 3: Prompt template storage path [Deviation | Medium risk | Decided | documentation update needed]

- Constitution says prompts live under `app/core/prompts/*.j2`
- The actual package name is `financial_agent_api`, not `app`
- This week's decision: use `src/financial_agent_api/core/prompts/*.j2` in the actual implementation, and document the mapping
- Reason: implement against the real package structure and avoid unnecessary directory reshuffling
- Impact:
  - create `src/financial_agent_api/core/prompts/`
  - add `.spdd_specs/Path_Mapping.md` to explain constitution vs actual path mapping
  - add `.spdd_specs/Migration_Plan.md` for a future package-path unification plan
- Acceptance: template files are created in the actual path, `PromptService` uses a hard-coded path constant, and the mapping docs exist under `.spdd_specs/`

#### Decision 4: PromptService configuration hard-coded [Deviation | Low risk | Decided]

- Constitution intent: StrictUndefined should be a configurable default
- This week's decision: hard-code StrictUndefined and the template directory path in code constants, not environment variables
- Reason:
  - reduce configuration complexity
  - StrictUndefined is a required safety policy and should not be toggleable at runtime
  - the template path is tightly coupled to code structure and does not need environment indirection
- Impact: `prompt_service.py` uses `Environment(undefined=StrictUndefined)` and a hard-coded template directory
- Acceptance: PromptService unit tests verify StrictUndefined behavior and code comments explain the design decision

#### Decision 5: Keep existing state field names [Deviation | Low risk | Decided]

- Background: the implementation plan includes node restructuring, especially `summarization` and `synthesise`, which could trigger field renaming
- This week's decision: do not rename fields. Keep `AgentState.analysis_notes` and `AgentState.final_answer`
- Reason: avoid widening the blast radius this week. Field renaming should be its own PR and data migration.
- Impact:
  - `summarization` output writes to `AgentState.analysis_notes`
  - `synthesise` output writes to `AgentState.final_answer`
- Acceptance: existing field slots remain in use, code comments clearly map nodes to fields, and tests cover both read and write paths

### 0. Preconditions before implementation

Understand and plan the five core deviation decisions above. The concrete implementation steps are listed in the sections below.

### 1. Prompt infrastructure

1. Add `PromptService` (recommended file: `src/financial_agent_api/core/prompt_service.py`).
   - Use Jinja2.
   - Hard-code `StrictUndefined`; do not make it an environment variable.
   - Hard-code the template directory path in source, do not add a `PROMPT_TEMPLATES_PATH` setting.
   - Minimum capability: `render(template_name, **kwargs)` plus template existence checks during startup and tests.

2. Add the template directory (recommended: `src/financial_agent_api/core/prompts/`).
   - Required templates this week:
     - `scenario_extraction.j2`
     - `compress_history.j2`
     - `summarization.j2`
     - `synthesise.j2`
   - Optional this week but not wired to the main graph:
     - `feedback_prompt.j2`

3. Wire template compile-time checks into the existing test or startup flow.
   - Minimum implementation: instantiate `PromptService` in unit tests and load each template.
   - Checkpoints:
     - template files exist
     - `StrictUndefined` is active
     - missing required variables raise an error, not an empty string

### 2. Data layer: `allowed_product_issue_map`

1. Add a complaints-derived table in the database to store valid `product` / `issue` combinations.
   - Recommended form: one row per valid combination, not one large JSON blob.
   - Purpose: easier validation, debugging, extensibility, and runtime assembly of the mapping.

2. Update the complaints ingestion flow so the derived table is refreshed after complaints refresh completes.
   - Existing entry point: `initialize_data.py -> ingest_public_data.py`
   - Suggested flow:
     - finish complaints upsert
     - regenerate unique `product` / `issue` combinations
     - overwrite the derived table

3. Provide runtime code that reads the derived table and assembles `allowed_product_issue_map`.
   - This can live in the retrieval service or a small dedicated reader service.
   - If the derived table does not exist or is empty:
     - skip `scenario_phase`
     - continue with docs retrieval and later nodes

### 3. State and model changes

1. Adjust the `Scenario` model to only contain:
   - `product_type: Optional[str]`
   - `issue_type: Optional[str]`
   - `confidence: float`
   - Note: do not add `amount` or `jurisdiction` this week. Update `models/scenario.py`, the related Pydantic schema, and affected tests to reflect the reduced model.

2. Keep the existing `AgentState` field slots this week.
   - `scenario`: stores `Scenario`
   - `analysis_notes`: stores `summarization` output
   - `final_answer`: stores `synthesise` output
   - Do not rename fields, nodes, or response names this week. Keep the blast radius small.

3. If we later decide to fully persist conversation history on the backend, it will affect:
   - `models/agent.py`
   - `routers/agent.py`
   - `agent/runner.py`
   - the history storage table or repository
   - related endpoint, graph, and tests
   - This week's plan does not include that refactor.

### 4. Graph and node refactor

1. Change the graph order to:
   - `ingest_input`
   - `compress_history`
   - `scenario_phase`
   - `retrieve`
   - `summarization`
   - `synthesise`

2. `ingest_input`
   - Keep it lightweight: validate that `user_query` exists.
   - `conversation_history` is no longer part of the client input contract. If old clients still send it, the backend should ignore it and use persisted server-side history.

3. `compress_history`
   - Implement it as a separate node or helper call after `ingest_input`.
   - Trigger condition: `len(conversation_history) > COMPRESS_THRESHOLD`.
   - Split strategy:
     - keep the most recent two turns verbatim
     - put earlier messages into `messages_to_compress`
   - Template call:
     - use `compress_history.j2`
     - output `{summary_text, confidence}`
   - Result handling:
     - if `confidence >= COMPRESS_CONFIDENCE_THRESHOLD`, write `[compressed summary] + [kept raw tail]` back into `conversation_history`
     - if below threshold, retry once more
     - if it still fails, abandon this compression run and log it
   - State strategy:
     - default to incremental compression
     - do not full-recompress every turn yet
     - leave code comments or extension points for full rebuild compression

4. `scenario_phase`
   - Read `allowed_product_issue_map`
   - If the map is empty: skip the node and set `scenario=None`. This is the only case where `scenario=None` may be returned silently.
   - If the map is non-empty:
     - call the LLM with `scenario_extraction.j2`
     - force JSON output
     - validate membership after parsing
   - Rules:
     - `product_type` can only be a valid key or `null`
     - `issue_type` can only be a valid value under the selected `product_type`, or `null`
     - high `confidence` plus `product_type=null` means there is no target product in complaints to reference, so complaints retrieval should be skipped
   - Failure strategy:
     - structured output parsing failure, low confidence, or membership validation failure can be retried once
     - if it still fails, trigger feedback and keep the user in the loop until a correct Scenario can be produced. Do not silently degrade to empty complaints retrieval.

   Implementation plan note for `USER_INPUT_VALIDATION_MODE`, for later implementation reference only:
   - Add `user_input_validation_mode: Literal['feedback', 'strict'] = 'feedback'` to `Settings` and list the values in `.env.example`.
   - Runtime behavior:
     - `feedback` (default) -> on input or scenario validation failure, trigger `feedback_prompt.j2` to generate a clarification prompt, stop the current graph, return to the caller, and record metrics `validation_failure_feedback` and `feedback_followup_rate`
     - `strict` -> on input or scenario validation failure, raise a structured validation error and let the API return 400 or 500, and record metric `validation_failure_strict`
   - Suggested implementation location: `ingest_input` or a dedicated input-validation middleware. Treat LLM parsing or schema-validation failure as a validation failure and route accordingly.
   - Observability and regression: add logs for mode, reason, and request_id, and A/B test in preproduction to measure follow-up rate and failure impact.

   Note: this is only a plan for now, not a Week-4 implementation item. Update the implementation guide and `.env.example` when implementing it.

5. `retrieve`
   - docs retrieval:
     - keep current behavior, using `user_query` for vector retrieval directly
   - complaints retrieval:
     - if `scenario=None` or `product_type=None`, skip complaints retrieval and do not open an unfiltered complaints query
     - if `scenario` exists and `product_type` is non-null, filter by `product`, and add `issue` if `issue_type` is non-null
     - if `scenario_phase` could not produce a trustworthy result because of low confidence, membership validation failure, or JSON parsing failure, go to feedback instead of falling back to unfiltered complaints retrieval
     - if complaints retrieval itself raises a database or system exception, treat it as a system failure and rethrow it. Do not silently return an empty array
   - parallel failure handling continues to follow Week 3 rules:
     - docs failures are system failures and must throw
     - complaints failures are system failures and must throw
     - if both fail, throw

6. `summarization`
   - move the inline prompt currently in `summarise_tool.py` into `summarization.j2`
   - inputs:
     - `user_query`
     - `conversation_history`
     - `retrieved_complaints`
     - `retrieved_docs`
   - output:
     - the document-layer semantic name is `summarization`
     - runtime writes into `AgentState.analysis_notes`

7. `synthesise`
   - move the inline prompt currently in `synthesise_answer_tool.py` into `synthesise.j2`
   - inputs:
     - `user_query`
     - `summarization` (runtime source: `analysis_notes`)
   - output:
     - final answer, written into `AgentState.final_answer`

8. `feedback` (this week may only require the template, not the main graph)
   - mainly used for:
     - low-confidence Scenario results
     - missing critical information
     - cases where complaints filters cannot be safely applied
   - if scope is tight, it is fine to define only the template and its inputs and outputs, without wiring it into the main path.

### 5. Tool and service refactor

1. `summarise_tool.py`
   - remove inline `system_prompt` and `user_prompt`
   - replace them with `PromptService.render("summarization.j2", ...)`

2. `synthesise_answer_tool.py`
   - remove inline prompts
   - replace them with `PromptService.render("synthesise.j2", ...)`

3. Add a `scenario_extraction` tool or node implementation
   - place it near `agent/tools/` or `agent/graph.py` to match the current style
   - keep it single-purpose: only structured extraction, no retrieval logic

4. Add a `compress_history` helper
   - recommended separate file, for example:
     - `agent/history_compression.py`
   - responsibilities:
     - split old history and keep the tail
     - render the template
     - check `confidence`
     - stitch `conversation_history` back together

5. `ServicesContainer`
   - inject `PromptService`
   - if needed, inject a small service for reading `allowed_product_issue_map`

### 6. Configuration and constants

1. Keep these environment variables:
   - `COMPRESS_THRESHOLD`
   - `COMPRESS_OPS_MODEL`
   - `COMPRESS_CONFIDENCE_THRESHOLD`

2. Hard-code or keep as source constants:
   - template directory path
   - `StrictUndefined`
   - `retain_last_n = 2`

3. Do not add these environment variables this week:
   - `PROMPT_TEMPLATES_PATH`
   - `PROMPT_STRICT_UNDEFINED`
   - `SCENARIO_EXTRACTION_RETRY`
   - `PROMPT_CACHE_*`

### 7. Test plan

1. `PromptService` unit tests
   - templates can be loaded
   - missing variables raise an error
   - missing template names raise an error

2. `compress_history` unit tests
   - history shorter than threshold: no compression
   - history longer than threshold: correct split and correct stitching
   - confidence below threshold: retry and then abandon compression
   - incremental compression: existing summary plus newly entered compression-window messages does not force a full recompression

3. `scenario_phase` unit tests
   - empty mapping: skip
   - valid `product_type` / `issue_type`: write `scenario` successfully
   - high `confidence` plus `product_type=null`: complaints retrieval should be skipped later
   - invalid member values: treat as invalid
   - second JSON parse failure: raise a structured error

4. Retrieval and graph tests
   - complaints are filtered correctly based on `scenario`
   - docs still depend only on `user_query`
   - if both retrieval paths fail, still throw according to Week 3 rules
   - graph order is `ingest_input -> compress_history -> scenario_phase -> retrieve -> summarization -> synthesise`

5. Endpoint and integration tests
   - `/agent/query` still returns a grounded answer
   - when `scenario_phase` is skipped or complaints are skipped, the docs path still works
   - no regression in old behavior after template migration

### 8. Recommended implementation order

1. Commit 1: `PromptService` + template directory + template loading tests
2. Commit 2: migrate `summarization` and `synthesise` inline prompts
3. Commit 3: complaints derived table + ingestion refresh of `allowed_product_issue_map`
4. Commit 4: implement `scenario_phase` + membership validation + complaints filtering
5. Commit 5: implement `compress_history` + threshold control + confidence checks
6. Commit 6: adjust graph order and node naming, add graph-level tests
7. Commit 7: add the feedback template if time remains

### 9. Explicit non-goals this week

1. Do not implement prompt cache.
2. Do not introduce a retrieve query rewrite template.
3. Do not force `feedback_prompt.j2` into the main path unless the earlier steps are stable.
4. Do not implement the new backend-owned full-session-history architecture this week unless the constitution and API contract are updated first.
