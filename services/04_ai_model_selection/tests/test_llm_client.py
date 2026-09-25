from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai import APITimeoutError

from app.llm_client import LLMUnavailableError, call_general_ai


def _fake_response(text: str, prompt_tokens: int, completion_tokens: int):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def test_primary_groq_success_no_fallback_called():
    with patch("app.llm_client._client") as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_client.chat.completions.create.return_value = _fake_response("hi", 5, 5)

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            request_id="r1",
        )

    assert content == "hi"
    assert usage == {"input": 5, "output": 5}
    # เรียก client แค่ครั้งเดียว (groq เท่านั้น) เพราะสำเร็จตั้งแต่ตัวแรก
    assert mock_client_factory.call_count == 1


def test_groq_timeout_falls_back_to_gemini():
    with patch("app.llm_client._client") as mock_client_factory:
        groq_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: (_ for _ in ()).throw(
                        APITimeoutError(request=SimpleNamespace())
                    )
                )
            )
        )
        gemini_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: _fake_response("fallback answer", 8, 12)
                )
            )
        )
        mock_client_factory.side_effect = [groq_client, gemini_client]

        content, model, usage = call_general_ai(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            request_id="r2",
        )

    assert content == "fallback answer"
    assert usage == {"input": 8, "output": 12}
    assert mock_client_factory.call_count == 2


def test_both_providers_fail_raises_llm_unavailable():
    with patch("app.llm_client._client") as mock_client_factory:
        broken = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: (_ for _ in ()).throw(
                        APITimeoutError(request=SimpleNamespace())
                    )
                )
            )
        )
        mock_client_factory.side_effect = [broken, broken]

        with pytest.raises(LLMUnavailableError):
            call_general_ai(
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=100,
                request_id="r3",
            )
