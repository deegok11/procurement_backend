from tests.conftest import auth_header


def test_missing_token_is_rejected(client):
    resp = client.get("/prs")
    assert resp.status_code == 401


def test_invalid_token_is_rejected(client):
    resp = client.get("/prs", headers=auth_header("not-a-real-token"))
    assert resp.status_code == 401


def test_valid_token_is_accepted(client, tokens):
    resp = client.get("/prs", headers=auth_header(tokens["requester"]))
    assert resp.status_code == 200


def test_logout_revokes_the_token(client, tokens):
    token = client.post(
        "/auth/login", json={"username": "test_requester", "password": "pw"}
    ).json()["access_token"]
    assert client.get("/prs", headers=auth_header(token)).status_code == 200

    client.post("/auth/logout", headers=auth_header(token))

    assert client.get("/prs", headers=auth_header(token)).status_code == 401


def test_health_and_login_are_exempt_from_auth(client):
    assert client.get("/health").status_code == 200
    resp = client.post("/auth/login", json={"username": "nope", "password": "nope"})
    assert resp.status_code == 403  # NotAuthorizedError -> 403, not 401-from-missing-token
