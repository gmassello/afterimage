import uuid

from services.conftest import localstack
from services.memory import runs


def exercise_backend(run_dir):
    assert runs.read(run_dir, "state.json") is None
    runs.write(run_dir, "state.json", {"status": "completed"})
    assert runs.read(run_dir, "state.json") == {"status": "completed"}
    runs.write(run_dir, "pending.json", {"run_id": run_dir.name})
    runs.write(run_dir.parent / "other0runab", "state.json", {"status": "completed"})
    assert runs.pending(run_dir.parent) == [{"run_id": run_dir.name}]
    runs.delete(run_dir, "pending.json")
    assert runs.pending(run_dir.parent) == []
    assert runs.read(run_dir, "pending.json") is None
    runs.delete(run_dir, "pending.json")


def test_disk_backend(tmp_path):
    exercise_backend(tmp_path / uuid.uuid4().hex[:12])


@localstack
def test_s3_backend(tmp_path, monkeypatch):
    from services.memory import images

    images.ensure_bucket()
    monkeypatch.setenv("AFTERIMAGE_RUNS_S3", "1")
    exercise_backend(tmp_path / uuid.uuid4().hex[:12])
