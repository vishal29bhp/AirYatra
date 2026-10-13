"""Unit tests for tools/audit/route_map.py helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import route_map as rm  # noqa: E402


def test_norm_strips_query_and_templates():
    assert rm._norm("/api/bookings/${id}/cancel?x=1") == "/api/bookings/{param}/cancel"
    assert rm._norm("/api/a/pre-${x}/") == "/api/a/{param}"


def test_match_params_both_sides():
    assert rm._match("/api/bookings/{param}", "/api/bookings/{booking_id}")
    assert rm._match("/api/bookings/{param}", "/api/bookings/stats")
    assert not rm._match("/api/bookings", "/api/bookings/{booking_id}")


def test_frontend_regexes(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.js").write_text(
        "api.get('/sos/my-alerts');\n"
        "fetch(`${API_URL}/api/auth/login`, { method: 'POST' });\n"
        "const ws = `${process.env.REACT_APP_BACKEND_URL?.replace('https','wss')}/api/ws/chat/${id}`;\n"
        "axios.get(`${API}/payments/receipt/${sid}`);\n"
        "api.get(url);\n")
    res = rm.frontend_calls(str(src), str(tmp_path))
    paths = sorted(c["path"] for c in res["calls"])
    assert paths == ["/api/auth/login", "/api/payments/receipt/{param}", "/api/sos/my-alerts", "/api/ws/chat/{param}"]
    assert res["unresolved_dynamic_calls"] == 1
    login = next(c for c in res["calls"] if c["path"] == "/api/auth/login")
    assert login["method"] == "POST"
