"""Tiny fake login API used by the end-to-end agent test."""


def login(email, password):
    """Return an HTTP-style status code for a login attempt.

    BUG: this does not validate that `email` was provided, so a missing
    email causes an unhandled AttributeError downstream (simulated here
    as a 500), instead of a clean 400 Bad Request.
    """
    # BUG: no check for missing/empty email before using it.
    domain = email.split("@")[1]  # raises if email is None or empty
    if password:
        return 200
    return 401
