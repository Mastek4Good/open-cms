import io
import tempfile
from pathlib import Path

import pytest

from app.services.transcription_client import TranscriptionClient
from tests.conftest import csrf_token, register


@pytest.fixture()
def worker(client):
    register(client, "worker@example.org")  # registering signs the user in
    return client


@pytest.fixture()
def seen_paths(monkeypatch):
    """Record the temp file path handed to the transcription client."""
    paths = []

    def fake_transcribe(self, path):
        paths.append(path)
        return "hello world"

    monkeypatch.setattr(TranscriptionClient, "transcribe", fake_transcribe)
    return paths


def upload(client, filename):
    return client.post(
        "/transcribe",
        data={"audio": (io.BytesIO(b"fake audio"), filename)},
        headers={"X-CSRFToken": csrf_token(client, "/cases/new")},
        content_type="multipart/form-data",
    )


@pytest.mark.parametrize("filename", ["voice_note.webm", "clip.OGG", "a.mp3", "a.wav", "a.m4a"])
def test_whitelisted_audio_is_transcribed(worker, seen_paths, filename):
    response = upload(worker, filename)

    assert response.status_code == 200
    assert response.get_json() == {"text": "hello world"}
    assert Path(seen_paths[0]).suffix == "." + filename.rsplit(".", 1)[-1].lower()


def test_name_without_extension_defaults_to_webm(worker, seen_paths):
    assert upload(worker, "recording").status_code == 200
    assert seen_paths[0].endswith(".webm")


@pytest.mark.parametrize(
    "filename",
    ["malware.exe", "page.html", "x.py", "a./../../etc/passwd", "audio.webm/../x", "a.we bm"],
)
def test_other_extensions_are_rejected_before_anything_is_written(worker, seen_paths, filename):
    response = upload(worker, filename)

    assert response.status_code == 400
    assert response.get_json() == {"error": "Unsupported audio file type"}
    assert seen_paths == []


def test_temp_file_always_lands_in_the_temp_directory(worker, seen_paths):
    upload(worker, "voice_note.webm")

    assert Path(seen_paths[0]).parent == Path(tempfile.gettempdir())


def test_requires_login(client):
    response = client.post(
        "/transcribe",
        data={"audio": (io.BytesIO(b"x"), "a.webm")},
        headers={"X-CSRFToken": csrf_token(client, "/login")},
        content_type="multipart/form-data",
    )
    assert response.status_code in (302, 401)
