from app.utils import append_query_params


def test_append_to_bare_url() -> None:
    result = append_query_params("http://localhost/en/subscription/success", session_id="abc")
    assert result == "http://localhost/en/subscription/success?session_id=abc"


def test_append_to_url_with_existing_params() -> None:
    result = append_query_params("http://localhost/en/pricing?status=cancelled", extra="1")
    assert "status=cancelled" in result
    assert "extra=1" in result
    assert result.count("?") == 1


def test_append_multiple_params() -> None:
    result = append_query_params("http://localhost/page", a="1", b="2")
    assert "a=1" in result
    assert "b=2" in result


def test_stripe_placeholder_is_url_encoded_or_literal() -> None:
    result = append_query_params(
        "http://localhost/en/subscription/success",
        session_id="{CHECKOUT_SESSION_ID}",
    )
    assert "session_id=" in result
    assert "CHECKOUT_SESSION_ID" in result
