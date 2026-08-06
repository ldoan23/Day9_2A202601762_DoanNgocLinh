import json
import os
import time
import urllib.error
import urllib.request

MODEL_NAME = "meta/llama-3.1-8b-instruct"
MODEL_PARAM_SIZE = "8B"
PROVIDER = "NVIDIA NIM"
BASE_URL = "https://integrate.api.nvidia.com/v1"
CHAT_URL = BASE_URL.rstrip("/") + "/chat/completions"
MAX_TOKENS = 300
RETRY_DELAYS = [1, 2, 4]

_call_count = 0
_total_duration_ms = 0.0
_stats_lock = None


def _lock():
    global _stats_lock
    if _stats_lock is None:
        import threading

        _stats_lock = threading.Lock()
    return _stats_lock


def load_api_key(env_path=".env"):
    if not os.path.exists(env_path):
        return None
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "NVIDIA_API_KEY":
                return value.strip()
    return None


def _record_call(duration_seconds):
    global _call_count, _total_duration_ms
    with _lock():
        _call_count += 1
        _total_duration_ms += duration_seconds * 1000.0


def stats():
    with _lock():
        return {
            "llm_calls": _call_count,
            "total_llm_duration_ms": round(_total_duration_ms, 1),
        }


def _extract_json(text):
    if not isinstance(text, str):
        raise ValueError("response is not a string")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return json.loads(text[start : end + 1])


def _post(system, user, api_key, timeout):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }
    request = urllib.request.Request(
        CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    content = data["choices"][0]["message"]["content"]
    return _extract_json(content)


def chat_json(system, user, timeout=30):
    api_key = load_api_key()
    if not api_key:
        _record_call(0.0)
        return None
    attempt = 0
    while True:
        attempt += 1
        start = time.time()
        try:
            result = _post(system, user, api_key, timeout)
            _record_call(time.time() - start)
            return result
        except urllib.error.HTTPError as exc:
            _record_call(time.time() - start)
            if exc.code == 429 and attempt <= len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt - 1])
                continue
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            _record_call(time.time() - start)
            if attempt <= len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt - 1])
                continue
            return None
        except Exception:
            _record_call(time.time() - start)
            return None
