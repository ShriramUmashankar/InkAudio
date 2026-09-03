import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

RPM_LIMIT = 10  
_MIN_INTERVAL = 60.0 / RPM_LIMIT
_rate_lock = threading.Lock()
_last_call = 0.0


def _pace():
    global _last_call
    with _rate_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        retries: int = 3,
        log_path: str | None = None,
    ):
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._retries = retries
        self._log_path = log_path
        self._call_count = 0
        if log_path:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    def _log(self, node_label: str, user_prompt: str, response: str) -> None:
        if not self._log_path:
            return
        self._call_count += 1
        p = Path(self._log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            if self._call_count == 1:
                f.write("# LLM Log\n")
            f.write(f"\n---\n\n## Round {self._call_count} — {node_label}\n\n")
            f.write(f"### Prompt\n\n{user_prompt}\n\n")
            f.write(f"### Response\n\n{response}\n")

    def chat(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        node_label = kwargs.pop("node_label", "")
        last_err: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                _pace()
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    **kwargs,
                )
                result = resp.choices[0].message.content or ""
                self._log(node_label, user_prompt, result)
                return result
            except Exception as e:  # noqa: BLE001 - retry on any SDK/network error
                last_err = e
                print(f"  [llm] call failed (attempt {attempt}/{self._retries}): {e}")
        raise RuntimeError(f"LLM call failed after {self._retries} attempts: {last_err}")


def extract_json(text: str) -> Any | None:
    """Recover a JSON object or array from loose LLM output.

    Handles ```json fences, prose wrapping, and trailing commentary by
    finding the first balanced {...} or [...] block.
    """
    if text is None:
        return None
    cleaned = text.strip()
    # strip code fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(cleaned)):
            c = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    return None


def validate_turns(parsed: Any) -> List[Dict[str, str]]:
    """Return a cleaned list of {'speaker','text'} dicts, or [] if invalid."""
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        speaker = item.get("speaker")
        text = item.get("text")
        if speaker not in ("Host 1", "Host 2") or not isinstance(text, str) or not text.strip():
            continue
        out.append({"speaker": speaker, "text": text.strip()})
    return out
