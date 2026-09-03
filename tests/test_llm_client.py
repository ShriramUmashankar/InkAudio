from src.llm_client import extract_json, validate_turns


def test_extract_fenced_json():
    text = "```json\n[{\"speaker\":\"Host 1\",\"text\":\"hi\"}]\n```"
    out = extract_json(text)
    assert isinstance(out, list)
    assert out[0]["speaker"] == "Host 1"


def test_extract_prose_wrapped():
    text = "Sure! Here is the script:\n[{\"speaker\":\"Host 2\",\"text\":\"uhh, okay\"}]\nHope that helps."
    out = extract_json(text)
    assert out[0]["speaker"] == "Host 2"


def test_extract_object():
    text = '{"is_approved": true, "feedback": "good"}'
    out = extract_json(text)
    assert out["is_approved"] is True


def test_extract_none_on_garbage():
    assert extract_json("no json here at all") is None


def test_validate_drops_bad_turns():
    raw = [
        {"speaker": "Host 1", "text": "real"},
        {"speaker": "Host 3", "text": "bad speaker"},
        {"speaker": "Host 2", "text": "   "},
        "not a dict",
    ]
    out = validate_turns(raw)
    assert len(out) == 1
    assert out[0]["text"] == "real"


def test_validate_empty_on_scalar():
    assert validate_turns("nope") == []
