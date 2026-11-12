import re

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_realtime_mode_uses_the_current_clock():
    assert client.post("/api/live/start").json()["mode"] == "realtime"
    point = client.get("/api/live/next").json()
    assert point["mode"] == "realtime"
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", point["time"])
    decision = point["decision"]
    assert 0.0 <= decision["rafc_v_promise_mw"] <= decision["requested_mw"]
    assert decision["baseline_promise_mw"] >= decision["rafc_v_promise_mw"]


def test_demo_mode_fast_forwards_and_is_reproducible():
    client.post("/api/live/start", params={"mode": "demo", "seed": 7})
    a = client.get("/api/live/next").json()
    b = client.get("/api/live/next").json()
    assert (a["time"], b["time"]) == ("09:00", "09:15")
    client.post("/api/live/start", params={"mode": "demo", "seed": 7})
    assert client.get("/api/live/next").json() == a


def test_unknown_mode_is_rejected():
    assert client.post("/api/live/start", params={"mode": "fast"}).status_code == 422