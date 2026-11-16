"""
Integration tests — Lexer API endpoints (Phase 3).

Tests the full HTTP stack:  TestClient → FastAPI → AnalysisService → Lexer

Covers:
  - POST /api/v1/lex  with valid source → real tokens in response
  - POST /api/v1/lex  with invalid source → HTTP 422 (Pydantic validation)
  - POST /api/v1/lex  with lexical errors → UNKNOWN tokens + diagnostics
  - POST /api/v1/analyze  with stages=["lexical"] → real token results
  - POST /api/v1/analyze  (full pipeline) → lexical stage COMPLETED
  - GET  /api/v1/session/{id}/lexical  → cached result retrieval
"""

from __future__ import annotations

import pytest

CANONICAL = (
    "START 100\n"
    "MOVER AREG ='5'\n"
    "ADD BREG ='1'\n"
    "LOOP SUB AREG ='2'\n"
    "MOVEM AREG RESULT\n"
    "RESULT DS 1\n"
    "END"
)

LEX_URL = "/api/v1/lex"
ANALYZE_URL = "/api/v1/analyze"


# ===========================================================================
# POST /api/v1/lex — canonical source
# ===========================================================================


class TestLexEndpointCanonical:
    def test_returns_200(self, client):
        resp = client.post(LEX_URL, json={"source_code": CANONICAL})
        assert resp.status_code == 200

    def test_response_has_session_id(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_status_is_completed(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["status"] == "COMPLETED"

    def test_result_is_not_null(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"] is not None

    def test_result_has_tokens(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert "tokens" in data["result"]
        assert isinstance(data["result"]["tokens"], list)

    def test_correct_token_count(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        # 19 tokens in canonical program
        assert len(data["result"]["tokens"]) == 19

    def test_token_count_field(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["token_count"] == 19

    def test_success_flag_true(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["success"] is True

    def test_no_diagnostics(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["diagnostics"] == []

    def test_first_token_is_directive(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        first = data["result"]["tokens"][0]
        assert first["type"] == "DIRECTIVE"
        assert first["value"] == "START"

    def test_first_token_line_1(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["tokens"][0]["line"] == 1

    def test_first_token_column_1(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["tokens"][0]["column"] == 1

    def test_last_token_is_end_directive(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        tokens = data["result"]["tokens"]
        last = tokens[-1]
        assert last["type"] == "DIRECTIVE"
        assert last["value"] == "END"

    def test_last_token_is_on_line_7(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        last = data["result"]["tokens"][-1]
        assert last["line"] == 7

    def test_token_categories_present(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        token_types = {t["type"] for t in data["result"]["tokens"]}
        assert "DIRECTIVE" in token_types
        assert "IMPERATIVE" in token_types
        assert "REGISTER" in token_types
        assert "LITERAL" in token_types
        assert "SYMBOL" in token_types
        assert "NUMBER" in token_types
        assert "DECLARATIVE" in token_types

    def test_loop_symbol_present(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        symbols = [t for t in data["result"]["tokens"] if t["value"] == "LOOP"]
        assert len(symbols) >= 1
        assert symbols[0]["type"] == "SYMBOL"

    def test_literals_present(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        literals = [t for t in data["result"]["tokens"] if t["type"] == "LITERAL"]
        literal_values = {t["value"] for t in literals}
        assert "='5'" in literal_values
        assert "='1'" in literal_values
        assert "='2'" in literal_values

    def test_each_token_has_required_fields(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        for token in data["result"]["tokens"]:
            assert "type" in token
            assert "value" in token
            assert "line" in token
            assert "column" in token

    def test_each_token_has_span(self, client):
        data = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        for token in data["result"]["tokens"]:
            assert token["span"] is not None
            assert "line" in token["span"]
            assert "column" in token["span"]
            assert "length" in token["span"]

    def test_content_type_is_json(self, client):
        resp = client.post(LEX_URL, json={"source_code": CANONICAL})
        assert "application/json" in resp.headers["content-type"]

    def test_two_requests_produce_different_session_ids(self, client):
        r1 = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        r2 = client.post(LEX_URL, json={"source_code": CANONICAL}).json()
        assert r1["session_id"] != r2["session_id"]


# ===========================================================================
# POST /api/v1/lex — validation errors (Pydantic-level)
# ===========================================================================


class TestLexEndpointValidation:
    def test_rejects_empty_source(self, client):
        resp = client.post(LEX_URL, json={"source_code": ""})
        assert resp.status_code == 422

    def test_rejects_whitespace_only(self, client):
        resp = client.post(LEX_URL, json={"source_code": "   "})
        assert resp.status_code == 422

    def test_rejects_missing_field(self, client):
        resp = client.post(LEX_URL, json={})
        assert resp.status_code == 422

    def test_error_envelope_shape(self, client):
        resp = client.post(LEX_URL, json={"source_code": ""})
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


# ===========================================================================
# POST /api/v1/lex — lexical errors in source
# ===========================================================================


class TestLexEndpointWithErrors:
    def test_unknown_char_returns_200(self, client):
        # The lexer doesn't throw; it returns UNKNOWN tokens
        resp = client.post(LEX_URL, json={"source_code": "@STOP"})
        assert resp.status_code == 200

    def test_unknown_char_status_is_error(self, client):
        data = client.post(LEX_URL, json={"source_code": "@STOP"}).json()
        assert data["status"] == "ERROR"

    def test_unknown_char_success_false(self, client):
        data = client.post(LEX_URL, json={"source_code": "@STOP"}).json()
        assert data["result"]["success"] is False

    def test_unknown_char_diagnostics_not_empty(self, client):
        data = client.post(LEX_URL, json={"source_code": "@STOP"}).json()
        assert len(data["result"]["diagnostics"]) >= 1

    def test_diagnostic_has_required_fields(self, client):
        data = client.post(LEX_URL, json={"source_code": "@STOP"}).json()
        diag = data["result"]["diagnostics"][0]
        assert "code" in diag
        assert "message" in diag
        assert "severity" in diag

    def test_stop_token_still_present_after_unknown(self, client):
        data = client.post(LEX_URL, json={"source_code": "@STOP"}).json()
        token_values = [t["value"] for t in data["result"]["tokens"]]
        assert "STOP" in token_values

    def test_unterminated_literal_returns_error(self, client):
        data = client.post(LEX_URL, json={"source_code": "='5"}).json()
        assert data["result"]["success"] is False
        assert any(
            d["code"] == "UNTERMINATED_LITERAL"
            for d in data["result"]["diagnostics"]
        )


# ===========================================================================
# POST /api/v1/analyze — lexical stage only
# ===========================================================================


class TestAnalyzeLexicalStage:
    def test_analyze_with_lexical_stage_returns_200(self, client):
        resp = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        )
        assert resp.status_code == 200

    def test_lexical_stage_is_completed(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        lexical_status = next(
            (s for s in data["stage_statuses"] if s["stage"] == "lexical"), None
        )
        assert lexical_status is not None
        assert lexical_status["status"] == "COMPLETED"

    def test_lexical_in_completed_stages(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        assert "lexical" in data["completed_stages"]

    def test_lexical_result_in_results_dict(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        assert "lexical" in data["results"]

    def test_lexical_result_has_tokens(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        assert len(data["results"]["lexical"]["tokens"]) == 19

    def test_full_pipeline_lexical_completed(self, client):
        # Full pipeline: lexical is COMPLETED, others are NOT_IMPLEMENTED
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL},
        ).json()
        lexical_status = next(
            (s for s in data["stage_statuses"] if s["stage"] == "lexical"), None
        )
        assert lexical_status["status"] == "COMPLETED"

    def test_full_pipeline_other_stages_not_implemented(self, client):
        # Phase 5: syntax and pass-one are now COMPLETED too; only later stages are NOT_IMPLEMENTED
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL},
        ).json()
        for entry in data["stage_statuses"]:
            if entry["stage"] in (
                "macro", "pass-two",
                "linker", "loader", "execution", "ai",
            ):
                assert entry["status"] == "NOT_IMPLEMENTED"


    def test_session_id_is_present(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        assert len(data["session_id"]) > 0


# ===========================================================================
# GET /api/v1/session/{id}/lexical — cached result retrieval
# ===========================================================================


class TestSessionLexicalRetrieval:
    def test_existing_session_lexical_returns_200(self, client):
        # Create session via analyze
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        session_id = analyze_data["session_id"]

        resp = client.get(f"/api/v1/session/{session_id}/lexical")
        assert resp.status_code == 200

    def test_session_result_has_tokens(self, client):
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        session_id = analyze_data["session_id"]

        result = client.get(f"/api/v1/session/{session_id}/lexical").json()
        assert "tokens" in result
        assert len(result["tokens"]) == 19

    def test_nonexistent_session_returns_404(self, client):
        resp = client.get("/api/v1/session/nonexistent_id/lexical")
        assert resp.status_code == 404

    def test_session_result_token_count(self, client):
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["lexical"]},
        ).json()
        result = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/lexical"
        ).json()
        assert result["token_count"] == 19
