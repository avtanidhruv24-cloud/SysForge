"""
Integration tests — Parser API endpoints (Phase 4).

Tests the full HTTP stack: TestClient → FastAPI → AnalysisService → Parser.

Covers:
  - POST /api/v1/parse  with valid source → real SyntaxResult
  - POST /api/v1/parse  with invalid source → HTTP 422 (Pydantic validation)
  - POST /api/v1/parse  with syntax errors → ERROR status + diagnostics
  - POST /api/v1/analyze  with stages=["syntax"] → real syntax results
  - POST /api/v1/analyze  (full pipeline) → lexical+syntax COMPLETED
  - GET  /api/v1/session/{id}/syntax  → cached result retrieval
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

PARSE_URL = "/api/v1/parse"
ANALYZE_URL = "/api/v1/analyze"


# ===========================================================================
# POST /api/v1/parse — canonical source
# ===========================================================================


class TestParseEndpointCanonical:
    def test_returns_200(self, client):
        resp = client.post(PARSE_URL, json={"source_code": CANONICAL})
        assert resp.status_code == 200

    def test_response_has_session_id(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_status_is_completed(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["status"] == "COMPLETED"

    def test_result_is_not_null(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"] is not None

    def test_result_has_statements(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert "statements" in data["result"]
        assert isinstance(data["result"]["statements"], list)

    def test_correct_statement_count(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["statement_count"] == 7

    def test_statements_list_length(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert len(data["result"]["statements"]) == 7

    def test_success_flag_true(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["success"] is True

    def test_no_diagnostics(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["diagnostics"] == []

    def test_first_statement_is_start(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        first = data["result"]["statements"][0]
        assert first["directive"] == "START"
        assert first["operand"] == "100"

    def test_first_statement_no_label(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["statements"][0]["label"] is None

    def test_second_statement_is_mover(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        s2 = data["result"]["statements"][1]
        assert s2["imperative"] == "MOVER"
        assert s2["register"] == "AREG"
        assert s2["operand"] == "='5'"

    def test_fourth_statement_has_label_loop(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        s4 = data["result"]["statements"][3]
        assert s4["label"] == "LOOP"
        assert s4["imperative"] == "SUB"

    def test_sixth_statement_has_label_result(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        s6 = data["result"]["statements"][5]
        assert s6["label"] == "RESULT"
        assert s6["declarative"] == "DS"
        assert s6["operand"] == "1"

    def test_last_statement_is_end(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        last = data["result"]["statements"][-1]
        assert last["directive"] == "END"

    def test_each_statement_has_required_fields(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        for s in data["result"]["statements"]:
            assert "line_number" in s
            assert "is_valid" in s
            assert "errors" in s

    def test_all_statements_valid(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        for s in data["result"]["statements"]:
            assert s["is_valid"] is True, (
                f"Statement on line {s['line_number']} should be valid: {s['errors']}"
            )

    def test_statement_class_fields_present(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        for s in data["result"]["statements"]:
            assert "statement_class" in s

    def test_first_statement_class_is_ad(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["statements"][0]["statement_class"] == "AD"

    def test_mover_class_is_is(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["statements"][1]["statement_class"] == "IS"

    def test_ds_class_is_dl(self, client):
        data = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert data["result"]["statements"][5]["statement_class"] == "DL"

    def test_content_type_is_json(self, client):
        resp = client.post(PARSE_URL, json={"source_code": CANONICAL})
        assert "application/json" in resp.headers["content-type"]

    def test_two_requests_produce_different_session_ids(self, client):
        r1 = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        r2 = client.post(PARSE_URL, json={"source_code": CANONICAL}).json()
        assert r1["session_id"] != r2["session_id"]


# ===========================================================================
# POST /api/v1/parse — validation errors
# ===========================================================================


class TestParseEndpointValidation:
    def test_rejects_empty_source(self, client):
        resp = client.post(PARSE_URL, json={"source_code": ""})
        assert resp.status_code == 422

    def test_rejects_whitespace_only(self, client):
        resp = client.post(PARSE_URL, json={"source_code": "   "})
        assert resp.status_code == 422

    def test_rejects_missing_field(self, client):
        resp = client.post(PARSE_URL, json={})
        assert resp.status_code == 422

    def test_error_envelope_shape(self, client):
        resp = client.post(PARSE_URL, json={"source_code": ""})
        data = resp.json()
        assert "error" in data


# ===========================================================================
# POST /api/v1/parse — syntax errors in source
# ===========================================================================


class TestParseEndpointWithErrors:
    def test_syntax_error_returns_200(self, client):
        # Parser doesn't throw; returns ERROR status
        resp = client.post(PARSE_URL, json={"source_code": "START"})
        assert resp.status_code == 200

    def test_syntax_error_status_is_error(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        assert data["status"] == "ERROR"

    def test_syntax_error_success_false(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        assert data["result"]["success"] is False

    def test_syntax_error_diagnostics_not_empty(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        assert len(data["result"]["diagnostics"]) >= 1

    def test_diagnostic_has_required_fields(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        diag = data["result"]["diagnostics"][0]
        assert "message" in diag
        assert "severity" in diag

    def test_invalid_statement_marked_in_list(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        bad_stmts = [s for s in data["result"]["statements"] if not s["is_valid"]]
        assert len(bad_stmts) >= 1

    def test_bad_line_has_errors_list(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        bad = next(s for s in data["result"]["statements"] if not s["is_valid"])
        assert len(bad["errors"]) >= 1
        assert len(bad["errors"][0]["message"]) > 0

    def test_error_recovery_valid_line_after_bad(self, client):
        data = client.post(
            PARSE_URL,
            json={"source_code": "START 100\nMOVER AREG\nEND"},
        ).json()
        # END on line 3 should still be valid
        end_stmt = next(
            s for s in data["result"]["statements"] if s["directive"] == "END"
        )
        assert end_stmt["is_valid"] is True

    def test_missing_operand_error_has_line(self, client):
        data = client.post(PARSE_URL, json={"source_code": "START"}).json()
        diag = data["result"]["diagnostics"][0]
        assert diag.get("line") is not None


# ===========================================================================
# POST /api/v1/analyze — syntax stage
# ===========================================================================


class TestAnalyzeSyntaxStage:
    def test_analyze_with_syntax_stage_returns_200(self, client):
        resp = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        )
        assert resp.status_code == 200

    def test_syntax_stage_is_completed(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        syntax_status = next(
            (s for s in data["stage_statuses"] if s["stage"] == "syntax"), None
        )
        assert syntax_status is not None
        assert syntax_status["status"] == "COMPLETED"

    def test_syntax_in_completed_stages(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        assert "syntax" in data["completed_stages"]

    def test_syntax_result_in_results_dict(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        assert "syntax" in data["results"]

    def test_syntax_result_has_statements(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        assert len(data["results"]["syntax"]["statements"]) == 7

    def test_full_pipeline_both_lexical_and_syntax_completed(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL},
        ).json()
        completed = data["completed_stages"]
        assert "lexical" in completed
        assert "syntax" in completed

    def test_full_pipeline_remaining_stages_not_implemented(self, client):
        data = client.post(ANALYZE_URL, json={"source_code": CANONICAL}).json()
        for entry in data["stage_statuses"]:
            if entry["stage"] in (
                "macro", "pass-two", "linker", "loader",
                "execution", "ai",
            ):
                assert entry["status"] == "NOT_IMPLEMENTED"


    def test_session_id_present(self, client):
        data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        assert len(data["session_id"]) > 0


# ===========================================================================
# GET /api/v1/session/{id}/syntax
# ===========================================================================


class TestSessionSyntaxRetrieval:
    def test_existing_session_syntax_returns_200(self, client):
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        resp = client.get(f"/api/v1/session/{analyze_data['session_id']}/syntax")
        assert resp.status_code == 200

    def test_session_result_has_statements(self, client):
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        result = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/syntax"
        ).json()
        assert "statements" in result
        assert len(result["statements"]) == 7

    def test_nonexistent_session_returns_404(self, client):
        resp = client.get("/api/v1/session/nonexistent_id/syntax")
        assert resp.status_code == 404

    def test_session_result_statement_count(self, client):
        analyze_data = client.post(
            ANALYZE_URL,
            json={"source_code": CANONICAL, "stages": ["syntax"]},
        ).json()
        result = client.get(
            f"/api/v1/session/{analyze_data['session_id']}/syntax"
        ).json()
        assert result["statement_count"] == 7
