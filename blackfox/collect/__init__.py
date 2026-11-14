"""Collector for the research knowledge base (text only, no pictures).

  python -m blackfox.collect harvest    download records from the public sources into a staging folder
  python -m blackfox.collect build      classify (Moon / Mars / 0 g + topic), sort and write the JSON database
  python -m blackfox.collect fulltext   optional: download the full report/article texts (server side)
  python -m blackfox.collect all        harvest + build

See blackfox/db/README.md for the database format and how the agent reads it.
"""
