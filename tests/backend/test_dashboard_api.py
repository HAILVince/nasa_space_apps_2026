from fastapi.testclient import TestClient
import pytest
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_all_scenarios_and_focus_counts(client):
    scenarios = client.get('/api/research/scenarios').json()
    assert len(scenarios['scenarios']) == 5
    for scenario in scenarios['scenarios']:
        for focus in scenarios['focuses']:
            response = client.get('/api/research/dashboard', params={'scenario': scenario['id'], 'focus': focus})
            assert response.status_code == 200
            data = response.json()
            assert data['total'] == sum(data['counts'].values())
            assert all(focus == 'all' or row['focus'] == focus for row in data['investigations'])
            assert data['limitations']
            for row in data['investigations']:
                assert row['source_url'].startswith('https://www.spaceappschallenge.org/')
                assert row['oxygen_percent'] is None and not row['measurements_available']


def test_scenario_ranking_is_explained_and_deterministic(client):
    lunar = client.get('/api/research/dashboard?scenario=lunar_base').json()['investigations']
    assert lunar[0]['focus'] == 'prevention'
    assert lunar == client.get('/api/research/dashboard?scenario=lunar_base').json()['investigations']
    assert any('oxygen-enriched' in reason for reason in lunar[0]['ranking_reasons'])
    station = client.get('/api/research/dashboard?scenario=station&focus=detection').json()
    assert station['investigations'][0]['id'] == 'same'
    assert station['investigations'][0]['relevance_score'] == 100


def test_search_and_validation(client):
    assert client.get('/api/research/dashboard?q=HeLiUm').json()['investigations'][0]['id'] == 'flex'
    assert client.get('/api/research/dashboard?q=nonexistent').json()['total'] == 0
    for params in ({'scenario': 'typo'}, {'focus': 'typo'}, {'q': 'a' * 201}):
        assert client.get('/api/research/dashboard', params=params).status_code == 422


def test_comparison_preserves_order_and_unknowns(client):
    data = client.get('/api/research/compare?ids=flex,bass,flex').json()
    assert [row['id'] for row in data['investigations']] == ['flex', 'bass']
    assert all(row['pressure_kpa'] is None for row in data['investigations'])
    for ids, status in [('bass', 422), ('bass,bass', 422), ('bass,unknown', 404),
                        ('bass,saffire,same,flex,bre', 422), ('', 422)]:
        assert client.get('/api/research/compare', params={'ids': ids}).status_code == status


def test_vector_api_disabled_and_validation(client):
    assert client.get('/api/research/vector/status').json()['enabled'] is False
    assert client.get('/api/research/vector/search?q=flames').status_code == 503
    assert client.get('/api/research/vector/search?q=').status_code == 422
    assert client.get('/api/research/vector/search?q=flames&limit=26').status_code == 422


def test_vector_api_returns_passages(client, monkeypatch):
    from blackfox.db import vector_store
    class Store:
        def status(self): return {'ready': True}
        def search(self, query, limit):
            return [{'text': query, 'page': 3, 'source': 'pdf-s/test.pdf', 'similarity': .8}][:limit]
    monkeypatch.setattr(vector_store, 'get_vector_store', lambda: Store())
    data = client.get('/api/research/vector/search?q=smoke').json()
    assert data['count'] == 1 and data['results'][0]['page'] == 3
