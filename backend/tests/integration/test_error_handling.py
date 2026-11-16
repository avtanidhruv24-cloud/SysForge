"""
Integration tests — Global error handling.

Verifies that the three exception handlers in ``main.py`` produce consistent
``ErrorResponse`` envelopes regardless of error type.
"""

from __future__ import annotations

import pytest


class TestValidationErrorEnvelope:
    """Pydantic validation failures are wrapped in ErrorResponse."""

    def test_missing_source_code_has_error_key(self, client):
        response = client.post("/api/v1/analyze", json={})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data

    def test_error_envelope_has_code(self, client):
        response = client.post("/api/v1/analyze", json={})
        data = response.json()
        assert "code" in data["error"]

    def test_error_envelope_has_message(self, client):
        response = client.post("/api/v1/analyze", json={})
        data = response.json()
        assert "message" in data["error"]
        assert len(data["error"]["message"]) > 0

    def test_error_code_is_invalid_request(self, client):
        response = client.post("/api/v1/analyze", json={})
        data = response.json()
        assert data["error"]["code"] == "INVALID_REQUEST"


class TestUnknownRouteReturns404:
    def test_unknown_route_404(self, client):
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
