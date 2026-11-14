"""Local, rebuildable dense-vector index for source PDFs and curated JSON passages."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def chunks(text: str, size: int = 1200, overlap: int = 200):
    text = " ".join(text.split())
    for start in range(0, len(text), size - overlap):
        yield text[start:start + size]
        if start + size >= len(text):
            break


class VectorStore:
    def __init__(self, root: Path, data_dir: Path, embedder=None):
        self.root, self.data_dir = Path(root), Path(data_dir)
        self.path = self.data_dir / "research_vectors.sqlite"
        self.model_name = MODEL
        self._embedder = embedder
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()
        self.building = False
        self.blocked = False
        self.error = ""
        self.extraction_errors = []
        self.pdf_pages = 0

    def _files(self):
        return sorted([*self.root.glob("pdf-s/*.pdf"), *self.root.glob("curated/*.json")])

    def signature(self):
        h = hashlib.sha256((self.model_name + ":page-chunks-v1:1200:200").encode())
        for path in self._files():
            h.update(str(path.relative_to(self.root)).encode())
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
        return h.hexdigest()

    def _model(self):
        if self._embedder is None:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self.model_name,
                                          cache_dir=str(self.data_dir / "embedding_models"), threads=2)
        return self._embedder

    def _embed(self, texts):
        import numpy as np
        with self._model_lock:
            vectors = [np.asarray(v, dtype=np.float32) for v in self._model().embed(texts)]
        if len(vectors) != len(texts):
            raise ValueError("Embedding count differs from passage count")
        normalized = []
        for v in vectors:
            norm = float(np.linalg.norm(v))
            if v.ndim != 1 or norm == 0 or not np.isfinite(v).all():
                raise ValueError("Invalid embedding vector")
            normalized.append(v / norm)
        return normalized

    def _passages(self):
        from pypdf import PdfReader
        for path in self._files():
            relative = str(path.relative_to(self.root))
            if path.suffix == '.pdf':
                reader = PdfReader(path)
                title = str((reader.metadata or {}).get('/Title') or path.stem.replace('_', ' '))
                self.pdf_pages += len(reader.pages)
                for page_number, page in enumerate(reader.pages, 1):
                    try:
                        page_text = page.extract_text() or ''
                    except Exception as exc:
                        self.extraction_errors.append(f"{relative}:p{page_number}: {type(exc).__name__}")
                        continue
                    for part, text in enumerate(chunks(page_text)):
                        yield {"id": f"{relative}:p{page_number}:{part}", "title": title,
                               "source": relative, "page": page_number, "text": text,
                               "evidence_type": "source_pdf", "gravity": [], "topic": "combustion_fire"}
            else:
                for record in json.loads(path.read_text())["records"]:
                    slug = record.get('id') or record.get('slug') or record['title']
                    text = ' '.join(str(record.get(k) or '') for k in ('title', 'summary', 'details'))
                    for part, passage in enumerate(chunks(text)):
                        yield {"id": f"{relative}:{slug}:{part}", "slug": slug,
                               "title": record['title'], "source": relative, "page": None,
                               "text": passage, "evidence_type": "curated_summary",
                               "gravity": record.get('gravity', []), "topic": record.get('topic', '')}

    def status(self):
        out = {"enabled": True, "ready": False, "building": self.building,
               "model": self.model_name, "error": self.error,
               "scope": "source PDFs and curated summaries; collected metadata uses keyword search"}
        if self.path.exists():
            try:
                with closing(sqlite3.connect(self.path)) as c:
                    meta = dict(c.execute('SELECT key, value FROM meta'))
                out.update(ready=meta['model'] == self.model_name, passages=int(meta['passages']),
                           documents=int(meta['documents']), empty_pages=int(meta['empty_pages']),
                           signature=meta['signature'],
                           extraction_errors=json.loads(meta.get('extraction_errors', '[]')))
            except (sqlite3.Error, KeyError, ValueError) as exc:
                out['error'] = str(exc)
        if self.blocked:
            out['ready'] = False
        return out

    def build(self):
        """Build atomically; on failure retain the last complete index and report the error."""
        if not self._lock.acquire(blocking=False):
            return
        self.building = True
        self.error = ''
        self.extraction_errors = []
        self.pdf_pages = 0
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f'.{os.getpid()}.tmp')
        try:
            # App and MCP processes may both start; serialize publication across processes.
            import fcntl
            with self.path.with_suffix('.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                signature = self.signature()
                if self.status().get('signature') == signature and self.status()['ready']:
                    return
                temporary.unlink(missing_ok=True)
                with closing(sqlite3.connect(temporary)) as c, c:
                    c.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);'
                                    'CREATE TABLE passages(id TEXT PRIMARY KEY, metadata TEXT, vector BLOB);')
                    batch, count, sources, pages_with_text = [], 0, set(), set()
                    dimension = None
                    def flush():
                        nonlocal count, dimension
                        for record, vector in zip(batch, self._embed([r['text'] for r in batch])):
                            if dimension is not None and dimension != len(vector):
                                raise ValueError('Inconsistent vector dimensions')
                            dimension = len(vector)
                            c.execute('INSERT INTO passages VALUES (?,?,?)',
                                      (record['id'], json.dumps(record), vector.tobytes()))
                            count += 1
                            sources.add(record['source'])
                            if record['page'] is not None:
                                pages_with_text.add((record['source'], record['page']))
                        batch.clear()
                    for record in self._passages():
                        batch.append(record)
                        if len(batch) == 4:
                            flush()
                    if batch:
                        flush()
                    if not count:
                        raise ValueError('No extractable passages found')
                    metadata = {'signature': signature, 'model': self.model_name,
                                'passages': count, 'documents': len(sources),
                                'empty_pages': self.pdf_pages - len(pages_with_text) - len(self.extraction_errors),
                                'extraction_errors': json.dumps(self.extraction_errors), 'dimensions': dimension}
                    c.executemany('INSERT INTO meta VALUES (?,?)', [(k, str(v)) for k, v in metadata.items()])
                os.replace(temporary, self.path)
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            temporary.unlink(missing_ok=True)
        finally:
            self.building = False
            self._lock.release()

    def search(self, query: str, limit: int = 6, gravity: str | None = None,
               topic: str | None = None):
        """Exact cosine search, streamed in batches; similarity is not scientific confidence."""
        import numpy as np
        if not query.strip() or not self.status()['ready']:
            return []
        q = self._embed([query[:2000]])[0]
        hits = []
        with closing(sqlite3.connect(self.path)) as c:
            dimension = int(c.execute("SELECT value FROM meta WHERE key='dimensions'").fetchone()[0])
            if len(q) != dimension:
                raise ValueError('Query embedding does not match index dimensions')
            rows = c.execute('SELECT metadata, vector FROM passages')
            while batch := rows.fetchmany(256):
                records = [json.loads(row[0]) for row in batch]
                matrix = np.stack([np.frombuffer(row[1], dtype=np.float32) for row in batch])
                for record, score in zip(records, matrix @ q):
                    # Do not infer experiment gravity from a paper's filename or its microgravity topic.
                    if gravity and gravity not in record['gravity']:
                        continue
                    if topic and record['topic'] != topic:
                        continue
                    hits.append({**record, 'similarity': round(float(score), 6)})
                hits = sorted(hits, key=lambda r: (-r['similarity'], r['id']))[:max(1, min(limit, 25))]
        return hits


_store = None


def get_vector_store():
    global _store
    from ..settings import get_settings
    settings = get_settings()
    if not settings.vector_enabled:
        return None
    if _store is None:
        _store = VectorStore(settings.knowledge_dir, settings.data_dir)
    return _store


def warm_vectors():
    store = get_vector_store()
    if store:
        try:
            memory_cap = Path('/sys/fs/cgroup/memory.max').read_text().strip()
            if memory_cap.isdigit() and int(memory_cap) < 768 * 1024 * 1024:
                store.blocked = True
                store.error = 'Memory cap is below 768 MB; install the updated 1 GB blackfox.service unit or disable vectors.'
                return
        except OSError:
            pass
        threading.Thread(target=store.build, name='research-vectors', daemon=True).start()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'status', 'search'])
    parser.add_argument('query', nargs='?', default='')
    args = parser.parse_args()
    store = get_vector_store()
    if store is None:
        raise SystemExit('Vector search is disabled')
    if args.action == 'build':
        store.build()
    print(json.dumps(store.search(args.query) if args.action == 'search' else store.status(), indent=2))
    if store.error:
        raise SystemExit(1)
