import json
import numpy as np
import pytest
from pypdf import PdfWriter
from blackfox.db.vector_store import VectorStore, chunks


class Embedder:
    def embed(self, texts):
        for text in texts:
            yield np.array([1 + text.lower().count('flame'), 1 + text.lower().count('dust'), 1], dtype=np.float32)


@pytest.fixture
def store(tmp_path):
    root = tmp_path / 'knowledge'
    (root / 'curated').mkdir(parents=True)
    (root / 'pdf-s').mkdir()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(root / 'pdf-s' / 'blank.pdf')
    records = [dict(id='flame', title='Flame study', summary='flame ' * 50, gravity=['zero_g'], topic='combustion_fire'),
               dict(id='dust', title='Dust study', summary='dust ' * 50, gravity=['moon'], topic='dust')]
    (root / 'curated' / 'research.json').write_text(json.dumps({'records': records}))
    return VectorStore(root, tmp_path / 'data', Embedder())


def test_dense_search_persistence_filters_and_citations(store):
    assert not store.status()['ready']
    store.build()
    assert store.status()['ready'] and store.status()['passages'] == 2
    assert store.status()['empty_pages'] == 1
    result = store.search('flame')[0]
    assert result['slug'] == 'flame' and result['source'] == 'curated/research.json'
    assert -1 <= result['similarity'] <= 1
    assert store.search('flame', gravity='moon')[0]['slug'] == 'dust'
    assert store.search('flame', topic='absent') == []
    assert store.search(' ') == []
    reloaded = VectorStore(store.root, store.data_dir, Embedder())
    assert reloaded.search('flame') == store.search('flame')
    before = store.path.stat().st_mtime_ns
    reloaded.build()
    assert store.path.stat().st_mtime_ns == before


def test_changed_sources_rebuild_and_failure_preserves_index(store):
    store.build()
    source = store.root / 'curated' / 'research.json'
    data = json.loads(source.read_text())
    data['records'].append(dict(id='new', title='New', summary='flame flame', gravity=['moon']))
    source.write_text(json.dumps(data))
    store.build()
    assert store.status()['passages'] == 3
    source.write_text('invalid JSON')
    store.build()
    assert store.error and store.status()['ready']
    assert store.status()['passages'] == 3 and store.search('flame')


def test_invalid_vectors_do_not_publish(store):
    class BadEmbedder:
        def embed(self, texts):
            return [np.array([np.nan]) for _ in texts]
    store._embedder = BadEmbedder()
    store.build()
    assert 'Invalid embedding' in store.error and not store.path.exists()


def test_pdf_page_chunks_preserve_source_and_page(store, monkeypatch):
    import pypdf
    class Page:
        def extract_text(self):
            return 'flame test ' * 200
    class Reader:
        metadata = {'/Title': 'NASA experiment'}
        pages = [Page(), Page()]
        def __init__(self, path): pass
    monkeypatch.setattr(pypdf, 'PdfReader', Reader)
    store.build()
    hits = [r for r in store.search('flame', 25) if r['page']]
    assert {r['page'] for r in hits} == {1, 2}
    assert all(r['source'] == 'pdf-s/blank.pdf' and r['title'] == 'NASA experiment' for r in hits)
    assert store.status()['empty_pages'] == 0


def test_chunks_overlap_and_finish():
    parts = list(chunks('x' * 2300))
    assert len(parts) == 3 and parts[0][-200:] == parts[1][:200]
    assert list(chunks('')) == []


def test_unreadable_pdf_page_is_reported(store, monkeypatch):
    import pypdf
    class Page:
        def extract_text(self):
            raise ValueError('unreadable stream')
    class Reader:
        metadata = {}
        pages = [Page()]
        def __init__(self, path): pass
    monkeypatch.setattr(pypdf, 'PdfReader', Reader)
    store.build()
    status = store.status()
    assert status['ready'] and status['empty_pages'] == 0
    assert status['extraction_errors'] == ['pdf-s/blank.pdf:p1: ValueError']


def test_low_memory_service_retains_keyword_fallback(store, monkeypatch):
    from pathlib import Path
    from blackfox.db import vector_store
    read_text = Path.read_text
    monkeypatch.setattr(vector_store, 'get_vector_store', lambda: store)
    def capped(path, *args, **kwargs):
        if str(path) == '/sys/fs/cgroup/memory.max':
            return str(400 * 1024 * 1024)
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', capped)
    vector_store.warm_vectors()
    assert not store.status()['ready'] and not store.building
    assert 'Memory cap' in store.status()['error']


def test_incremental_build_reuses_unchanged_embeddings(store):
    store.build()
    class CountingEmbedder(Embedder):
        seen = []
        def embed(self, texts):
            self.seen.extend(texts)
            return super().embed(texts)
    embedder = CountingEmbedder()
    store._embedder = embedder
    source = store.root / 'curated' / 'research.json'
    data = json.loads(source.read_text())
    data['records'].append(dict(id='added', title='Added', summary='flame detection', gravity=['zero_g']))
    source.write_text(json.dumps(data))
    store.build()
    assert store.status()['passages'] == 3
    assert len(embedder.seen) == 1 and 'Added' in embedder.seen[0]


def test_bundled_model_loads_offline_and_ranks_by_meaning(tmp_path):
    """The real model shipped in blackfox/db/models: no network, 384 numbers per text, related texts closer."""
    import numpy as np
    store = VectorStore(tmp_path / 'knowledge', tmp_path / 'data')
    assert store.model_dir is not None and (store.model_dir / 'model.onnx').is_file()
    assert store.status()['model_source'].startswith('bundled')
    flame, dust, spread = store._embed(['A candle flame in microgravity is spherical and dim.',
                                        'Lunar regolith dust sticks to spacesuits and seals.',
                                        'Flames spread more slowly in weightlessness.'])
    assert flame.shape == (384,) and abs(float(np.linalg.norm(flame)) - 1) < 1e-5
    assert float(flame @ spread) > float(flame @ dust) + 0.15
    (tmp_path / 'other').mkdir()
    (tmp_path / 'other' / 'model.onnx').write_bytes(b'x')
    other = VectorStore(tmp_path / 'knowledge', tmp_path / 'data')
    other.model_dir = tmp_path / 'other'
    assert other.signature() != store.signature()           # another model file = rebuild the vectors
