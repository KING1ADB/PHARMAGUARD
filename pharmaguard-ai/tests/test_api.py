from fastapi.testclient import TestClient
from app.main import app
from app.database.database import init_db

init_db()
client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ONLINE"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


def test_get_inventory():
    response = client.get("/inventory")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_search_inventory():
    response = client.get("/inventory/search?q=Coartem")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "Coartem" in data[0]["name"]


def test_agent_cycle_trigger():
    response = client.post("/agent/cycle")
    assert response.status_code == 200
    data = response.json()
    assert "cycle_id" in data
    assert "briefing_text" in data


def test_agent_query_endpoint():
    response = client.post("/agent/query", json={"query": "What are the expiring medicines?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 10


def test_agent_briefing_endpoint():
    response = client.get("/agent/briefing")
    assert response.status_code == 200
    data = response.json()
    assert "briefing_markdown" in data
    assert "PHARMAGUARD" in data["briefing_markdown"]
