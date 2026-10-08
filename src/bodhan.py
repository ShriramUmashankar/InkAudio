"""Bodhan HTTP calls with bounded retries and cooperative rate-limit waits."""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests


_limits = {}


def wait_with_cancel(seconds, check_cancel=None):
    while seconds > 0:
        if check_cancel:
            check_cancel()
        step = min(seconds, 0.25)
        time.sleep(step)
        seconds -= step
    if check_cancel:
        check_cancel()


def _retry_delay(value, default):
    try:
        return max(0.0, float(value))
    except (ValueError, TypeError):
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return default


def post_bodhan(path, key, payload, check_cancel=None, default_rpm=0):
    if not key:
        raise RuntimeError("Bodhan API credential is missing")
    # The application processes one podcast at a time; limits are per model/key.
    limit_key = (path, key)
    next_call, interval = _limits.get(limit_key, (0.0, 60.0 / default_rpm if default_rpm else 0.0))
    for attempt in range(3):
        wait_with_cancel(max(0.0, next_call - time.monotonic()), check_cancel)
        started = time.monotonic()
        next_call = started + interval
        _limits[limit_key] = (next_call, interval)
        try:
            response = requests.post(
                "https://api.bodhan.ai" + path,
                headers={"Authorization": f"Bearer {key}"},
                json=payload, timeout=120,
            )
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            wait_with_cancel(2 ** attempt, check_cancel)
            continue
        if check_cancel:
            check_cancel()
        try:
            rpm = float(response.headers.get("x-ratelimit-limit-requests", ""))
            if rpm > 0:
                interval = 60.0 / rpm
                next_call = started + interval
                _limits[limit_key] = (next_call, interval)
        except (ValueError, TypeError):
            pass
        if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
            wait_with_cancel(_retry_delay(response.headers.get("Retry-After"), 2 ** attempt), check_cancel)
            continue
        response.raise_for_status()
        return response

