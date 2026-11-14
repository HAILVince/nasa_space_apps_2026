"""Every test run gets its own empty data dir and no real AI key, so tests never touch
production data or call the AI API."""

import os
import tempfile

os.environ["BLACKFOX_DATA_DIR"] = tempfile.mkdtemp(prefix="bfx-test-")
os.environ["BLACKFOX_AI_KEY"] = ""
os.environ["BLACKFOX_AI_CONFIG"] = ""      # don't pick the key up from the VPS's AI API config
os.environ["BLACKFOX_AGENCY_DIR"] = ""     # ...nor run AI_agency.py in-process
os.environ["BLACKFOX_TOOL_TRANSPORT"] = "inproc"

# Tests never download embedding models; vector tests inject a deterministic embedder.
os.environ["BLACKFOX_VECTOR_ENABLED"] = "false"
