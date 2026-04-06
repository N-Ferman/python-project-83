from importlib import import_module
from types import SimpleNamespace

import pytest

app_module = import_module('page_analyzer.app')


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_values:
            return self.fetchall_values.pop(0)
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    app_module.app.config['SECRET_KEY'] = 'test-secret-key'

    with app_module.app.test_client() as client:
        yield client


def test_home(client):
    response = client.get('/')

    assert response.status_code == 200


def test_add_url_with_empty_value_returns_422(client):
    response = client.post('/urls', data={'url': ''})

    assert response.status_code == 422
    assert 'URL обязателен'.encode('utf-8') in response.data


def test_add_url_with_invalid_url_returns_422(client):
    response = client.post('/urls', data={'url': 'invalid-url'})

    assert response.status_code == 422
    assert 'Некорректный URL'.encode('utf-8') in response.data


def test_add_url_with_existing_url_redirects(client, monkeypatch):
    cursor = FakeCursor(fetchone_values=[(7,)])
    conn = FakeConnection(cursor)

    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)

    response = client.post('/urls', data={'url': 'https://example.com/path'}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/urls/7')
    assert conn.closed is True


def test_add_url_with_new_url_saves_and_redirects(client, monkeypatch):
    cursor = FakeCursor(fetchone_values=[None, (15,)])
    conn = FakeConnection(cursor)

    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)

    response = client.post('/urls', data={'url': 'https://example.com/path?query=1'}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/urls/15')
    assert conn.committed is True
    assert conn.closed is True


def test_get_urls_returns_page(client, monkeypatch):
    cursor = FakeCursor(
        fetchall_values=[
            [
                (1, 'https://example.com', None, None),
            ]
        ]
    )
    conn = FakeConnection(cursor)

    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)

    response = client.get('/urls')

    assert response.status_code == 200
    assert b'https://example.com' in response.data


def test_show_url_returns_page(client, monkeypatch):
    cursor = FakeCursor(
        fetchone_values=[
            (1, 'https://example.com', '2026-04-06 10:00:00'),
        ],
        fetchall_values=[
            [
                (1, 200, 'Example H1', 'Example Title', 'Example Description', '2026-04-06 10:05:00'),
            ]
        ],
    )
    conn = FakeConnection(cursor)

    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)

    response = client.get('/urls/1')

    assert response.status_code == 200
    assert b'https://example.com' in response.data


def test_check_url_saves_check_result(client, monkeypatch):
    cursor = FakeCursor(fetchone_values=[('https://example.com',)])
    conn = FakeConnection(cursor)

    monkeypatch.setattr(app_module, 'get_db_connection', lambda: conn)
    monkeypatch.setattr(
        app_module.requests,
        'get',
        lambda url, timeout=10: SimpleNamespace(
            status_code=200,
            text='<html><head><title>Test</title><meta name="description" content="Desc"></head><body><h1>H1</h1></body></html>',
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setattr(
        app_module,
        'get_seo_data',
        lambda soup: {
            'h1': 'H1',
            'title': 'Test',
            'description': 'Desc',
        },
    )

    response = client.post('/urls/1/checks', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/urls/1')
    assert conn.committed is True
    assert conn.closed is True