"""
Integration tests — Analysis pipeline endpoint.

Verifies ``POST /api/v1/analyze`` with the full FastAPI test client.

Phase 4 update: LEXICAL and SYNTAX stages are now fully implemented.
Tests updated to reflect Phase 4 reality.
"""

from __future__ import annotations

import pytest


class TestAnalyzeEndpoint:
    URL = "/api/v1/analyze"

    def test_returns_200_for_canonical_source(self, client, canonical_source):
        response = client.post(self.URL, json={"source_code": canonical_source})
        assert response.status_code == 200

    def test_response_has_session_id(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_response_echoes_source_code(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert data["source_code"] == canonical_source.strip()

    def test_lexical_stage_is_completed(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "lexical" in data["completed_stages"]

    def test_syntax_stage_is_completed(self, client, canonical_source):
        # Phase 4: syntax is now COMPLETED
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "syntax" in data["completed_stages"]

    def test_stage_statuses_present(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "stage_statuses" in data
        assert isinstance(data["stage_statuses"], list)
        assert len(data["stage_statuses"]) > 0

    def test_lexical_status_is_completed(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        lexical = next(
            (s for s in data["stage_statuses"] if s["stage"] == "lexical"), None
        )
        assert lexical is not None
        assert lexical["status"] == "COMPLETED"

    def test_syntax_status_is_completed(self, client, canonical_source):
        # Phase 4: syntax is COMPLETED
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        syntax = next(
            (s for s in data["stage_statuses"] if s["stage"] == "syntax"), None
        )
        assert syntax is not None
        assert syntax["status"] == "COMPLETED"

    def test_unimplemented_stages_are_not_implemented(self, client, canonical_source):
        # All stages except lexical, syntax, pass-one are NOT_IMPLEMENTED in Phase 5
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        for entry in data["stage_statuses"]:
            if entry["stage"] in (
                "macro", "pass-two",
                "linker", "loader", "execution", "ai",
            ):
                assert entry["status"] == "NOT_IMPLEMENTED", (
                    f"Stage {entry['stage']} should be NOT_IMPLEMENTED in Phase 5"
                )


    def test_lexical_result_present_in_results(self, client, canonical_source):
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "lexical" in data["results"]
        assert data["results"]["lexical"] is not None

    def test_syntax_result_present_in_results(self, client, canonical_source):
        # Phase 4: syntax result is in the results dict
        data = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert "syntax" in data["results"]
        assert data["results"]["syntax"] is not None

    def test_rejects_empty_source(self, client):
        response = client.post(self.URL, json={"source_code": ""})
        assert response.status_code == 422

    def test_rejects_whitespace_only_source(self, client):
        response = client.post(self.URL, json={"source_code": "   "})
        assert response.status_code == 422

    def test_rejects_missing_source_code_field(self, client):
        response = client.post(self.URL, json={})
        assert response.status_code == 422

    def test_error_response_has_error_envelope(self, client):
        response = client.post(self.URL, json={"source_code": ""})
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_two_requests_produce_different_session_ids(self, client, canonical_source):
        r1 = client.post(self.URL, json={"source_code": canonical_source}).json()
        r2 = client.post(self.URL, json={"source_code": canonical_source}).json()
        assert r1["session_id"] != r2["session_id"]

    def test_minimal_source_accepted(self, client, minimal_source):
        response = client.post(self.URL, json={"source_code": minimal_source})
        assert response.status_code == 200

    def test_explicit_stages_accepted(self, client, canonical_source):
        response = client.post(
            self.URL,
            json={
                "source_code": canonical_source,
                "stages": ["lexical", "syntax"],
            },
        )
        assert response.status_code == 200

    def test_content_type_is_json(self, client, canonical_source):
        response = client.post(self.URL, json={"source_code": canonical_source})
        assert "application/json" in response.headers["content-type"]


class TestStageEndpointsNotImplemented:
    """
    Per-stage endpoints:
      /lex   is live (Phase 3)
      /parse is live (Phase 4)
    All others remain NOT_IMPLEMENTED stubs.
    """

    # Endpoints still NOT_IMPLEMENTED in Phase 5
    UNIMPLEMENTED_ENDPOINTS = [
        "/api/v1/macro/process",
        "/api/v1/assemble/pass2",
        "/api/v1/link",
        "/api/v1/load",
        "/api/v1/execute",
    ]


    def _payload(self, canonical_source: str) -> dict:
        return {"source_code": canonical_source}

    @pytest.mark.parametrize("url", UNIMPLEMENTED_ENDPOINTS)
    def test_returns_200(self, client, canonical_source, url):
        response = client.post(url, json=self._payload(canonical_source))
        assert response.status_code == 200

    @pytest.mark.parametrize("url", UNIMPLEMENTED_ENDPOINTS)
    def test_status_is_not_implemented(self, client, canonical_source, url):
        data = client.post(url, json=self._payload(canonical_source)).json()
        assert data["status"] == "NOT_IMPLEMENTED"

    @pytest.mark.parametrize("url", UNIMPLEMENTED_ENDPOINTS)
    def test_result_is_null(self, client, canonical_source, url):
        data = client.post(url, json=self._payload(canonical_source)).json()
        assert data["result"] is None

    def test_lex_endpoint_returns_completed(self, client, canonical_source):
        data = client.post(
            "/api/v1/lex", json=self._payload(canonical_source)
        ).json()
        assert data["status"] == "COMPLETED"

    def test_lex_endpoint_result_not_null(self, client, canonical_source):
        data = client.post(
            "/api/v1/lex", json=self._payload(canonical_source)
        ).json()
        assert data["result"] is not None

    def test_parse_endpoint_returns_completed(self, client, canonical_source):
        # Phase 4: /parse is live
        data = client.post(
            "/api/v1/parse", json=self._payload(canonical_source)
        ).json()
        assert data["status"] == "COMPLETED"

    def test_parse_endpoint_result_not_null(self, client, canonical_source):
        data = client.post(
            "/api/v1/parse", json=self._payload(canonical_source)
        ).json()
        assert data["result"] is not None


class TestSessionRetrieval:
    """GET /api/v1/session/{session_id}/{stage} endpoint."""

    def test_nonexistent_session_returns_404(self, client):
        response = client.get("/api/v1/session/nonexistent/lexical")
        assert response.status_code == 404

    def test_404_has_error_envelope(self, client):
        response = client.get("/api/v1/session/nonexistent/lexical")
        data = response.json()
        assert "detail" in data

    def test_lexical_result_retrievable_after_analyze(
        self, client, canonical_source
    ):
        analyze_data = client.post(
            "/api/v1/analyze",
            json={"source_code": canonical_source},
        ).json()
        response = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/lexical"
        )
        assert response.status_code == 200

    def test_lexical_session_result_has_tokens(self, client, canonical_source):
        analyze_data = client.post(
            "/api/v1/analyze",
            json={"source_code": canonical_source},
        ).json()
        result = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/lexical"
        ).json()
        assert "tokens" in result
        assert len(result["tokens"]) == 19

    def test_syntax_result_retrievable_after_analyze(
        self, client, canonical_source
    ):
        # Phase 4: syntax runs during /analyze → result cached → 200
        analyze_data = client.post(
            "/api/v1/analyze",
            json={"source_code": canonical_source},
        ).json()
        response = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/syntax"
        )
        assert response.status_code == 200

    def test_syntax_session_result_has_statements(self, client, canonical_source):
        analyze_data = client.post(
            "/api/v1/analyze",
            json={"source_code": canonical_source},
        ).json()
        result = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/syntax"
        ).json()
        assert "statements" in result
        assert len(result["statements"]) == 7

    def test_macro_stage_not_yet_available_returns_404(
        self, client, canonical_source
    ):
        # macro is NOT_IMPLEMENTED → no result → 404
        analyze_data = client.post(
            "/api/v1/analyze",
            json={"source_code": canonical_source},
        ).json()
        response = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/macro"
        )
        assert response.status_code == 404
