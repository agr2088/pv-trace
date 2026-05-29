from utils.validators import InputValidator


def test_valid_drug_name_accepted():
    v = InputValidator()
    ok, msg = v.validate_drug_name("ibuprofen")
    assert ok is True
    assert msg == ""


def test_drug_name_with_number_suffix_accepted():
    """Drug names like Interferon-2a or 5-fluorouracil must be valid."""
    v = InputValidator()
    ok, _ = v.validate_drug_name("5-fluorouracil")
    assert ok is True


def test_empty_drug_name_rejected():
    v = InputValidator()
    ok, msg = v.validate_drug_name("")
    assert ok is False
    assert "required" in msg.lower()


def test_sql_injection_rejected():
    v = InputValidator()
    ok, _ = v.validate_drug_name("drug'; DROP TABLE--")
    assert ok is False


def test_angle_bracket_rejected():
    v = InputValidator()
    ok, _ = v.validate_drug_name("<script>alert(1)</script>")
    assert ok is False


def test_sanitize_strips_special_characters():
    v = InputValidator()
    result = v.sanitize_drug_name("  ibuprofen!!! ")
    assert result == "Ibuprofen"
