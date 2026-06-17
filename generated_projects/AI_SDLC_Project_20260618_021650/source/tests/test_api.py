from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_record():
    response = client.post("/api/records", json={"name": "sample"})
    assert response.status_code == 200
    assert response.json()["status"] == "created"
