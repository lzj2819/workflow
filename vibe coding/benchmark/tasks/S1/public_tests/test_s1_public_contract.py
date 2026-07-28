"""Public contract for the independently authored S1 calibration task.

Future executor runs copy this file into the isolated leaf workspace. It is public
model context and is deliberately not a hidden-acceptance oracle.
"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_s1_pub_001_health_is_json_and_healthy():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_s1_pub_002_normalizes_visible_example():
    response = client.post("/v1/labels/normalize", json={"label": "  Blue   SKY "})
    assert response.status_code == 200
    assert response.json() == {"normalized_label": "blue sky"}


def test_s1_pub_003_rejects_blank_label():
    response = client.post("/v1/labels/normalize", json={"label": "   "})
    assert 400 <= response.status_code < 500
    assert "detail" in response.json()

