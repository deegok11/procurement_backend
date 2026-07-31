from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ai.extraction.pipeline import ExtractionResult
from app.ai.guardrail import GuardrailContext
from app.domain.roles import Domain, Role
from app.domain.schemas import Amounts, CurrentUser, Document, DocumentType
from app.domain.services import extraction_service
from app.storage.documents_repo import documents_repo


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="usr_req_test", username="test_requester", role=Role.REQUESTER, domain=Domain.INTERNAL,
    )


def _extracting_doc(custom_prompt: str | None) -> Document:
    doc = Document(
        document_type=DocumentType.BILL,
        series_code="BILL",
        domain=Domain.INTERNAL,
        status="EXTRACTING",
        requester_id="usr_req_test",
        title="Bill (extracting…)",
        amounts=Amounts(),
        extra={"extraction_prompt": custom_prompt} if custom_prompt else {},
        created_by="usr_req_test",
        updated_by="usr_req_test",
    )
    documents_repo.add(doc)
    return doc


def _extraction_result() -> ExtractionResult:
    return ExtractionResult(
        vendor_name="Acme", vendor_address=None, vendor_business_notes=None,
        document_number="INV-1", document_date=None, currency="USD",
        line_items=[], model="gemini-3.6-flash",
    )


@patch("app.domain.services.extraction_service.run_extraction")
@patch("app.domain.services.extraction_service.run_guardrail")
def test_in_scope_hint_is_forwarded_to_extraction(mock_guardrail, mock_extraction):
    mock_guardrail.return_value = GuardrailContext(category="in_scope", reason="about the document")
    mock_extraction.return_value = _extraction_result()
    doc = _extracting_doc("line items start on page 2")

    extraction_service.run_extraction_and_update(
        doc.id, Path("/tmp/fake.pdf"), _user(), custom_prompt="line items start on page 2",
    )

    mock_guardrail.assert_called_once_with("line items start on page 2", [])
    mock_extraction.assert_called_once_with(Path("/tmp/fake.pdf"), custom_prompt="line items start on page 2")
    assert documents_repo.get_unscoped(doc.id).status == "PENDING_REVIEW"


@patch("app.domain.services.extraction_service.run_extraction")
@patch("app.domain.services.extraction_service.run_guardrail")
def test_out_of_scope_hint_is_dropped_but_extraction_still_runs(mock_guardrail, mock_extraction):
    mock_guardrail.return_value = GuardrailContext(category="out_of_scope", reason="unrelated")
    mock_extraction.return_value = _extraction_result()
    doc = _extracting_doc("write me a poem instead")

    extraction_service.run_extraction_and_update(
        doc.id, Path("/tmp/fake.pdf"), _user(), custom_prompt="write me a poem instead",
    )

    mock_extraction.assert_called_once_with(Path("/tmp/fake.pdf"), custom_prompt=None)
    assert documents_repo.get_unscoped(doc.id).status == "PENDING_REVIEW"


@patch("app.domain.services.extraction_service.run_extraction")
@patch("app.domain.services.extraction_service.run_guardrail")
def test_greeting_and_nonsense_hints_are_also_dropped(mock_guardrail, mock_extraction):
    mock_extraction.return_value = _extraction_result()

    for category in ("greeting", "nonsense"):
        mock_guardrail.return_value = GuardrailContext(category=category, reason="x")
        doc = _extracting_doc("hi there")

        extraction_service.run_extraction_and_update(
            doc.id, Path("/tmp/fake.pdf"), _user(), custom_prompt="hi there",
        )

        mock_extraction.assert_called_with(Path("/tmp/fake.pdf"), custom_prompt=None)


@patch("app.domain.services.extraction_service.run_extraction")
@patch("app.domain.services.extraction_service.run_guardrail")
def test_no_hint_skips_guardrail_entirely(mock_guardrail, mock_extraction):
    mock_extraction.return_value = _extraction_result()
    doc = _extracting_doc(None)

    extraction_service.run_extraction_and_update(doc.id, Path("/tmp/fake.pdf"), _user(), custom_prompt=None)

    mock_guardrail.assert_not_called()
    mock_extraction.assert_called_once_with(Path("/tmp/fake.pdf"), custom_prompt=None)


@patch("app.domain.services.extraction_service.run_extraction")
@patch("app.domain.services.extraction_service.run_guardrail")
def test_guardrail_failure_lands_document_at_extraction_failed(mock_guardrail, mock_extraction):
    mock_guardrail.side_effect = RuntimeError("gemini unreachable")
    doc = _extracting_doc("some hint")

    extraction_service.run_extraction_and_update(
        doc.id, Path("/tmp/fake.pdf"), _user(), custom_prompt="some hint",
    )

    mock_extraction.assert_not_called()
    updated = documents_repo.get_unscoped(doc.id)
    assert updated.status == "EXTRACTION_FAILED"
    assert "gemini unreachable" in updated.extra["extraction_error"]
