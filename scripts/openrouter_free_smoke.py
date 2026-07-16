from __future__ import annotations

import getpass
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

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

    # Deduplicate by id while preserving order.
    deduped: list[dict] = []
    seen: set[str] = set()
    for model in models:
        model_id = model.get("id")
        if isinstance(model_id, str) and model_id not in seen:
            seen.add(model_id)
            deduped.append(model)
    return deduped


def model_ids(catalog: list[dict], require_free: bool) -> list[str]:
    ids: list[str] = []
    for model in catalog:
        model_id = model.get("id")
        if not isinstance(model_id, str):
            continue
        if require_free and not model_id.endswith(":free"):
            continue
        ids.append(model_id)
    return sorted(set(ids))


def prioritize_models(models: list[str], preferred_keywords: tuple[str, ...]) -> list[str]:
    prioritized: list[str] = []
    remaining = list(dict.fromkeys(models))
    for keyword in preferred_keywords:
        for model in list(remaining):
            if keyword in model.lower():
                prioritized.append(model)
                remaining.remove(model)
    return prioritized + remaining


def ordered_chat_models(free_chat_models: list[str]) -> list[str]:
    preferred_keywords = ("qwen", "llama", "gemma", "mistral", "deepseek")
    return prioritize_models(free_chat_models, preferred_keywords)


def ordered_embedding_models(embedding_catalog: list[dict]) -> tuple[list[str], bool]:
    free_candidates = model_ids(embedding_catalog, require_free=True)
    paid_candidates = model_ids(embedding_catalog, require_free=False)
    paid_candidates = [model for model in paid_candidates if model not in free_candidates]
    preferred_keywords = ("text-embedding", "bge", "e5", "nomic", "gte", "embed")
    ordered_free = prioritize_models(free_candidates, preferred_keywords)
    ordered_paid = prioritize_models(paid_candidates, preferred_keywords)
    ordered = ordered_free + ordered_paid
    if "openai/text-embedding-3-small" in paid_candidates and "openai/text-embedding-3-small" not in ordered:
        ordered.append("openai/text-embedding-3-small")
    return ordered, bool(ordered_free)


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

    metadata = (
        payload.get("error", {}).get("metadata", {})
        if isinstance(payload, dict)
        else {}
    )
    retry_seconds = metadata.get("retry_after_seconds")
    if isinstance(retry_seconds, int) and retry_seconds > 0:
        return retry_seconds
    if isinstance(retry_seconds, float) and retry_seconds > 0:
        return int(retry_seconds) + 1
    return 2


def try_chat_with_fallback(api_key: str, user_message: str, model_candidates: list[str]) -> tuple[str, str] | None:
    for model in model_candidates[:MAX_MODELS_TO_TRY]:
        attempt = 0
        while attempt <= MAX_RETRIES_PER_MODEL:
            try:
                answer = request_chat_completion(api_key=api_key, model=model, user_message=user_message)
                return model, answer
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < MAX_RETRIES_PER_MODEL:
                    raw_wait = parse_retry_after_seconds(exc, body)
                    if raw_wait > MAX_RETRY_WAIT_SECONDS:
                        print(
                            f"Model {model} got 429 with Retry-After={raw_wait}s "
                            f"(>{MAX_RETRY_WAIT_SECONDS}s cap). Skipping retry for this model."
                        )
                        break
                    wait_seconds = max(1, raw_wait)
                    print(
                        f"Model {model} got 429. Waiting {wait_seconds}s and retrying "
                        f"({attempt + 1}/{MAX_RETRIES_PER_MODEL})..."
                    )
                    time.sleep(wait_seconds)
                    attempt += 1
                    continue
                if exc.code == 429:
                    print(f"Model {model} is rate-limited. Trying next free model...")
                    break
                if exc.code in {500, 502, 503, 504}:
                    print(f"Model {model} is temporarily unavailable (HTTP {exc.code}). Trying next...")
                    break
                print(f"Request failed with HTTP {exc.code}: {body}")
                return None
            except urllib.error.URLError as exc:
                print(f"Request failed: {exc}")
                return None
            except (json.JSONDecodeError, RuntimeError) as exc:
                print(f"Failed to parse completion response: {exc}")
                return None
    return None


def try_embedding_with_fallback(api_key: str, candidates: list[str]) -> tuple[str, int] | None:
    test_text = "OpenRouter embedding smoke test."
    for model in candidates[:MAX_MODELS_TO_TRY]:
        attempt = 0
        while attempt <= MAX_RETRIES_PER_MODEL:
            try:
                embedding_dim = request_embedding(api_key=api_key, model=model, text=test_text)
                return model, embedding_dim
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < MAX_RETRIES_PER_MODEL:
                    raw_wait = parse_retry_after_seconds(exc, body)
                    if raw_wait > MAX_RETRY_WAIT_SECONDS:
                        print(
                            f"Embedding model {model} got 429 with Retry-After={raw_wait}s "
                            f"(>{MAX_RETRY_WAIT_SECONDS}s cap). Skipping retry for this model."
                        )
                        break
                    wait_seconds = max(1, raw_wait)
                    print(
                        f"Embedding model {model} got 429. Waiting {wait_seconds}s and retrying "
                        f"({attempt + 1}/{MAX_RETRIES_PER_MODEL})..."
                    )
                    time.sleep(wait_seconds)
                    attempt += 1
                    continue
                if exc.code in {400, 404, 422}:
                    break
                if exc.code in {429, 500, 502, 503, 504}:
                    break
                print(f"Embedding request failed with HTTP {exc.code}: {body}")
                return None
            except urllib.error.URLError as exc:
                print(f"Embedding request failed: {exc}")
                return None
            except (json.JSONDecodeError, RuntimeError):
                break
    return None


def main() -> int:
    print("OpenRouter free-tier quick smoke test")
    print("-" * 40)
    api_key = getpass.getpass("Enter OPENROUTER_API_KEY (input hidden): ").strip()
    if not api_key:
        print("Error: OPENROUTER_API_KEY is required.")
        return 1

    try:
        chat_catalog = fetch_models_catalog(output_modalities="text")
        embedding_catalog = fetch_models_catalog(output_modalities="embeddings")
    except urllib.error.URLError as exc:
        print(f"Failed to fetch models: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"Failed to parse model list response: {exc}")
        return 1
    except RuntimeError as exc:
        print(str(exc))
        return 1

    free_chat_models = model_ids(chat_catalog, require_free=True)
    if not free_chat_models:
        print("No :free chat model is currently available from OpenRouter.")
        return 1

    chat_candidates = ordered_chat_models(free_chat_models)
    print(f"Found {len(free_chat_models)} free chat models.")
    print("Sample free models:")
    for model in chat_candidates[:10]:
        print(f"  - {model}")
    print(f"Initial model: {chat_candidates[0]}")

    user_message = TEST_CHAT_MESSAGE
    print(f"Using built-in chat test message: {user_message!r}")

    chat_result = try_chat_with_fallback(api_key=api_key, user_message=user_message, model_candidates=chat_candidates)
    if chat_result is None:
        print("All discovered free chat models are currently rate-limited or unavailable. Please retry shortly.")
        return 1

    chat_model, answer = chat_result
    print(f"\nUsed chat model: {chat_model}")
    print("\nModel response:")
    print(answer)

    embedding_candidates, has_free_embedding = ordered_embedding_models(embedding_catalog)
    if not embedding_candidates:
        print("\nNo embedding model was discovered from OpenRouter embeddings catalog.")
        return 1
    if not has_free_embedding:
        print("\nNo free embedding model is currently listed. Falling back to paid embedding candidates.")

    embedding_result = try_embedding_with_fallback(api_key=api_key, candidates=embedding_candidates)
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
