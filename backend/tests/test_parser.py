from app.parser import parse_logs


def test_parse_logs_groups_stack_trace_and_extracts_fields():
    raw = """2026-09-18T14:21:01Z INFO service=api request started
2026-09-18T14:21:03Z ERROR [billing] PaymentException: card gateway timeout
    at BillingClient.charge(BillingClient.java:42)
    at Checkout.submit(Checkout.java:88)
2026-09-18T14:21:04Z WARN service=api retrying checkout"""

    lines, patterns = parse_logs(raw)

    assert len(lines) == 3
    assert lines[1].level == "ERROR"
    assert lines[1].service == "billing"
    assert "BillingClient.charge" in lines[1].message
    assert patterns[lines[1].fingerprint] == 1


def test_fingerprint_collapses_variable_numbers():
    raw = """ERROR service=worker job 123 failed for user 456
ERROR service=worker job 999 failed for user 888"""

    _, patterns = parse_logs(raw)

    assert len(patterns) == 1
    assert list(patterns.values()) == [2]
