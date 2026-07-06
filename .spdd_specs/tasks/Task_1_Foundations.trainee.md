# Task 1 — Foundations (REASONS Canvas, trainee edition)

> **Trainee-edition posture.** This is the canvas you receive on
> Day 1 of Week 1. It is intentionally **under-specified** in places —
> the missing detail is the work you are expected to do during your
> analysis-step + canvas-completion practice. The destination state
> for this task lives in `Task_1_Foundations.md`; do not read that
> file until your mentor signs off this canvas. Sections you must
> complete before generating code are marked **TODO(trainee)**.
>
> **Maps to:** Learning Plan Week 1 — *Python Foundations & Service Abstractions*.
> **Depends on:** `Task_0_Environment.md` (already complete and identical
> to the destination version).
> **Unblocks:** `Task_2_Ingestion.trainee.md`, `Task_3_Orchestration.trainee.md`.

---

## Requirements

### Analysis context

TODO AI update the mentioned directories, artifacts, etc. based on the current implementation; if they don't exist, mark them as not existing.

**Domain keywords scanned:** LLMService, OpenRouter, Ollama,
embeddings, settings, request_id, structured logging, retries.
**Existing artifacts:** `.env.example`, the `app/` skeleton from
Task 0. **Prior tasks read:** Task 0 (env keys, healthz, settings
stub).

**Strategic direction:** one provider-agnostic facade over chat +
embeddings, configured by `Settings`. Retries and structured-output
parsing live behind the facade, never in the caller. Errors are
typed so callers can decide policy without sniffing message
strings.

**TODO(trainee) — Risks noticed.** Before writing any code, list
**at least three** risks you think this Task introduces and how
your design mitigates them. Examples of the *kind* of risk to
think about: provider response-shape drift, retry-induced cost
amplification, request_id correlation gaps, secret leakage in
logs. Land your answer here as a numbered list before opening a
PR.

1. No multi-environment configuration introduced yet
2. Plaintext configuration in environment variables
3. Continuous error handling after API KEY expiry or quota exceeded
4. No mention of how to constrain the LLM response to a fixed format
5. After response message parsing fails, there is no failure cause analysis — e.g., whether it was due to a malformed structured input message, or an occasional LLM issue causing unexpected output; should such errors be re-submitted to the LLM for analysis to optimize the input message?
6. No AsyncClient-level log interceptor is used; when modifying logs, locations that need to be changed may be missed
7. Settings directly supports `python -c` invocation in all environments, leading to config info leakage; additional restrictions should be in place
8. Retry node control to avoid nested retries
9. Truncated prompts in logs are actually very important information in certain scenarios — should we consider full storage somewhere depending on context?

### Why this task exists

The agent needs **one place** that knows how to talk to LLMs and
**one place** that knows how to read configuration. Without these
abstractions, every retrieval/synthesis/evaluation script would
couple itself directly to OpenRouter or Ollama, which makes the
codebase impossible to test, reason about, or swap providers in.
Task 1 also introduces the structured-logging contract that
everything downstream depends on for observability and request
correlation.

### Acceptance criteria (Given/When/Then)

These are the contract; do not soften them.

- **Given** valid env variables in `.env`,
  **when** `python -c "from app.core.config import get_settings;
  print(get_settings().openrouter_model)"` runs,
  **then** it prints the configured model name without raising.
- **Given** `LLM_PROVIDER=openrouter` and a missing
  `OPENROUTER_API_KEY`,
  **when** `get_settings()` is called,
  **then** Pydantic raises a `ValueError` from the `model_validator`
  naming the missing key. (Under `LLM_PROVIDER=ollama` the key is
  optional.)
- **Given** an `LLMService` instance configured for OpenRouter and a
  test that mocks the underlying `httpx.AsyncClient`,
  **when** `await llm.complete(messages=[{"role":"user","content":"hi"}])`
  is invoked,
  **then** the mocked HTTP layer receives a POST to
  `https://openrouter.ai/api/v1/chat/completions`.
- **Given** an `LLMService` instance configured for Ollama and a
  test that mocks the underlying `httpx.AsyncClient`,
  **when** `await llm.complete(...)` is invoked,
  **then** the mocked HTTP layer receives a POST to
  `http://localhost:11434/api/chat` and unwraps `message.content`.
- **Given** a transient HTTP 5xx response,
  **when** `LLMService.complete` runs,
  **then** the call retries with exponential backoff up to **3
  attempts** before raising `LLMProviderError`.
- **Given** any service or LangGraph node logs a structured event,
  **when** `LOG_FORMAT=json`,
  **then** every record contains at minimum `timestamp`, `level`,
  `request_id`, `event`, and (where applicable) `duration_ms`.

---

## Entities

| Entity | Spec |
|---|---|
| `Settings` | Pydantic Settings model for the env keys listed in Root Architecture. |
| `LLMService` | Provider-agnostic facade. Two methods: `complete` (chat) and `embed` (batch embeddings). |
| `LLMProviderError` | Custom exception. Carries `provider`, `status_code`, `payload`, `request_id`. |
| `LLMOutputValidationError` | Custom exception raised when a structured-output parse fails. (Used in Task 4 but defined here.) |
| `request_id` | UUIDv4. Generated by middleware. Threaded into every log line. |
| `ServicesContainer` | Plain dataclass that bundles `Settings` + `LLMService`. Constructed once in `app/api/main.py` lifespan. |

### Class diagram — TODO(trainee)

> The Constitution's *SPDD discipline* norm requires every Task
> canvas to ship a `classDiagram` (or `flowchart` when the topology
> is graph-shaped) inside the Entities section. Draw one here using
> Mermaid before generating code. Suggested shape:
> `Settings`, `LLMService`, `ServicesContainer`,
> `LLMProviderError`, `LLMOutputValidationError`. Show containment
> (`ServicesContainer` *owns* `Settings`, `LLMService`) and
> dependencies (`LLMService` *raises* both exceptions; `LLMService`
> *reads* `Settings`).

---

## Approach

### Design decisions

1. **Single `Settings` class** with a Pydantic `model_validator`
   that raises early when required env keys are missing. No
   per-module env reads scattered through the codebase.
2. **One `LLMService` facade** with two methods (`complete`,
   `embed`). Provider differences (Ollama vs OpenRouter) live
   *inside* the service; callers never see them.
3. **A thin HTTP layer** (`LLMHTTPClient` wrapping
   `httpx.AsyncClient`) so tests can swap in `httpx.MockTransport`
   without monkey-patching the whole network stack.
4. **Typed exceptions** (`LLMProviderError`,
   `LLMOutputValidationError`) so callers branch on type, not on
   error-string parsing.
5. **Structured logging via ContextVar.** A `request_id`
   middleware binds the id once at API ingress; loggers read from
   the ContextVar. No threading the id through every function
   signature.

### TODO(trainee) — Trade-offs accepted

> List the trade-offs your chosen design accepts. Hint: think
> about retry budget vs latency, log volume vs traceability,
> Pydantic-validation strictness vs developer ergonomics, and
> structured-output enforcement vs LLM compliance. **At least
> three** items, each with the form *"we accept X because Y, even
> though Z."* This list is what your reviewer will check against
> in code review.

#### Retry budget vs latency

When LLMService sends requests through different providers via LLMHttpClient, retryable errors such as network fluctuations or request timeouts are unavoidable.
Each retry incurs additional token consumption, and token consumption is related to prompt size — so the number of retries must be controlled, and different retry strategies should be used for different prompt sizes.
Additionally, given a fixed maximum request time, the longer each delay, the fewer total retries are possible.

Therefore, we must consider a reasonable retry budget to decide — within a fixed total duration — how to determine retry strategy based on different prompts.

##### Dimensions to consider

1. Which errors are retryable?
2. How many retries for a given prompt size?
3. Is it reasonable to correlate prompt size with token usage? If so, should we determine the number of retries within a fixed duration based on the prompt?

##### Options

TODO AI fill in (retain this "AI-filled" note after filling)

##### Final choice

After AI fills in the options, the user decides based on the trade-offs.

#### Log volume vs traceability

In log-based tracing, too many logs improve traceability but cause log volume to multiply, and vice versa.
Therefore, the code should first be decomposed into logical units.
Within the same logical unit, only input and output logs are needed (since logical units can be unit-tested or manually tested — with input + output, any request can be reproduced).

We can consider a same-process context, where no other logical unit has been interleaved, to be a single logical unit — for example:

A method entry called by another process is the input of a logical unit; returning from the method is the output.
Within a process, if another process is invoked — e.g., another thread or an HTTP request — that is considered the start of another logical unit, and the call parameters and returned results should be logged.

##### Options

TODO AI fill in (retain this "AI-filled" note after filling)

##### Final choice

After AI fills in the options, the user decides based on the trade-offs.

#### Pydantic validation strictness vs developer ergonomics

On this dimension, I believe there are not many trade-offs to make. From a data perspective, all necessary validations should be present — even if tedious, developers should comply, especially with AI assistance reducing repetitive development burden.

However, there is still one consideration: given that basic data format validation is in place, constraints should be relaxed as much as possible. For example, a phone number only needs to be numeric — it does not need to validate length, prefix, etc.

##### Options

TODO AI fill in (retain this "AI-filled" note after filling)

##### Final choice

After AI fills in the options, the user decides based on the trade-offs.

#### Structured-output enforcement vs LLM compliance

While enforcing structured output, some information that does not satisfy LLM compliance requirements may be produced.

We should not display/store non-compliant information in any place unless necessary. If it truly needs to be logged/stored, at minimum it should carry a clearly unified label identifying the compliance risk. Additionally, the information should be masked to varying degrees based on its specific attributes. If plaintext output is explicitly required, batch-retrieval interfaces for such information must not exist; a dedicated interface must be provided for retrieval, with a clear audit log inside that interface (who, at what time, accessed which compliance-sensitive data of which record).

##### Options

TODO AI fill in (retain this "AI-filled" note after filling)

##### Final choice

After AI fills in the options, the user decides based on the trade-offs.

---

## Structure

### File layout

TODO AI update the directory structure based on the current state of the directory.

```
app/
├── core/
│   ├── config.py             # Settings + get_settings()
│   ├── logging.py            # configure_logging + bind_request_id
│   ├── exceptions.py         # LLMProviderError, LLMOutputValidationError
│   └── services_container.py # ServicesContainer dataclass
├── services/
│   ├── llm_client.py         # LLMHTTPClient (httpx wrapper)
│   └── llm_service.py        # LLMService (provider switch)
└── api/
    └── main.py               # lifespan wires the container; /readyz added here
```

### Method signatures (the contract)

TODO AI update Settings based on the config truly needed up to this task, rather than setting everything at once; therefore the Settings content needs to be updated.

TODO AI expand method purpose descriptions; if there are external links for supplementary explanation, include them as well.

```python
# app/core/config.py
class Settings(BaseSettings):
    pg_dsn: str
    llm_provider: Literal["ollama", "openrouter"] = "ollama"
    log_format: Literal["json", "text"] = "text"
    # Conditional, see Acceptance Criteria
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "gpt-4.1-mini"
    # Defaulted
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gemma3:27b"
    ollama_ops_model: str = "qwen3.5:4b"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

@lru_cache
def get_settings() -> Settings: ...

# app/services/llm_service.py
class LLMService:
    def __init__(self, settings: Settings, http_client: LLMHTTPClient) -> None: ...
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: str | None = None,
        request_id: str | None = None,
    ) -> str: ...
    async def embed(
        self,
        inputs: list[str],
        *,
        model: str | None = None,
        request_id: str | None = None,
    ) -> list[list[float]]: ...
```

---

## Operations (strict execution order)

TODO AI update the mentioned file or directory locations based on the previous directory structure.

> The first 4 steps are pinned. Steps 5+ are **TODO(trainee)** —
> derive them from the Acceptance Criteria + your Approach. Your
> mentor will sign off the full Operations list before you generate
> code.

1. **Replace the Task 0 `Settings` stub** in `app/core/config.py`
   with the full Pydantic Settings model from *Structure*. Add the
   `@lru_cache` factory.
2. **Implement `app/core/logging.py`** with `configure_logging` and
   `bind_request_id`. Read formats from `Settings.log_format`.
3. **Implement `app/core/exceptions.py`** with the two exception
   classes. They must serialise their `payload` safely if printed.
4. **Implement `app/services/llm_client.py`** wrapping
   `httpx.AsyncClient`. The constructor accepts `base_url`, `api_key`,
   and an optional `transport` so tests can inject
   `httpx.MockTransport`.

5. **TODO(trainee) — implement `LLMService`** for both providers.
   Hint: a "transient" failure is not just HTTP 5xx — it also
   includes connection-level errors (`httpx.TimeoutException`,
   `httpx.RequestError`). Decide your retry predicate before
   you write the loop and document the choice in your
   Trade-offs section.
   For `complete`, use the chat endpoints already pinned in the
   acceptance criteria. For `embed`, the canonical paths are
   `embeddings` (OpenRouter) and `api/embeddings` (Ollama, one
   vector per call — you'll write a small client-side batch
   loop). Document any deviations in your Trade-offs.
6. **TODO(trainee) — wire `ServicesContainer` into `app/api/main.py`
   lifespan and add `/readyz`.** While you are in `main.py`, add
   the request-id middleware: read an incoming `X-Request-Id`
   header if present, otherwise generate a UUIDv4; bind it via
   `bind_request_id`; and set `X-Request-Id` on the outgoing
   response so downstream services can correlate. The HTTP
   header is the public contract; the ContextVar is the in-process
   carrier.
7. **TODO(trainee) — write tests**: `test_config.py`,
   `test_llm_service.py` (with `httpx.MockTransport`),
   `test_logging.py`. Aim for 100% coverage of the new modules.
8. **Update `README.md`** with a *Local development* section that
   covers `poetry install`, the canonical Ollama path (`ollama pull
   …`), and how to run `pytest` + `mypy --strict`. The destination
   README's *Local development* section is a useful reference *after*
   you draft yours.
9. **Verify** by running `pytest`, `ruff check .`, `mypy --strict
   --explicit-package-bases app data_pipelines`, and
   `./scripts/smoke.sh` (the script exists from Task 3+; until then,
   manually `curl /healthz` and `curl /readyz`).

---

## Norms

- Constructor-based DI only. No global singletons.
- All new functions are type-hinted; `mypy --strict` passes.
- Async by default for I/O paths.
- Pydantic v2 for all DTOs.
- Structured logging carries `request_id` on every record.
- Public service methods (`complete`, `embed`) declare
  `request_id: str | None = None`. The default `None` is
  resolved to the ContextVar's bound value at log time, never
  logged as `null`. Safeguard 4 below forbids *bypassing* the
  ContextVar by inventing ad-hoc kwargs; it does NOT forbid the
  documented `request_id` parameter.
- Truncate prompts in logs at 500 chars with a `_truncated: true`
  flag.

---

## Safeguards

1. **Do not import `os.getenv` outside `app/core/config.py`.**
   Every other module reads from a `Settings` instance.
2. **Do not silently swallow LLM errors.** Retries are bounded and
   the final failure raises `LLMProviderError` with the upstream
   payload.
3. **Do not log the `OPENROUTER_API_KEY`** or any header that
   contains it. Redact at the logging layer.
4. **Do not bypass `bind_request_id`** by passing `request_id`
   through arbitrary kwargs. The ContextVar is the canonical
   carrier.
5. **Do not commit a real API key.** `.env` is gitignored;
   `.env.example` ships placeholders only.

---

> **Spec drift watch.** When your implementation diverges from this
> canvas (e.g. you discover the LLM client needs a `timeout`
> parameter that wasn't documented), edit this canvas FIRST in the
> same PR — that's the project's *SPDD discipline* norm. A code-only
> diff with stale specs is a review block.

## Post-reading questions

TODO AI needs to fill in answers to these questions based on the questions below. After the user confirms all questions are resolved, proceed to fill in the implementation plan.

1. For the TODO risk identification above, I listed 8 items — for each one, indicate whether it is a risk that must be resolved in the current phase; if so, a clear resolution approach must be specified in the implementation plan.
2. What is OpenRouter? How do you use it?
3. What is Ollama? How do you use it?
4. In what situations should `LLMProviderError` appear?
5. In what situations should `LLMOutputValidationError` appear?
6. Are there multi-threading scenarios? If so, how can `request_id` be retrieved across threads?
7. What mechanisms does Python use to implement singletons and containers? What are the underlying principles?
8. For truncated prompts appearing in logs, should they be stored somewhere in full?


## Implementation plan

TODO AI generate the implementation plan; execute according to the plan after user approval.
