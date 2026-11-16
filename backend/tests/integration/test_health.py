"""
Integration tests — Health endpoint.

Verifies the ``GET /api/v1/health`` and bare ``GET /health`` endpoints
using the full FastAPI test client (all middleware, exception handlers,
and routing active).
"""

from __future__ import annotations

import pytest


class TestVersionedHealth:
    def test_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_response_body_status_ok(self, client):
        data = client.get("/api/v1/health").json()
        assert data["status"] == "ok"

    def test_response_body_service_name(self, client):
        data = client.get("/api/v1/health").json()
        assert data["service"] == "sysforge-backend"

    def test_response_body_version(self, client):
        data = client.get("/api/v1/health").json()
        assert data["version"] == "1.0.0"

    def test_content_type_is_json(self, client):
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]


class TestBareHealth:
    def test_bare_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_bare_health_body_matches_versioned(self, client):
        versioned = client.get("/api/v1/health").json()
        bare = client.get("/health").json()
        assert bare["status"] == versioned["status"]
        assert bare["service"] == versioned["service"]
