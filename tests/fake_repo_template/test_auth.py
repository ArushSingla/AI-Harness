from auth import login


def test_login_success():
    assert login("user@example.com", "secret") == 200


def test_login_wrong_password():
    assert login("user@example.com", "") == 401


def test_login_missing_email_returns_400():
    # Missing email should be handled gracefully, not raise/500.
    assert login(None, "secret") == 400
