import sys
from unittest.mock import patch

import backend.inference.worker as worker_module

def test_main_cli_invokes_run(monkeypatch, tmp_path):
    # Prepare dummy args
    dummy_dir = tmp_path / "data"
    dummy_dir.mkdir()
    test_args = [
        'prog',
        '--base-dir', str(dummy_dir),
        '--action', 'translate',
        '--language', 'spanish',
        '--instruction', 'automatic',
    ]
    monkeypatch.setattr(sys, 'argv', test_args)

    run_called = False
    
    class DummyWorker:
        def __init__(self, **kwargs):
            pass
        def run(self):
            nonlocal run_called
            run_called = True

    # Patch LocalWorker to our dummy
    monkeypatch.setattr(worker_module, 'LocalWorker', DummyWorker)

    # Act
    worker_module.main()

    # Assert
    assert run_called, "LocalWorker.run() should be called by main()"