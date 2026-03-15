"""Tests for OpenAPI spec → NetworkX graph builder."""

import json
from pathlib import Path

import pytest

from graphrag.builder import OpenAPIGraph

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def midas_spec():
    with open(FIXTURES / "midas-openapi.json") as f:
        return json.load(f)


@pytest.fixture
def calliope_spec():
    with open(FIXTURES / "calliope-openapi.json") as f:
        return json.load(f)


@pytest.fixture
def midas_graph(midas_spec):
    return OpenAPIGraph.from_spec(midas_spec)


@pytest.fixture
def calliope_graph(calliope_spec):
    return OpenAPIGraph.from_spec(calliope_spec)


# ── Node creation ──


class TestNodeCreation:
    def test_endpoints_become_nodes(self, midas_graph):
        """Each path+method combo should be an endpoint node."""
        endpoint_nodes = midas_graph.endpoints()
        # Midas has: register, login, list_accounts, get_account, create_account,
        # list_transactions, transfer, deposit, health
        assert len(endpoint_nodes) >= 9
        assert "POST /api/auth/login" in endpoint_nodes
        assert "GET /api/health" in endpoint_nodes

    def test_schemas_become_nodes(self, midas_graph):
        """Each components/schemas entry should be a schema node."""
        schema_nodes = midas_graph.schemas()
        assert "RegisterRequest" in schema_nodes
        assert "AuthResponse" in schema_nodes
        assert "AccountOut" in schema_nodes

    def test_properties_become_nodes(self, midas_graph):
        """Schema properties should be property nodes."""
        props = midas_graph.properties_of("LoginRequest")
        assert "email" in props
        assert "password" in props

    def test_security_schemes_become_nodes(self, calliope_graph):
        """Security schemes should be nodes."""
        assert calliope_graph.has_node("security:BearerAuth")

    def test_node_types(self, midas_graph):
        """Every node should have a 'type' attribute."""
        G = midas_graph.graph
        for node, data in G.nodes(data=True):
            assert "type" in data, f"Node {node} missing 'type' attribute"
            assert data["type"] in ("endpoint", "schema", "property", "security", "parameter")


# ── Edge creation ──


class TestEdgeCreation:
    def test_endpoint_returns_schema(self, midas_graph):
        """Endpoint nodes should have RETURNS edges to response schemas."""
        G = midas_graph.graph
        assert G.has_edge("POST /api/auth/login", "AuthResponse")
        edge_data = G.edges["POST /api/auth/login", "AuthResponse"]
        assert edge_data["relation"] == "RETURNS"

    def test_endpoint_accepts_schema(self, midas_graph):
        """Endpoint nodes should have ACCEPTS edges to request body schemas."""
        G = midas_graph.graph
        assert G.has_edge("POST /api/auth/login", "LoginRequest")
        edge_data = G.edges["POST /api/auth/login", "LoginRequest"]
        assert edge_data["relation"] == "ACCEPTS"

    def test_schema_has_property(self, midas_graph):
        """Schema nodes should have HAS_PROPERTY edges to property nodes."""
        G = midas_graph.graph
        assert G.has_edge("LoginRequest", "LoginRequest.email")
        edge_data = G.edges["LoginRequest", "LoginRequest.email"]
        assert edge_data["relation"] == "HAS_PROPERTY"

    def test_schema_references_schema(self, midas_graph):
        """Schemas that $ref other schemas should have REFERENCES edges."""
        G = midas_graph.graph
        # AuthResponse has a 'user' property that references UserOut
        assert G.has_edge("AuthResponse", "UserOut")
        edge_data = G.edges["AuthResponse", "UserOut"]
        assert edge_data["relation"] == "REFERENCES"

    def test_endpoint_requires_auth(self, calliope_graph):
        """Secured endpoints should have REQUIRES_AUTH edges."""
        G = calliope_graph.graph
        # POST /api/books requires BearerAuth
        assert G.has_edge("POST /api/books", "security:BearerAuth")
        edge_data = G.edges["POST /api/books", "security:BearerAuth"]
        assert edge_data["relation"] == "REQUIRES_AUTH"

    def test_endpoint_has_parameter(self, midas_graph):
        """Endpoints with path/query params should have HAS_PARAM edges."""
        G = midas_graph.graph
        # GET /api/accounts/{account_id} has a path param
        param_edges = [
            (u, v) for u, v, d in G.edges(data=True)
            if u == "GET /api/accounts/{account_id}" and d.get("relation") == "HAS_PARAM"
        ]
        assert len(param_edges) >= 1

    def test_unsecured_endpoint_no_auth_edge(self, midas_graph):
        """Health endpoint should NOT have auth edges."""
        G = midas_graph.graph
        auth_edges = [
            (u, v) for u, v, d in G.edges(data=True)
            if u == "GET /api/health" and d.get("relation") == "REQUIRES_AUTH"
        ]
        assert len(auth_edges) == 0


# ── Node attributes ──


class TestNodeAttributes:
    def test_endpoint_has_method_and_path(self, midas_graph):
        G = midas_graph.graph
        data = G.nodes["POST /api/auth/login"]
        assert data["method"] == "POST"
        assert data["path"] == "/api/auth/login"

    def test_endpoint_has_summary(self, midas_graph):
        G = midas_graph.graph
        data = G.nodes["POST /api/auth/login"]
        assert "summary" in data

    def test_property_has_type_info(self, midas_graph):
        G = midas_graph.graph
        data = G.nodes["LoginRequest.email"]
        assert data["property_type"] == "string"

    def test_schema_has_required_fields(self, midas_graph):
        G = midas_graph.graph
        data = G.nodes["LoginRequest"]
        assert "required" in data
        assert "email" in data["required"]
        assert "password" in data["required"]


# ── Cross-spec compatibility ──


class TestCalliopeSpec:
    def test_calliope_endpoints(self, calliope_graph):
        endpoints = calliope_graph.endpoints()
        assert "GET /api/books" in endpoints
        assert "GET /api/books/search" in endpoints
        assert "POST /api/books/{id}/reviews" in endpoints

    def test_calliope_nested_refs(self, calliope_graph):
        """SearchResponse has nested $ref to ReviewOut via recent_reviews."""
        G = calliope_graph.graph
        # SearchResponse should reference BookOut and ReviewOut
        refs = [
            v for u, v, d in G.edges(data=True)
            if u == "SearchResponse" and d.get("relation") == "REFERENCES"
        ]
        # Should reference at least BookOut and ReviewOut
        assert len(refs) >= 2

    def test_calliope_schema_count(self, calliope_graph):
        schemas = calliope_graph.schemas()
        # RegisterRequest, LoginRequest, AuthResponse, UserOut, BookCreate,
        # BookOut, BookListResponse, SearchResponse, ReviewCreate, ReviewOut,
        # ReviewListResponse, HealthResponse, ErrorResponse
        assert len(schemas) >= 12


# ── Serialization ──


class TestSerialization:
    def test_to_dict_roundtrip(self, midas_graph):
        """Graph should serialize to dict and back."""
        data = midas_graph.to_dict()
        assert "nodes" in data
        assert "edges" in data
        restored = OpenAPIGraph.from_dict(data)
        assert set(restored.endpoints()) == set(midas_graph.endpoints())
        assert set(restored.schemas()) == set(midas_graph.schemas())

    def test_stats(self, midas_graph):
        stats = midas_graph.stats()
        assert stats["endpoints"] >= 9
        assert stats["schemas"] >= 5
        assert stats["edges"] > stats["endpoints"]  # should have many more edges
