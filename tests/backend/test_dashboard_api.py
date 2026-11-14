from fastapi.testclient import TestClient
import pytest
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_dashboard_lists_all_investigations_with_real_conditions(client):
    from flame.data import get_investigations, get_envelopes
    data = client.get('/api/research/dashboard?scenario=lunar_base').json()
    rows = {r['id']: r for r in data['investigations']}
    assert data['total'] == len(rows) == len(get_investigations()) == 24
    assert set(rows) == {i.accession for i in get_investigations()}
    assert sum(data['counts'].values()) == data['total']
    for accession, row in rows.items():
        envs = get_envelopes(accession)
        assert row['measurements_available'] == bool(envs)
        for name, attr in [('oxygen_percent', 'o2_pct'), ('pressure_kpa', 'pressure_kpa'), ('airflow_m_s', 'flow_mps')]:
            ranges = [getattr(e, attr) for e in envs if getattr(e, attr) is not None]
            expected = [min(x[0] for x in ranges), max(x[1] for x in ranges)] if ranges else None
            assert row[name] == expected
        if not envs:
            assert 'Modeling study' in row['conditions_note']
    assert rows['PSI-25']['oxygen_percent'] == [13.5, 22.2]
    assert rows['PSI-22']['oxygen_percent'] is None
    assert rows['PSI-60']['pressure_kpa'] is None


def test_scenario_ranking_and_multitopic_filters_are_explained(client):
    scenarios = client.get('/api/research/scenarios').json()
    assert len(scenarios['scenarios']) == 5
    for scenario in scenarios['scenarios']:
        for focus in scenarios['focuses']:
            data = client.get('/api/research/dashboard', params={'scenario': scenario['id'], 'focus': focus}).json()
            assert data['total'] == sum(data['counts'].values())
            assert all(focus == 'all' or focus in row['focuses'] for row in data['investigations'])
            assert all(row['ranking_reasons'] and row['relevance_score'] in (50, 70, 80, 100) for row in data['investigations'])
    lunar = client.get('/api/research/dashboard?scenario=lunar_base').json()['investigations']
    assert lunar == client.get('/api/research/dashboard?scenario=lunar_base').json()['investigations']
    assert lunar[0]['fuel_phase'] == 'solid' and any('+20' in r for r in lunar[0]['ranking_reasons'])
    suppression = client.get('/api/research/dashboard?focus=suppression').json()['investigations']
    assert 'PSI-25' in {r['id'] for r in suppression}  # BASS-II has multiple topics


def test_search_and_validation(client):
    assert any(r['id'] == 'PSI-107' for r in client.get('/api/research/dashboard?q=SPICE').json()['investigations'])
    assert client.get('/api/research/dashboard?q=nonexistent').json()['total'] == 0
    for params in ({'scenario': 'typo'}, {'focus': 'typo'}, {'q': 'a' * 201}):
        assert client.get('/api/research/dashboard', params=params).status_code == 422


def test_comparison_preserves_order_and_legacy_aliases(client):
    data = client.get('/api/research/compare?ids=flex,bass,flex').json()
    assert [row['id'] for row in data['investigations']] == ['flex', 'bass']
    assert [row['accession'] for row in data['investigations']] == ['PSI-69', 'PSI-26']
    assert all(row['pressure_kpa'] is not None for row in data['investigations'])
    for ids, status in [('bass', 422), ('bass,bass', 422), ('bass,unknown', 404),
                        ('bass,saffire,same,flex,bre', 422), ('', 422)]:
        assert client.get('/api/research/compare', params={'ids': ids}).status_code == status
    for alias in ['bass', 'saffire', 'same', 'flex', 'bre', 'cfi_g']:
        assert client.get('/api/research/compare', params={'ids': f'{alias},PSI-47'}).status_code == 200


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
