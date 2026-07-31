from unittest.mock import MagicMock, patch

from app.ai import chat_agent
from app.ai.guardrail import (
    GUARDRAIL_GREETING_FALLBACK_MESSAGE,
    GUARDRAIL_HISTORY_TURNS,
    GUARDRAIL_NONSENSE_FALLBACK_MESSAGE,
    GUARDRAIL_REFUSAL_MESSAGE,
    GuardrailContext,
    run_guardrail,
)
from app.config import settings
from app.domain.roles import Domain, Role
from app.domain.schemas import CurrentUser


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="usr_req_test", username="test_requester", role=Role.REQUESTER, domain=Domain.INTERNAL,
    )


def _mock_response(parsed=None, text=None):
    response = MagicMock()
    response.parsed = parsed
    response.text = text
    return response


# --- run_guardrail ---


@patch("app.ai.guardrail.client.models.generate_content")
def test_run_guardrail_returns_parsed_context_when_in_scope(mock_generate):
    expected = GuardrailContext(category="in_scope", reason="about a PR")
    mock_generate.return_value = _mock_response(parsed=expected)

    result = run_guardrail("what's the status of my PR?", [])

    assert result == expected
    _, kwargs = mock_generate.call_args
    assert kwargs["model"] == settings.GUARDRAIL_MODEL
    assert kwargs["config"].response_schema is GuardrailContext


@patch("app.ai.guardrail.client.models.generate_content")
def test_run_guardrail_out_of_scope(mock_generate):
    mock_generate.return_value = _mock_response(
        parsed=GuardrailContext(category="out_of_scope", reason="unrelated chit-chat")
    )

    result = run_guardrail("tell me a joke", [])

    assert result.category == "out_of_scope"


@patch("app.ai.guardrail.client.models.generate_content")
def test_run_guardrail_falls_back_to_text_when_parsed_is_none(mock_generate):
    mock_generate.return_value = _mock_response(
        parsed=None, text='{"category": "in_scope", "reason": "about a PR"}'
    )

    result = run_guardrail("what's the status of my PR?", [])

    assert result == GuardrailContext(category="in_scope", reason="about a PR")


@patch("app.ai.guardrail.client.models.generate_content")
def test_run_guardrail_only_sends_recent_history(mock_generate):
    mock_generate.return_value = _mock_response(parsed=GuardrailContext(category="in_scope", reason="x"))
    long_history = [{"role": "user", "parts": [{"text": f"message {i}"}]} for i in range(20)]

    run_guardrail("latest message", long_history)

    _, kwargs = mock_generate.call_args
    assert kwargs["contents"] == long_history[-GUARDRAIL_HISTORY_TURNS:] + [
        {"role": "user", "parts": [{"text": "latest message"}]}
    ]


# --- run_chat_turn branching ---


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_out_of_scope_message_returns_refusal_without_calling_main_model(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(category="out_of_scope", reason="unrelated")
    session_id = "test-session-out-of-scope"

    result = chat_agent.run_chat_turn(session_id, _user(), "tell me a joke")

    assert result.reply == GUARDRAIL_REFUSAL_MESSAGE
    mock_generate.assert_not_called()
    assert chat_agent.CHAT_SESSIONS[session_id] == [
        {"role": "user", "parts": [{"text": "tell me a joke"}]},
        {"role": "model", "parts": [{"text": GUARDRAIL_REFUSAL_MESSAGE}]},
    ]


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_greeting_returns_guardrail_generated_reply_without_calling_main_model(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(
        category="greeting", reason="just a greeting", reply="Good morning! How can I help with procurement?"
    )
    session_id = "test-session-greeting"

    result = chat_agent.run_chat_turn(session_id, _user(), "good morning")

    assert result.reply == "Good morning! How can I help with procurement?"
    mock_generate.assert_not_called()
    assert chat_agent.CHAT_SESSIONS[session_id] == [
        {"role": "user", "parts": [{"text": "good morning"}]},
        {"role": "model", "parts": [{"text": "Good morning! How can I help with procurement?"}]},
    ]


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_greeting_falls_back_to_fixed_message_when_reply_missing(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(category="greeting", reason="just a greeting", reply=None)
    session_id = "test-session-greeting-fallback"

    result = chat_agent.run_chat_turn(session_id, _user(), "hi")

    assert result.reply == GUARDRAIL_GREETING_FALLBACK_MESSAGE
    mock_generate.assert_not_called()


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_nonsense_returns_guardrail_generated_reply_without_calling_main_model(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(
        category="nonsense", reason="gibberish", reply="Sorry, I didn't catch that — could you rephrase?"
    )
    session_id = "test-session-nonsense"

    result = chat_agent.run_chat_turn(session_id, _user(), "asdkjf qwoeiru")

    assert result.reply == "Sorry, I didn't catch that — could you rephrase?"
    mock_generate.assert_not_called()
    assert chat_agent.CHAT_SESSIONS[session_id] == [
        {"role": "user", "parts": [{"text": "asdkjf qwoeiru"}]},
        {"role": "model", "parts": [{"text": "Sorry, I didn't catch that — could you rephrase?"}]},
    ]


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_nonsense_falls_back_to_fixed_message_when_reply_missing(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(category="nonsense", reason="gibberish", reply=None)
    session_id = "test-session-nonsense-fallback"

    result = chat_agent.run_chat_turn(session_id, _user(), "asdkjf qwoeiru")

    assert result.reply == GUARDRAIL_NONSENSE_FALLBACK_MESSAGE
    mock_generate.assert_not_called()


@patch("app.ai.chat_agent.client.models.generate_content")
@patch("app.ai.chat_agent.run_guardrail")
def test_in_scope_message_calls_main_model(mock_guardrail, mock_generate):
    mock_guardrail.return_value = GuardrailContext(category="in_scope", reason="about a PR")
    main_response = MagicMock()
    main_response.text = "Here is your PR status."
    mock_generate.return_value = main_response
    session_id = "test-session-in-scope"

    result = chat_agent.run_chat_turn(session_id, _user(), "what's the status of my PR?")

    assert result.reply == "Here is your PR status."
    mock_generate.assert_called_once()
    assert chat_agent.CHAT_SESSIONS[session_id] == [
        {"role": "user", "parts": [{"text": "what's the status of my PR?"}]},
        {"role": "model", "parts": [{"text": "Here is your PR status."}]},
    ]
