import pytest
from unittest.mock import MagicMock, patch

from inference.worker import LocalWorker
from inference.processors.factory import ProcessorFactory

class DummyProcessor:
    def __init__(self):
        self.process = MagicMock()

@pytest.fixture(autouse=True)
def patch_factory():
    dummy = DummyProcessor()
    with patch.object(ProcessorFactory, 'get_processor', return_value=dummy):
        yield dummy

def test_local_worker_processes_folder(tmp_path, patch_factory, capsys):
    # Arrange: create dummy folder
    base = tmp_path / "session1"
    base.mkdir()

    worker = LocalWorker(
        base_dir=str(base),
        action='transcribe',
        language='english',
        instruction=None,
        translationModel=None,
        glossingModel=None,
        job=None
    )

    # Act
    worker.run()

    # Assert: dummy.process called on the base dir
    patch_factory.process.assert_called_once_with(str(base))
    # Check console output contains start and done messages
    captured = capsys.readouterr().out
    assert "Starting job local_job" in captured
    assert "Processed folder" in captured
    assert "[DONE ALL]" in captured