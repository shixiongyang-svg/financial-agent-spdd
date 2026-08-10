from __future__ import annotations

import getpass
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

MODELS_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
TIMEOUT_SECONDS = 30
PAGE_SIZE = 500
MAX_CATALOG_MODELS = 5000
MAX_MODELS_TO_TRY = 8
MAX_RETRIES_PER_MODEL = 1
MAX_RETRY_WAIT_SECONDS = 8
TEST_CHAT_MESSAGE = "Please reply with exactly: smoke-test-ok"
INFINITE_PRICE = Decimal("Infinity")
ROOT_DIR = Path(__file__).resolve().parents[1]
LLM_ENV_PATH = ROOT_DIR / ".local-config" / "llm.env"


def fetch_models_catalog(output_modalities: str) -> list[dict]:
    models: list[dict] = []
    offset = 0
    while offset < MAX_CATALOG_MODELS:
        query = urllib.parse.urlencode(
            {
                "output_modalities": output_modalities,
                "limit": PAGE_SIZE,
                "offset": offset,
            }
        )
        request = urllib.request.Request(f"{MODELS_URL}?{query}", method="GET")
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected model catalog payload: {payload}")
        page_items = [item for item in data if isinstance(item, dict)]
        models.extend(page_items)
        if len(data) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    deduped: list[dict] = []
    seen: set[str] = set()
    for model in models:
        model_id = model.get("id")
        if isinstance(model_id, str) and model_id not in seen:
            seen.add(model_id)
            deduped.append(model)
    return deduped


def model_ids(catalog: list[dict], exclude_free: bool = True) -> list[str]:
    ids: list[str] = []
    for model in catalog:
        model_id = model.get("id")
        if not isinstance(model_id, str):
            continue
        if exclude_free and model_id.endswith(":free"):
            continue
        ids.append(model_id)
    return sorted(set(ids))


def parse_decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def read_optional_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        current_key, raw_value = line.split("=", 1)
        if current_key.strip() != key:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return None


def model_price(model: dict, *, kind: str) -> Decimal:
    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        return INFINITE_PRICE

    prompt = parse_decimal(pricing.get("prompt"))
    if prompt is None:
        return INFINITE_PRICE

    if kind == "embedding":
        return prompt

    completion = parse_decimal(pricing.get("completion"))
    if completion is None:
        return INFINITE_PRICE

    return prompt + completion


def prioritize_by_price(catalog: list[dict], *, kind: str) -> list[str]:
    candidates: list[tuple[Decimal, str]] = []
    for model in catalog:
        model_id = model.get("id")
        if not isinstance(model_id, str) or model_id.endswith(":free"):
            continue
        price = model_price(model, kind=kind)
        candidates.append((price, model_id))

    candidates.sort(key=lambda item: (item[0], item[1]))
    return [model_id for _, model_id in candidates]


def ordered_completion_models(chat_catalog: list[dict]) -> list[str]:
    return prioritize_by_price(chat_catalog, kind="chat")


def ordered_embedding_models(embedding_catalog: list[dict]) -> list[str]:
    return prioritize_by_price(embedding_catalog, kind="embedding")


def prioritized_candidates(
    preferred_model: str | None,
    ranked_models: list[str],
    *,
    skip_models: set[str] | None = None,
) -> list[str]:
    candidates: list[str] = []
    skipped = skip_models or set()
    if preferred_model and preferred_model not in skipped:
        candidates.append(preferred_model)
    for model in ranked_models:
        if model not in candidates and model not in skipped:
            candidates.append(model)
    return candidates


def request_chat_completion(api_key: str, model: str, user_message: str) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        CHAT_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        result = json.loads(response.read().decode("utf-8"))

    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Unexpected response format: {result}")

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    raise RuntimeError(f"Unexpected message content format: {content!r}")


def request_embedding(api_key: str, model: str, text: str) -> int:
    payload = {"model": model, "input": text}
    request = urllib.request.Request(
        EMBEDDINGS_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        result = json.loads(response.read().decode("utf-8"))

    data = result.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Unexpected embedding response: {result}")

    first = data[0]
    if not isinstance(first, dict):
        raise RuntimeError(f"Unexpected embedding response item: {first!r}")

    embedding = first.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError(f"Unexpected embedding vector: {embedding!r}")
    return len(embedding)


def parse_retry_after_seconds(exc: urllib.error.HTTPError, response_body: str) -> int:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after and retry_after.isdigit():
        return max(1, int(retry_after))

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return 2

    metadata = payload.get("error", {}).get("metadata", {}) if isinstance(payload, dict) else {}
    retry_seconds = metadata.get("retry_after_seconds")
    if isinstance(retry_seconds, int) and retry_seconds > 0:
        return retry_seconds
    if isinstance(retry_seconds, float) and retry_seconds > 0:
        return int(retry_seconds) + 1
    return 2


def print_candidate_preview(title: str, catalog: list[dict], *, kind: str) -> list[str]:
    ordered = prioritize_by_price(catalog, kind=kind)
    print(title)
    if not ordered:
        print("  (none)")
        return []

    preview_limit = min(10, len(ordered))
    price_by_id = {
        model.get("id"): model_price(model, kind=kind)
        for model in catalog
        if isinstance(model.get("id"), str)
    }
    for model_id in ordered[:preview_limit]:
        print(f"  - {model_id}  [estimated price: {price_by_id.get(model_id, INFINITE_PRICE)}]")
    return ordered


def try_chat_model(api_key: str, user_message: str, model: str) -> str | None:
    attempt = 0
    while attempt <= MAX_RETRIES_PER_MODEL:
        try:
            return request_chat_completion(api_key=api_key, model=model, user_message=user_message)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < MAX_RETRIES_PER_MODEL:
                raw_wait = parse_retry_after_seconds(exc, body)
                if raw_wait > MAX_RETRY_WAIT_SECONDS:
                    print(
                        f"Model {model} got 429 with Retry-After={raw_wait}s "
                        f"(>{MAX_RETRY_WAIT_SECONDS}s cap). Skipping retry for this model."
                    )
                    return None
                wait_seconds = max(1, raw_wait)
                print(
                    f"Model {model} got 429. Waiting {wait_seconds}s and retrying "
                    f"({attempt + 1}/{MAX_RETRIES_PER_MODEL})..."
                )
                time.sleep(wait_seconds)
                attempt += 1
                continue
            if exc.code == 429:
                print(f"Model {model} is rate-limited.")
                return None
            if exc.code in {500, 502, 503, 504}:
                print(f"Model {model} is temporarily unavailable (HTTP {exc.code}).")
                return None
            print(f"Request failed with HTTP {exc.code}: {body}")
            return None
        except urllib.error.URLError as exc:
            print(f"Request failed: {exc}")
            return None
        except (json.JSONDecodeError, RuntimeError) as exc:
            print(f"Failed to parse completion response: {exc}")
            return None
    return None


def try_embedding_model(api_key: str, model: str, text: str) -> int | None:
    attempt = 0
    while attempt <= MAX_RETRIES_PER_MODEL:
        try:
            return request_embedding(api_key=api_key, model=model, text=text)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < MAX_RETRIES_PER_MODEL:
                raw_wait = parse_retry_after_seconds(exc, body)
                if raw_wait > MAX_RETRY_WAIT_SECONDS:
                    print(
                        f"Embedding model {model} got 429 with Retry-After={raw_wait}s "
                        f"(>{MAX_RETRY_WAIT_SECONDS}s cap). Skipping retry for this model."
                    )
                    return None
                wait_seconds = max(1, raw_wait)
                print(
                    f"Embedding model {model} got 429. Waiting {wait_seconds}s and retrying "
                    f"({attempt + 1}/{MAX_RETRIES_PER_MODEL})..."
                )
                time.sleep(wait_seconds)
                attempt += 1
                continue
            if exc.code in {400, 404, 422}:
                return None
            if exc.code in {429, 500, 502, 503, 504}:
                return None
            print(f"Embedding request failed with HTTP {exc.code}: {body}")
            return None
        except urllib.error.URLError as exc:
            print(f"Embedding request failed: {exc}")
            return None
        except (json.JSONDecodeError, RuntimeError):
            return None
    return None


def try_model_candidates(
    *,
    api_key: str,
    candidates: list[str],
    request_fn,
) -> tuple[str, object] | None:
    for model in candidates[:MAX_MODELS_TO_TRY]:
        result = request_fn(api_key, model)
        if result is not None:
            return model, result
    return None


def try_model_with_optional_fallback(
    *,
    api_key: str,
    preferred_model: str | None,
    output_modalities: str,
    request_fn,
    preview_title: str,
    kind: str,
) -> tuple[str, object] | None:
    if preferred_model:
        print(f"Trying preferred {kind} model from {LLM_ENV_PATH}: {preferred_model}")
        result = request_fn(api_key, preferred_model)
        if result is not None:
            return preferred_model, result
        print(f"Preferred {kind} model failed validation, falling back to model catalog.")

    try:
        catalog = fetch_models_catalog(output_modalities=output_modalities)
    except urllib.error.URLError as exc:
        print(f"Failed to fetch {kind} model catalog: {exc}")
        return None
    except json.JSONDecodeError as exc:
        print(f"Failed to parse {kind} model list response: {exc}")
        return None
    except RuntimeError as exc:
        print(str(exc))
        return None

    candidates = print_candidate_preview(
        preview_title,
        catalog,
        kind=kind,
    )
    candidates = prioritized_candidates(
        preferred_model,
        candidates,
        skip_models={preferred_model} if preferred_model else None,
    )

    if not candidates:
        print(f"No paid {kind} model was discovered from OpenRouter.")
        return None

    return try_model_candidates(
        api_key=api_key,
        candidates=candidates,
        request_fn=request_fn,
    )


def main() -> int:
    print("OpenRouter paid-model smoke test")
    print("-" * 40)
    api_key = getpass.getpass("Enter OPENROUTER_API_KEY (input hidden): ").strip()
    if not api_key:
        print("Error: OPENROUTER_API_KEY is required.")
        return 1

    preferred_chat_model = read_optional_env_value(LLM_ENV_PATH, "OPENROUTER_MODEL")
    preferred_embedding_model = read_optional_env_value(LLM_ENV_PATH, "EMBEDDING_MODEL")
    preferred_embedding_dim = read_optional_env_value(LLM_ENV_PATH, "EMBEDDING_DIM")

    if preferred_chat_model or preferred_embedding_model:
        print(f"Loaded optional model overrides from {LLM_ENV_PATH}")
        if preferred_chat_model:
            print(f"  OPENROUTER_MODEL={preferred_chat_model}")
        if preferred_embedding_model:
            print(f"  EMBEDDING_MODEL={preferred_embedding_model}")
        if preferred_embedding_dim:
            print(f"  EMBEDDING_DIM={preferred_embedding_dim}")

    user_message = TEST_CHAT_MESSAGE
    print(f"Using built-in chat test message: {user_message!r}")

    chat_result = try_model_with_optional_fallback(
        api_key=api_key,
        preferred_model=preferred_chat_model,
        output_modalities="text",
        request_fn=lambda key, model: try_chat_model(key, user_message, model),
        preview_title="Paid completion candidates ordered by estimated price:",
        kind="chat",
    )
    if chat_result is None:
        print("All discovered chat models are currently rate-limited or unavailable. Please retry shortly.")
        return 1

    chat_model, answer = chat_result
    print(f"\nUsed completion model: {chat_model}")
    print("\nModel response:")
    print(answer)

    embedding_result = try_model_with_optional_fallback(
        api_key=api_key,
        preferred_model=preferred_embedding_model,
        output_modalities="embeddings",
        request_fn=lambda key, model: try_embedding_model(key, model, "OpenRouter embedding smoke test."),
        preview_title="Paid embedding candidates ordered by estimated price:",
        kind="embedding",
    )
    if embedding_result is None:
        print("\nCould not find an available embedding model right now. Please retry shortly.")
        return 1

    embedding_model, embedding_dim = embedding_result
    print(f"\nUsed embedding model: {embedding_model}")
    print(f"Detected embedding dimension: {embedding_dim}")
    print("\nRecommended env values:")
    print(f"OPENROUTER_MODEL={chat_model}")
    print(f"EMBEDDING_MODEL={embedding_model}")
    print(f"EMBEDDING_DIM={embedding_dim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
