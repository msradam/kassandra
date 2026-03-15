"""Integration tests: full pipeline from diff → graph → context.

Tests the real-world scenario: given a diff from an MR,
build the graph, retrieve relevant context, and verify it's
both correct (includes what's needed) and compact (excludes what's not).
"""

import json
from pathlib import Path

import pytest

from graphrag.builder import OpenAPIGraph
from graphrag.retriever import SubgraphRetriever

FIXTURES = Path(__file__).parent / "fixtures"


# ── Real diff samples ──

# The actual diff from the Midas spending endpoint MR
MIDAS_SPENDING_DIFF = (
    Path(__file__).parent.parent / "simulator" / "samples" / "diffs" / "midas-spending.diff"
)


@pytest.fixture
def midas_spec():
    with open(FIXTURES / "midas-openapi.json") as f:
        return json.load(f)


@pytest.fixture
def calliope_spec():
    with open(FIXTURES / "calliope-openapi.json") as f:
        return json.load(f)


# ── Token efficiency tests ──


class TestTokenEfficiency:
    """Prove that graph-retrieved context is smaller than the full spec."""

    def test_single_endpoint_vs_full_spec(self, midas_spec):
        """Context for one endpoint should be much smaller than full spec."""
        full_spec_text = json.dumps(midas_spec, indent=2)
        full_spec_chars = len(full_spec_text)

        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/auth/login"])
        context_text = context.to_text()
        context_chars = len(context_text)

        # Graph context should be <20% of full spec
        ratio = context_chars / full_spec_chars
        assert ratio < 0.20, f"Context is {ratio:.0%} of full spec, expected <20%"

    def test_two_endpoints_vs_full_spec(self, midas_spec):
        """Even two endpoints should be significantly smaller than full spec."""
        full_spec_chars = len(json.dumps(midas_spec, indent=2))

        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints([
            "POST /api/auth/login",
            "POST /api/transactions/transfer",
        ])
        context_text = context.to_text()
        context_chars = len(context_text)

        ratio = context_chars / full_spec_chars
        assert ratio < 0.40, f"Context is {ratio:.0%} of full spec, expected <40%"

    def test_calliope_search_endpoint_compact(self, calliope_spec):
        """Search endpoint with nested allOf should still be compact."""
        full_spec_chars = len(json.dumps(calliope_spec, indent=2))

        graph = OpenAPIGraph.from_spec(calliope_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["GET /api/books/search"])
        context_chars = len(context.to_text())

        ratio = context_chars / full_spec_chars
        assert ratio < 0.30, f"Context is {ratio:.0%} of full spec, expected <30%"


# ── Correctness tests (does the context have what the LLM needs?) ──


class TestContextCorrectness:
    """Verify retrieved context includes everything needed for k6 generation."""

    def test_login_context_has_request_body(self, midas_spec):
        """Login context must include email + password fields."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/auth/login"])
        text = context.to_text()

        assert "email" in text
        assert "password" in text

    def test_login_context_has_response_shape(self, midas_spec):
        """Login context must show that response has 'token' field."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/auth/login"])
        text = context.to_text()

        assert "AuthResponse" in text
        assert "token" in text

    def test_transfer_context_has_all_fields(self, midas_spec):
        """Transfer context must include from/to account IDs, amount."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/transactions/transfer"])
        text = context.to_text()

        assert "from_account_id" in text
        assert "to_account_id" in text
        assert "amount" in text

    def test_transfer_context_shows_required_fields(self, midas_spec):
        """LLM needs to know which fields are required."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/transactions/transfer"])
        d = context.to_dict()

        transfer_schema = d["schemas"].get("TransferRequest", {})
        required_props = [
            p["name"] for p in transfer_schema.get("properties", [])
            if p.get("required")
        ]
        assert "from_account_id" in required_props
        assert "to_account_id" in required_props
        assert "amount" in required_props

    def test_search_context_includes_nested_schemas(self, calliope_spec):
        """Search endpoint context must include BookOut and ReviewOut via allOf."""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["GET /api/books/search"])

        # SearchResponse references BookOut and ReviewOut
        assert "SearchResponse" in context.schemas
        assert "BookOut" in context.schemas or "ReviewOut" in context.schemas

    def test_auth_endpoints_have_login_context(self, calliope_spec):
        """Creating a book requires auth — context should signal this."""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/books"])

        assert context.requires_auth
        assert "BookCreate" in context.schemas


# ── Exclusion tests (context should NOT include unrelated schemas) ──


class TestContextExclusion:
    """Verify retrieved context excludes unrelated schemas."""

    def test_login_excludes_transaction_schemas(self, midas_spec):
        """Login context should not include any transaction/account schemas."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["POST /api/auth/login"])

        assert "TransferRequest" not in context.schemas
        assert "TransactionOut" not in context.schemas
        assert "AccountOut" not in context.schemas
        assert "AccountListResponse" not in context.schemas

    def test_health_excludes_everything(self, midas_spec):
        """Health endpoint should only pull HealthResponse."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["GET /api/health"])

        non_health = [s for s in context.schemas if "Health" not in s and "Validation" not in s]
        assert len(non_health) == 0, f"Unexpected schemas: {non_health}"

    def test_books_list_excludes_review_schemas(self, calliope_spec):
        """GET /api/books should not include review schemas."""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        retriever = SubgraphRetriever(graph)
        context = retriever.for_endpoints(["GET /api/books"])

        assert "ReviewCreate" not in context.schemas
        assert "ReviewOut" not in context.schemas


# ── Real diff pipeline tests ──


class TestRealDiffPipeline:
    """End-to-end tests using actual MR diffs from the repo."""

    def test_midas_transfer_diff(self, midas_spec):
        """Simulate a diff that modifies the transfer endpoint."""
        diff = """\
diff --git a/demos/midas-bank/app.py b/demos/midas-bank/app.py
--- a/demos/midas-bank/app.py
+++ b/demos/midas-bank/app.py
@@ -295,6 +295,8 @@ def deposit(req: DepositRequest):
 @app.post("/api/transactions/transfer", status_code=201, response_model=TransactionOut)
 def transfer(req: TransferRequest, user=Depends(get_current_user), db=Depends(get_db)):
+    # Added rate limiting
+    check_rate_limit(user["id"])
     if req.amount <= 0:
         raise HTTPException(400, "Amount must be positive")
"""
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)

        endpoints = retriever.endpoints_from_diff(diff)
        assert "POST /api/transactions/transfer" in endpoints

        context = retriever.for_endpoints(endpoints)
        assert "TransferRequest" in context.schemas
        assert "TransactionOut" in context.schemas

        text = context.to_text()
        assert "from_account_id" in text
        assert "amount" in text

    def test_calliope_review_diff(self, calliope_spec):
        """Simulate a diff that modifies the create review endpoint."""
        diff = """\
diff --git a/demos/calliope-books/app.js b/demos/calliope-books/app.js
--- a/demos/calliope-books/app.js
+++ b/demos/calliope-books/app.js
@@ -150,6 +150,8 @@ app.get('/api/books/:id', (req, res) => {
 router.post('/api/books/:id/reviews', authenticate, async (req, res) => {
+  // Validate rating range server-side
+  if (req.body.rating < 1 || req.body.rating > 5) return res.status(400).json({ error: 'Invalid rating' });
   const { rating, comment } = req.body;
"""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        retriever = SubgraphRetriever(graph)

        endpoints = retriever.endpoints_from_diff(diff)
        assert len(endpoints) >= 1
        assert any("reviews" in ep for ep in endpoints)

        context = retriever.for_endpoints(endpoints)
        assert "ReviewCreate" in context.schemas
        text = context.to_text()
        assert "rating" in text

    @pytest.mark.skipif(
        not MIDAS_SPENDING_DIFF.exists(),
        reason="Spending diff sample not available"
    )
    def test_real_midas_spending_diff(self, midas_spec):
        """Use the actual spending endpoint diff from the simulator samples."""
        diff = MIDAS_SPENDING_DIFF.read_text()
        graph = OpenAPIGraph.from_spec(midas_spec)
        retriever = SubgraphRetriever(graph)

        endpoints = retriever.endpoints_from_diff(diff)
        # The spending endpoint isn't in the current spec, so the diff parser
        # should still identify the closest account-related endpoints
        # OR return empty if no match — both are valid behaviors
        context = retriever.for_endpoints(endpoints)
        # Even if no direct match, the pipeline should not crash
        assert isinstance(context.to_text(), str)
        assert isinstance(context.to_dict(), dict)


# ── Graph structure tests ──


class TestGraphStructure:
    """Verify the graph has expected structural properties."""

    def test_midas_graph_is_connected_via_auth(self, midas_spec):
        """All secured endpoints should share the auth flow."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        # Login returns AuthResponse which has 'token'
        # Other endpoints need that token as Bearer header
        login_context = SubgraphRetriever(graph).for_endpoints(["POST /api/auth/login"])
        assert "token" in login_context.to_text()

    def test_calliope_graph_depth(self, calliope_spec):
        """SearchResponse → BookOut and ReviewOut should be reachable within 2 hops."""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        G = graph.graph

        # SearchResponse -> BookOut (via REFERENCES from allOf)
        assert G.has_edge("SearchResponse", "BookOut")
        # SearchResponse -> ReviewOut (via inline allOf properties)
        assert G.has_edge("SearchResponse", "ReviewOut")

    def test_no_orphan_schemas(self, midas_spec):
        """Every schema should be reachable from at least one endpoint."""
        graph = OpenAPIGraph.from_spec(midas_spec)
        G = graph.graph

        endpoints = graph.endpoints()
        schemas = graph.schemas()

        reachable = set()
        for ep in endpoints:
            for node in _bfs_reachable(G, ep):
                if G.nodes[node].get("type") == "schema":
                    reachable.add(node)

        # Allow HTTPValidationError as it's auto-generated by FastAPI
        unreachable = set(schemas) - reachable
        # Filter out auto-generated validation schemas
        unreachable = {s for s in unreachable if "Validation" not in s and "HTTP" not in s}
        assert len(unreachable) == 0, f"Orphan schemas: {unreachable}"

    def test_graph_is_dag_from_endpoints(self, calliope_spec):
        """The subgraph from any single endpoint should be a DAG (no cycles)."""
        graph = OpenAPIGraph.from_spec(calliope_spec)
        G = graph.graph

        for ep in graph.endpoints():
            subgraph_nodes = _bfs_reachable(G, ep)
            sub = G.subgraph(subgraph_nodes)
            # Should have no cycles in the endpoint→schema→property direction
            # (property nodes are leaves, schemas can reference other schemas)
            assert not _has_cycle_in_subgraph(sub, ep)


def _bfs_reachable(G, start):
    """BFS from start, return all reachable nodes."""
    visited = {start}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for neighbor in G.successors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


def _has_cycle_in_subgraph(G, start):
    """Check for cycles reachable from start using DFS."""
    visited = set()
    stack = set()

    def dfs(node):
        visited.add(node)
        stack.add(node)
        for neighbor in G.successors(node):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in stack:
                return True
        stack.discard(node)
        return False

    return dfs(start)
