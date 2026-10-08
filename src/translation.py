"""Whole-conversation code-mixed translation, preserving original turn identity."""

import re

import requests

from .bodhan import post_bodhan


LANGUAGES = {
    "en": "English", "as": "Assamese", "bn": "Bengali", "brx": "Bodo",
    "doi": "Dogri", "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada",
    "kok": "Konkani", "ks": "Kashmiri", "mai": "Maithili", "ml": "Malayalam",
    "mni": "Manipuri", "mr": "Marathi", "ne": "Nepali", "or": "Odia",
    "pa": "Punjabi", "sa": "Sanskrit", "sat": "Santali", "sd": "Sindhi",
    "ta": "Tamil", "te": "Telugu", "ur": "Urdu",
}


def validate_language_config(mode, config, default="en"):
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    language = config.get("podcast_language", default)
    if not isinstance(language, str) or language not in LANGUAGES:
        raise ValueError("Unsupported podcast_language; use a supported Bodhan language code")
    if mode != "bodhan":
        if "podcast_language" in config and language != "en":
            raise ValueError("Indic podcast_language is supported only with Bodhan")
        return "en"
    for host in ("host1", "host2"):
        if host in config and not isinstance(config[host], dict):
            raise ValueError(f"{host} must be a JSON object")
        if "lang" in config.get(host, {}) and config[host]["lang"] != language:
            raise ValueError(f"{host}.lang conflicts with podcast_language; both hosts must use {language}")
    return language


def _serialize(turns):
    return "\n\n".join(f"## `{t['turn_id']}` — {t['speaker']}\n\n{t['text']}" for t in turns)


def _parse(text, turns):
    if not isinstance(text, str):
        raise ValueError("translation is not text")
    headings = list(re.finditer(r"^##[ \t]+.*$", text, re.MULTILINE))
    if len(headings) != len(turns) or not headings or text[:headings[0].start()].strip():
        raise ValueError("translation turn markers are missing or extra")
    result = []
    for idx, (heading, turn) in enumerate(zip(headings, turns)):
        marker = re.fullmatch(r"##[ \t]+`([0-9]+)`(?:[ \t]+[^\n]*)?", heading.group().rstrip("\r"))
        if not marker or marker[1] != turn["turn_id"]:
            raise ValueError("translation turn markers are reordered or changed")
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        translated = text[heading.end():end].strip()
        if not translated:
            raise ValueError("translation contains an empty turn")
        result.append({**turn, "text": translated})
    return result


def translate_turns(turns, settings, check_cancel=None, on_progress=None):
    """Translate all turns first; split only when size or alignment prevents it."""
    language = validate_language_config(settings.tts.mode, {}, settings.tts.podcast_language)
    if settings.tts.mode != "bodhan" or language == "en":
        return [dict(t) for t in turns]
    if not settings.tts.bodhan_translation_api_key:
        raise RuntimeError("Bodhan translation credential is missing; configure BODHAN_TRANSLATION")
    if not turns:
        raise RuntimeError("Cannot translate an empty podcast")
    completed = 0

    def block(source):
        nonlocal completed
        if check_cancel:
            check_cancel()
        try:
            response = post_bodhan("/v1/chat/completions", settings.tts.bodhan_translation_api_key,
                                   {"model": "indic-translate",
                                    "messages": [{"role": "user", "content": _serialize(source)}],
                                    "target_language_code": language,
                                    "target_script": "codemix"}, check_cancel=check_cancel)
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 413:
                raise
            response = None
        if response is not None and response.status_code != 413:
            body = response.json()
            if not isinstance(body, dict) or "error" in body:
                raise RuntimeError("Bodhan translation returned an invalid/error response")
            try:
                choice = body["choices"][0]
                text = choice["message"]["content"]
                finish_reason = choice["finish_reason"]
                if not isinstance(text, str):
                    raise TypeError("translation is not text")
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("Bodhan translation returned an invalid chat response") from exc
            try:
                if finish_reason != "stop":
                    raise ValueError("translation did not finish completely")
                translated = _parse(text, source)
            except ValueError:
                translated = None
            if translated is not None:
                completed += len(source)
                if on_progress:
                    on_progress(completed, len(turns))
                return translated
        if len(source) == 1:
            raise RuntimeError(f"Bodhan could not translate turn {source[0]['turn_id']} completely with valid alignment")
        middle = len(source) // 2
        return block(source[:middle]) + block(source[middle:])

    return block(turns)
