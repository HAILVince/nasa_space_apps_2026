# Bundled embedding model

`all-MiniLM-L6-v2-int8/` is the model the vector database (`blackfox/db/vector_store.py`) uses to
turn text into 384-number vectors. It is shipped in the repository so the server never has to
download anything: the first download from Hugging Face failed on the VPS and left the vector
index unbuilt.

| | |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` (English, 256-token inputs), Apache-2.0 |
| Files | ONNX export with int8 weights (`onnx/model_quantized.onnx` from `Xenova/all-MiniLM-L6-v2`), tokenizer files unchanged |
| Size | 23 MB (the full-precision model is 90 MB) |
| Quality | embeddings point the same way as the full model: cosine similarity 0.989 to 0.993 on test sentences |
| SHA-256 of `model.onnx` | `afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1` |

Changing the model (or this folder's files) changes the index fingerprint, so the next start
rebuilds the vector index by itself. `BLACKFOX_EMBEDDING_MODEL_DIR` points the store at another
folder; if the folder is missing the store falls back to downloading the full model.
