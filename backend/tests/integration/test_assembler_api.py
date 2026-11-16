"""
Integration tests — Assembler Pass-I API endpoints (Phase 5).

Tests the full HTTP stack: TestClient -> FastAPI -> AnalysisService -> AssemblerPass1.

Covers:
  - POST /api/v1/assemble/pass1 with valid source -> real Pass1Result
  - POST /api/v1/assemble/pass1 with invalid input (validation error) -> HTTP 422
  - POST /api/v1/assemble/pass1 with semantic/pass1 errors -> ERROR status + diagnostics
  - POST /api/v1/analyze with stages=["pass-one"] -> real Pass1Result in pipeline
  - POST /api/v1/analyze (full pipeline) -> lexical + syntax + pass-one COMPLETED
  - GET  /api/v1/session/{id}/pass-one -> cached result retrieval
  - GET  /api/v1/session/{id}/symbols -> sub-view retrieval
  - GET  /api/v1/session/{id}/literals -> sub-view retrieval
  - GET  /api/v1/session/{id}/pools -> sub-view retrieval
  - GET  /api/v1/session/{id}/intermediate -> sub-view retrieval
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

ASSEMBLE_PASS1_URL = "/api/v1/assemble/pass1"
ANALYZE_URL = "/api/v1/analyze"


# ===========================================================================
# POST /api/v1/assemble/pass1 — canonical source
# ===========================================================================


class TestAssemblePass1EndpointCanonical:
    def test_returns_200(self, client):
        resp = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL})
        assert resp.status_code == 200

    def test_response_has_session_id(self, client):
        data = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_status_is_completed(self, client):
        data = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()
        assert data["status"] == "COMPLETED"

    def test_result_is_not_null(self, client):
        data = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()
        assert data["result"] is not None

    def test_result_contains_all_core_tables(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        assert "symbol_table" in res
        assert "literal_table" in res
        assert "pool_table" in res
        assert "intermediate_code" in res
        assert "lc_trace" in res

    def test_symbol_table_contents(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        syms = {s["name"]: s for s in res["symbol_table"]}
        assert "LOOP" in syms
        assert "RESULT" in syms
        assert syms["LOOP"]["value"] == 102
        assert syms["RESULT"]["value"] == 104
        assert syms["LOOP"]["is_defined"] is True
        assert syms["RESULT"]["is_defined"] is True

    def test_literal_table_contents(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        lits = res["literal_table"]
        assert len(lits) == 3
        lit_vals = [lit["value"] for lit in lits]
        assert "='5'" in lit_vals
        assert "='1'" in lit_vals
        assert "='2'" in lit_vals
        # Check literals allocated at END
        assert lits[0]["address"] == 105
        assert lits[1]["address"] == 106
        assert lits[2]["address"] == 107

    def test_pool_table_contents(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        pools = res["pool_table"]
        assert len(pools) == 1
        assert pools[0]["pool_number"] == 1
        assert pools[0]["littab_start_index"] == 0
        assert pools[0]["literal_count"] == 3

    def test_intermediate_code_emitted(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        ic = res["intermediate_code"]
        assert len(ic) > 0
        mnemonics = [record["mnemonic"] for record in ic]
        assert "START" in mnemonics
        assert "MOVER" in mnemonics
        assert "ADD" in mnemonics
        assert "SUB" in mnemonics
        assert "MOVEM" in mnemonics
        assert "DS" in mnemonics
        assert "END" in mnemonics

    def test_metadata_fields(self, client):
        res = client.post(ASSEMBLE_PASS1_URL, json={"source_code": CANONICAL}).json()["result"]
        assert res["starting_address"] == 100
        assert res["final_location_counter"] == 108
        assert res["success"] is True
        assert res["unresolved_symbol_count"] == 0


# ===========================================================================
# POST /api/v1/assemble/pass1 — error scenarios
# ===========================================================================


class TestAssemblePass1EndpointErrors:
    def test_missing_source_code_returns_422(self, client):
        resp = client.post(ASSEMBLE_PASS1_URL, json={})
        assert resp.status_code == 422

    def test_undefined_symbol_returns_error_status(self, client):
        source = "START 200\nMOVER AREG UNDEF\nEND"
        data = client.post(ASSEMBLE_PASS1_URL, json={"source_code": source}).json()
        assert data["status"] == "ERROR"
        assert data["result"]["success"] is False
        assert data["result"]["unresolved_symbol_count"] == 1
        errors = [d for d in data["result"]["diagnostics"] if d["severity"] == "ERROR"]
        assert len(errors) >= 1
        assert any("UNDEF" in e["message"] for e in errors)

    def test_duplicate_symbol_returns_error_status(self, client):
        source = "START 100\nALPHA DS 1\nALPHA DS 1\nEND"
        data = client.post(ASSEMBLE_PASS1_URL, json={"source_code": source}).json()
        assert data["status"] == "ERROR"
        assert data["result"]["success"] is False
        codes = [d["code"] for d in data["result"]["diagnostics"]]
        assert "DUPLICATE_SYMBOL" in codes


# ===========================================================================
# POST /api/v1/analyze — pipeline integration
# ===========================================================================


class TestAnalyzePipelinePass1:
    def test_full_pipeline_completes_pass1(self, client):
        resp = client.post(ANALYZE_URL, json={"source_code": CANONICAL})
        assert resp.status_code == 200
        data = resp.json()
        assert "pass-one" in data["completed_stages"]
        assert "lexical" in data["completed_stages"]
        assert "syntax" in data["completed_stages"]

    def test_results_contains_pass1_and_subviews(self, client):
        resp = client.post(ANALYZE_URL, json={"source_code": CANONICAL})
        results = resp.json()["results"]
        assert "pass-one" in results
        assert "symbols" in results
        assert "literals" in results
        assert "pools" in results
        assert "intermediate" in results
        assert results["pass-one"]["starting_address"] == 100

    def test_stage_statuses_show_completed(self, client):
        resp = client.post(ANALYZE_URL, json={"source_code": CANONICAL})
        statuses = {s["stage"]: s["status"] for s in resp.json()["stage_statuses"]}
        assert statuses.get("pass-one") == "COMPLETED"
        assert statuses.get("symbols") == "COMPLETED"
        assert statuses.get("literals") == "COMPLETED"
        assert statuses.get("pools") == "COMPLETED"
        assert statuses.get("intermediate") == "COMPLETED"


# ===========================================================================
# GET /api/v1/session/{id}/{stage} — session retrieval
# ===========================================================================


class TestSessionStageRetrieval:
    def test_retrieve_pass_one_stage(self, client):
        init_resp = client.post(ANALYZE_URL, json={"source_code": CANONICAL})
        session_id = init_resp.json()["session_id"]

        resp = client.get(f"/api/v1/session/{session_id}/pass-one")
        assert resp.status_code == 200
        data = resp.json()
        assert "symbol_table" in data
        assert "literal_table" in data

    def test_retrieve_subviews(self, client):
        init_resp = client.post(ANALYZE_URL, json={"source_code": CANONICAL})
        session_id = init_resp.json()["session_id"]

        for stage in ("symbols", "literals", "pools", "intermediate"):
            resp = client.get(f"/api/v1/session/{session_id}/{stage}")
            assert resp.status_code == 200
            data = resp.json()
            assert "symbol_table" in data

    def test_nonexistent_session_returns_404(self, client):
        resp = client.get("/api/v1/session/nonexistent-session-id/pass-one")
        assert resp.status_code == 404
