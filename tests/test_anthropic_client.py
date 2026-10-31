"""anthropic_chat_client + chon client trong run_news_service — khong goi mang.

Client Anthropic duoc thay bang MagicMock qua `anthropic.Anthropic`; kiem request
gui di (system tach rieng, khong temperature, effort tuong minh) va cach doc
response (bo block thinking, boc rao ```json, raise khi refusal/max_tokens).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gpr_engine.scoring.statement_scorer import (
    LLMRefusalError,
    anthropic_chat_client,
    parse_score,
)

_VALID = ('{"v": 0.4, "specificity": 0.6, "channel": null, "commitment": "rhetoric",'
          ' "actor_country": "USA", "target_country": "IRN", "rationale": "x"}')


def _resp(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason,
                           _request_id="req_test")


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _thinking():
    return SimpleNamespace(type="thinking", thinking="")


def _client_returning(resp):
    fake = MagicMock()
    fake.messages.create.return_value = resp
    return fake


def _call(resp, messages=None, **kw):
    fake = _client_returning(resp)
    with patch("anthropic.Anthropic", return_value=fake):
        llm = anthropic_chat_client(api_key="k", **kw)
        out = llm(messages or [{"role": "system", "content": "SYS"},
                               {"role": "user", "content": "U"}], 0.0)
    return out, fake.messages.create.call_args.kwargs


def test_request_splits_system_and_sends_no_temperature():
    out, kwargs = _call(_resp(_thinking(), _text(_VALID)))
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["system"] == "SYS"
    assert kwargs["messages"] == [{"role": "user", "content": "U"}]
    assert kwargs["output_config"] == {"effort": "medium"}
    assert "temperature" not in kwargs
    assert out == _VALID
    parse_score(out)  # contract strict van giu nguyen


def test_retry_history_keeps_assistant_and_user_turns():
    msgs = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "U"},
            {"role": "assistant", "content": "bad"},
            {"role": "user", "content": "Invalid output"}]
    _, kwargs = _call(_resp(_text(_VALID)), messages=msgs)
    assert [m["role"] for m in kwargs["messages"]] == ["user", "assistant", "user"]


def test_json_fence_is_unwrapped_but_content_untouched():
    out, _ = _call(_resp(_text(f"```json\n{_VALID}\n```")))
    assert out == _VALID


def test_non_json_text_passes_through_for_parse_score_to_reject():
    out, _ = _call(_resp(_text("Score: 0.4")))
    assert out == "Score: 0.4"


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_refusal_or_truncation_raises(stop):
    with pytest.raises(LLMRefusalError):
        _call(_resp(_text(""), stop_reason=stop))


def test_effort_is_configurable():
    _, kwargs = _call(_resp(_text(_VALID)), effort="low")
    assert kwargs["output_config"] == {"effort": "low"}


def _load_run_news_service():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_news_service.py"
    spec = importlib.util.spec_from_file_location("run_news_service_t", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_llm_client_routes_claude_models_to_anthropic(monkeypatch):
    rns = _load_run_news_service()
    assert rns.DEFAULT_LLM_MODEL == "claude-haiku-5-5"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with patch.object(rns, "anthropic_chat_client") as a, \
            patch.object(rns, "openai_chat_client") as o:
        rns.build_llm_client("claude-haiku-5-5")
    a.assert_called_once_with(model="claude-haiku-5-5", api_key="k", effort="medium")
    o.assert_not_called()


def test_build_llm_client_claude_requires_anthropic_key(monkeypatch):
    rns = _load_run_news_service()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        rns.build_llm_client("claude-haiku-5-5")


def test_build_llm_client_other_models_still_use_openai(monkeypatch):
    rns = _load_run_news_service()
    monkeypatch.setenv("OPENAI_BASE_URL", "http://vllm:8003/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.object(rns, "openai_chat_client") as o:
        rns.build_llm_client("Qwen3-14B-AWQ")
    o.assert_called_once_with(model="Qwen3-14B-AWQ", base_url="http://vllm:8003/v1",
                              api_key="EMPTY")
