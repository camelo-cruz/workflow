import pytest
from fastapi.testclient import TestClient

from app import app

@pytest.fixture
def client():
    return TestClient(app)

def test_transcribe_endpoint(client, tmp_path):
    # Arrange: create uploaded file
    folder = tmp_path / "upload"
    folder.mkdir()
    # Simulate posting folder path or files depending on your API design
    response = client.post(
        "/api/inference/process",
        data={
            "base_dir": str(folder),
            "access_token": "fake-token",
            "action": "transcribe",
            "language": "german",
            "instruction": "automatic",
        }
    )
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data