import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

from mempalace_agi.unified_api import create_app

@pytest.fixture
def mock_clients():
    palace = Mock()
    palace.to_dict.return_value = {"palace": True}
    palace.get_persistence_stats.return_value = {"palace_wings": 5}
    palace.semantic_search.return_value = [{"text": "Found it!"}]
    palace.search_across_domains.return_value = {"CrossDomain": [{"text": "Cross context"}]}
    
    engine = Mock()
    
    kg = Mock()
    kg.stats.return_value = {"triples": 100}
    
    specialists = Mock()
    specialists.get_domain_context.return_value = ["Context"]
    specialists.get_pre_investigation_context.return_value = {"domain": "CrossDomain", "hypothesis_id": "H1"}
    
    return palace, engine, kg, specialists

@pytest.fixture
def client(mock_clients):
    app = create_app(*mock_clients)
    return TestClient(app)

def test_palace_status(client):
    response = client.get("/api/v1/palace/status")
    assert response.status_code == 200
    assert response.json() == {"palace": True}

def test_palace_search(client, mock_clients):
    palace = mock_clients[0]
    response = client.post("/api/v1/palace/search", json={"query": "test query", "n_results": 5})
    assert response.status_code == 200
    assert response.json() == [{"text": "Found it!"}]
    palace.semantic_search.assert_called_once_with("test query", None, 5)

def test_integration_status(client):
    response = client.get("/api/v1/integration/status")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_integration_cross_domain(client, mock_clients):
    palace = mock_clients[0]
    response = client.get("/api/v1/integration/cross-domain")
    assert response.status_code == 200
    assert "CrossDomain" in response.json()
