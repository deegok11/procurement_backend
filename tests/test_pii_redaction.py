from app.ai.extraction.pii_redaction import redact_pii


def test_gstin_is_redacted():
    text, counts = redact_pii("GSTIN: 27ABCDE1234F1Z5")
    assert "27ABCDE1234F1Z5" not in text
    assert "[REDACTED:GSTIN]" in text
    assert counts == {"GSTIN": 1}


def test_pan_is_redacted_but_not_double_counted_inside_a_gstin():
    # A GSTIN embeds a PAN-shaped substring — once GSTIN is redacted, the PAN
    # pattern must not also match what's left of it.
    text, counts = redact_pii("GSTIN: 27ABCDE1234F1Z5\nPAN: ABCDE1234F")
    assert counts == {"GSTIN": 1, "PAN": 1}
    assert "ABCDE1234F" not in text


def test_ifsc_is_redacted():
    text, counts = redact_pii("IFSC: HDFC0001234")
    assert "HDFC0001234" not in text
    assert counts == {"IFSC": 1}


def test_bank_account_requires_a_label():
    labeled, counts = redact_pii("Bank A/C No: 123456789012")
    assert "123456789012" not in labeled
    assert counts == {"BANK_ACCOUNT": 1}

    # A bare digit run with no account/A-C label is left alone — could be
    # anything (invoice number, PO number, amount).
    unlabeled, counts2 = redact_pii("Reference 123456789012")
    assert "123456789012" in unlabeled
    assert counts2 == {}


def test_mobile_label_anchored_and_bare_indian_shape():
    text, counts = redact_pii("Mobile: +91 9876543210\nContact: 9123456780")
    assert "9876543210" not in text
    assert "9123456780" not in text
    assert counts == {"MOBILE": 2}


def test_mobile_pattern_does_not_match_non_mobile_shaped_numbers():
    # 10 digits but doesn't start 6-9, and no label nearby — a PO number, not a phone.
    text, counts = redact_pii("PO Number: 4500001234")
    assert "4500001234" in text
    assert counts == {}


def test_email_is_redacted():
    text, counts = redact_pii("Email: sales@acme.example")
    assert "sales@acme.example" not in text
    assert counts == {"EMAIL": 1}


def test_non_pii_business_fields_are_left_untouched():
    sample = (
        "Invoice No: INV-2026-001\n"
        "PO Number: 4500001234\n"
        "Item: Widget A  Qty: 10  Rate: 500.00\n"
        "HSN: 8471  Amount: 5000.00"
    )
    text, counts = redact_pii(sample)
    assert text == sample
    assert counts == {}


def test_redaction_never_returns_the_matched_values_in_counts():
    text, counts = redact_pii("GSTIN: 27ABCDE1234F1Z5, Mobile: 9876543210")
    for label, count in counts.items():
        assert isinstance(count, int)
        assert "27ABCDE1234F1Z5" not in str(count)


def test_full_document_redaction_matches_expected_summary():
    sample = (
        "ACME SUPPLIES PVT LTD\n"
        "GSTIN: 27ABCDE1234F1Z5\n"
        "PAN: ABCDE1234F\n"
        "Mobile: +91 9876543210\n"
        "Contact: 9123456780\n"
        "Email: sales@acme.example\n"
        "Bank A/C No: 123456789012\n"
        "IFSC: HDFC0001234\n"
        "Invoice No: INV-2026-001\n"
        "PO Number: 4500001234\n\n"
        "Item: Widget A  Qty: 10  Rate: 500.00\n"
        "HSN: 8471  Amount: 5000.00"
    )
    text, counts = redact_pii(sample)
    assert counts == {"GSTIN": 1, "PAN": 1, "IFSC": 1, "BANK_ACCOUNT": 1, "MOBILE": 2, "EMAIL": 1}
    assert "INV-2026-001" in text
    assert "4500001234" in text
    assert "8471" in text
    assert "5000.00" in text
