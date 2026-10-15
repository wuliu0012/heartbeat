"""Independent scheduler; never proxies ordinary chat. 原创：空气小狗老师."""
import argparse
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from app import Store, settings

SILENCE = "<SILENCE/>"


def policy():
    hour = datetime.now(ZoneInfo(os.getenv("HEARTBEAT_TZ", "Asia/Shanghai"))).hour
    start, end = int(os.getenv("DAY_START_HOUR", "10")), int(os.getenv("NIGHT_START_HOUR", "0"))
    day = start <= hour < end if start < end else hour >= start or hour < end
    prefix = "DAY" if day else "NIGHT"
    return (max(1, int(os.getenv(prefix + "_INTERVAL_MIN", "60" if day else "180"))),
            max(1, int(os.getenv("CHECK_INTERVAL_" + prefix + "_SEC", "600" if day else "7200"))))


def generate(state, extra):
    key, model = os.getenv("LLM_API_KEY", ""), os.getenv("LLM_MODEL", "")
    if not key or not model:
        return ""
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("Model endpoint must use HTTPS")
    instruction = ("This is a scheduled check, not a real user message. Based on the conversation, decide whether "
                   "to send a brief, non-demanding proactive message. If interruption is inappropriate, output only "
                   "<SILENCE/>. Do not invent events or claim to monitor the user. Respect rest and boundaries.")
    history = list(state["history"])
    seen = {(e["role"], e["content"]) for e in history}
    history += [e for e in extra if ("ai", e["content"]) not in seen]
    messages = [{"role": "system", "content": state["system_prompt"] + "\n\n" + instruction}]
    limit = max(1, min(2000, int(os.getenv("CONTEXT_MAX_MESSAGES", "40"))))
    messages += [{"role": "user" if h.get("role") == "user" else "assistant", "content": h["content"]}
                 for h in history[-limit:] if h.get("content")]
    messages.append({"role": "user", "content": "Scheduled heartbeat check: speak briefly or remain silent."})
    payload = {"model": model, "messages": messages, "max_completion_tokens": 1024}
    if model.startswith("openai/gpt-oss-"):
        payload.update(reasoning_effort="low", include_reasoning=False)
    response = requests.post(base + "/chat/completions", headers={"Authorization": "Bearer " + key},
                             json=payload, timeout=60)
    response.raise_for_status()
    return (response.json()["choices"][0]["message"].get("content") or "").strip()


def notify(entry):
    key = os.getenv("BARK_KEY", "")
    if not key:
        return False
    payload = {"device_key": key, "title": "Heartbeat", "body": entry["content"][:200], "group": "Heartbeat"}
    if os.getenv("FRONTEND_URL"):
        payload["url"] = os.environ["FRONTEND_URL"]
    response = requests.post("https://api.day.app/push", json=payload, timeout=10)
    response.raise_for_status()
    return response.json().get("code") == 200


def tick(store, generate_fn=generate, notify_fn=notify, now=None, threshold=None):
    state, extra = store.snapshot()
    if not state or not state["history"]:
        return "no_context"
    now = int(time.time()*1000) if now is None else now
    threshold = policy()[0] if threshold is None else threshold
    if now - max(state["last_user_ts"], state["last_heartbeat_ts"]) < threshold * 60000:
        return "not_due"
    text = generate_fn(state, extra)
    if not text or SILENCE in text:
        return "silent"
    entry = store.enqueue(state, text[:4000], now)
    if entry is None:
        return "obsolete_generation"
    # Check again before notification; transport still cannot be atomic with a context switch.
    current, _ = store.snapshot()
    if current["generation"] != entry["generation"]:
        return "obsolete_generation"
    try:
        pushed = notify_fn(entry)
    except Exception:
        pushed = False
    return "queued_notified" if pushed else "queued_only"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    cfg = settings()
    store = Store(cfg["DATA_DIR"])
    while True:
        try:
            print("heartbeat:", tick(store), flush=True)
        except Exception:
            print("heartbeat: check_failed", flush=True)
        if args.once:
            break
        time.sleep(policy()[1])


if __name__ == "__main__":
    main()
