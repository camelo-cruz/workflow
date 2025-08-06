import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app import app
from inference.processors.factory import ProcessorFactory

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def fake_processor():
    dummy = MagicMock()
    dummy.process.return_value = None
    with patch.object(ProcessorFactory, 'get_processor', return_value=dummy):
        yield dummy

def test_transcribe_endpoint(client, tmp_path, fake_processor):
    # Arrange: create uploaded file
    folder = tmp_path / "upload"
    folder.mkdir()
    # Simulate posting folder path or files depending on your API design
    response = client.post(
        "/process",
        json={
            "base_dir": str(folder),
            "action": "transcribe",
            "language": "english",
            "instruction": null
        }
    )
    assert response.status_code == 200
    fake_processor.process.assert_called_once_with(str(folder))
    assert response.json()["status"] == "done"