from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_reports_ok_and_data_files():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["data"]) == {"311 월별 원본", "기상 원본", "날짜×기관 병합", "날짜×이슈 병합"}


def test_api_docs_available():
    assert client.get("/docs").status_code == 200
