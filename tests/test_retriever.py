"""Tests for subgraph retrieval — given changed endpoints, pull relevant context."""

import json
from pathlib import Path

import pytest

from graphrag.builder import OpenAPIGraph
from graphrag.retriever import SubgraphRetriever

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def midas_graph():
    with open(FIXTURES / "midas-openapi.json") as f:
        spec = json.load(f)
    return OpenAPIGraph.from_spec(spec)


@pytest.fixture
def calliope_graph():
    with open(FIXTURES / "calliope-openapi.json") as f:
        spec = json.load(f)
    return OpenAPIGraph.from_spec(spec)


@pytest.fixture
def midas_retriever(midas_graph):
    return SubgraphRetriever(midas_graph)


@pytest.fixture
def calliope_retriever(calliope_graph):
    return SubgraphRetriever(calliope_graph)


# ── Endpoint-based retrieval ──


class TestEndpointRetrieval:
    def test_retrieve_single_endpoint(self, midas_retriever):
        """Retrieving context for one endpoint should include its schemas."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        assert "LoginRequest" in context.schemas
        assert "AuthResponse" in context.schemas
        assert "POST /api/auth/login" in context.endpoints

    def test_retrieve_includes_nested_refs(self, midas_retriever):
        """AuthResponse references UserOut — should be included."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        assert "UserOut" in context.schemas

    def test_retrieve_includes_auth(self, calliope_retriever):
        """Secured endpoints should include auth context."""
        context = calliope_retriever.for_endpoints(["POST /api/books"])
        assert context.requires_auth

    def test_retrieve_excludes_unrelated(self, midas_retriever):
        """Retrieving login context should NOT include account schemas."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        assert "AccountOut" not in context.schemas
        assert "TransactionOut" not in context.schemas

    def test_retrieve_multiple_endpoints(self, midas_retriever):
        """Multiple endpoints should union their subgraphs."""
        context = midas_retriever.for_endpoints([
            "POST /api/auth/login",
            "GET /api/accounts",
        ])
        assert "LoginRequest" in context.schemas
        assert "AccountOut" in context.schemas
        assert "AccountListResponse" in context.schemas

    def test_retrieve_with_parameters(self, midas_retriever):
        """Endpoint with path params should include param info."""
        context = midas_retriever.for_endpoints(["GET /api/accounts/{account_id}"])
        assert len(context.parameters) >= 1
        param_names = [p["name"] for p in context.parameters]
        assert "account_id" in param_names


# ── Diff-based retrieval ──


class TestDiffRetrieval:
    def test_diff_identifies_changed_endpoints(self, midas_retriever):
        """Should extract endpoint paths from a unified diff."""
        diff = """
diff --git a/demos/midas-bank/app.py b/demos/midas-bank/app.py
--- a/demos/midas-bank/app.py
+++ b/demos/midas-bank/app.py
@@ -280,6 +280,46 @@
+@app.post("/api/transactions/transfer", status_code=201, response_model=TransactionOut)
+def transfer(req: TransferRequest, user=Depends(get_current_user), db=Depends(get_db)):
+    if req.amount <= 0:
"""
        endpoints = midas_retriever.endpoints_from_diff(diff)
        assert "POST /api/transactions/transfer" in endpoints

    def test_diff_retrieval_end_to_end(self, midas_retriever):
        """Full pipeline: diff → endpoints → context."""
        diff = """
+@app.post("/api/transactions/transfer", status_code=201)
+def transfer(req: TransferRequest, user=Depends(get_current_user)):
"""
        endpoints = midas_retriever.endpoints_from_diff(diff)
        assert len(endpoints) >= 1
        context = midas_retriever.for_endpoints(endpoints)
        assert len(context.schemas) >= 1

    def test_diff_with_express_routes(self, calliope_retriever):
        """Should parse Express-style route definitions too."""
        diff = """
+router.get('/api/books/search', async (req, res) => {
+  const { q, limit = 20, offset = 0 } = req.query;
"""
        endpoints = calliope_retriever.endpoints_from_diff(diff)
        assert any("books/search" in ep or "/api/books" in ep for ep in endpoints)


# ── Context serialization ──


class TestContextSerialization:
    def test_to_text_includes_schemas(self, midas_retriever):
        """Serialized context should include schema definitions."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        text = context.to_text()
        assert "LoginRequest" in text
        assert "AuthResponse" in text
        assert "email" in text
        assert "password" in text

    def test_to_text_includes_endpoint_info(self, midas_retriever):
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        text = context.to_text()
        assert "POST" in text
        assert "/api/auth/login" in text

    def test_to_text_includes_auth_hint(self, calliope_retriever):
        context = calliope_retriever.for_endpoints(["POST /api/books"])
        text = context.to_text()
        assert "auth" in text.lower() or "bearer" in text.lower()

    def test_to_text_compact(self, midas_retriever):
        """Context for a single endpoint should be reasonably compact."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        text = context.to_text()
        # Should be under 2000 chars for a single endpoint
        assert len(text) < 2000

    def test_to_dict(self, midas_retriever):
        """Context should be serializable to dict for JSON output."""
        context = midas_retriever.for_endpoints(["POST /api/auth/login"])
        d = context.to_dict()
        assert "endpoints" in d
        assert "schemas" in d
        assert isinstance(d["schemas"], dict)


# ── Edge cases ──


class TestEdgeCases:
    def test_nonexistent_endpoint(self, midas_retriever):
        """Should handle unknown endpoints gracefully."""
        context = midas_retriever.for_endpoints(["GET /api/nonexistent"])
        assert len(context.schemas) == 0
        assert len(context.endpoints) == 0

    def test_empty_endpoint_list(self, midas_retriever):
        context = midas_retriever.for_endpoints([])
        assert len(context.schemas) == 0

    def test_health_endpoint_minimal_context(self, midas_retriever):
        """Health endpoint should have minimal context (no auth, simple schema)."""
        context = midas_retriever.for_endpoints(["GET /api/health"])
        assert not context.requires_auth
        assert "HealthResponse" in context.schemas
        assert len(context.schemas) <= 2  # Just HealthResponse, maybe ValidationError
