import os
import sys
import pytest
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.stt import router as stt_router

test_app = FastAPI(title="STT Test App")
test_app.include_router(stt_router, prefix="/api/v1")
test_app.include_router(stt_router, prefix="/api")

client = TestClient(test_app)

def test_stt_providers_endpoint():
    response = client.get("/api/v1/stt/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "supported_languages" in data
    assert "kn-IN" in data["supported_languages"]
    assert "hi-IN" in data["supported_languages"]
    assert "ta-IN" in data["supported_languages"]
    assert "te-IN" in data["supported_languages"]

def test_stt_transcribe_endpoint_v1():
    fake_audio_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    files = {"audio": ("sample_sos.wav", io.BytesIO(fake_audio_content), "audio/wav")}
    data = {"language": "kn-IN"}
    
    response = client.post("/api/v1/stt/transcribe", files=files, data=data)
    assert response.status_code == 200
    res = response.json()
    assert "transcript" in res
    assert res["language"] == "kn-IN"
    assert "confidence" in res
    assert "provider" in res
    assert len(res["transcript"]) > 0

def test_stt_transcribe_endpoint_legacy_prefix():
    fake_audio_content = b"FAKE_AUDIO_SAMPLE_DATA_EN_EMERGENCY_REQUEST_BYTES_12345"
    files = {"audio": ("sos.m4a", io.BytesIO(fake_audio_content), "audio/m4a")}
    data = {"language": "en"}
    
    response = client.post("/api/stt/transcribe", files=files, data=data)
    assert response.status_code == 200
    res = response.json()
    assert "transcript" in res
    assert res["language"] == "en-IN"
    assert res["confidence"] > 0.5
