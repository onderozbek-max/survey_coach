"""Progress uses real captured screens, never an invented percentage."""
from fastapi.testclient import TestClient
from surveycoach.server import create_app


def test_reader_mode_is_disclosed_without_starting_a_read(tmp_path, monkeypatch):
    monkeypatch.setenv('SURVEYCOACH_PARTICIPANT_MODE','1')
    app = create_app(tmp_path/'progress.sqlite3')
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.get('/api/reader/mode')
        assert response.status_code == 200
        assert response.json()['participates'] is True
        assert 'test responses' in response.json()['notice']
