# Scenario dashboard implementation

> **Status (14 Nov 2026).** Steps 1-3 below are done (step 1 now serves all 24 PSI investigations instead of curated
> families), and the data milestone at the end has been reached:
> the dashboard ranks all 24 PSI investigations (`topic-relevance-v2`), takes oxygen, pressure and airflow
> ranges from the `flame/data` envelopes (19 of 24 have an envelope; the other 5 are computational studies),
> and 13 investigations have cleaned raw test tables (1,755 rows) behind `GET /api/flame/sweep`. Still not
> done: quantitative plots of the measurements and validated modelling. The numbers in the README paragraph
> are checked against the live endpoints by `tests/backend/test_readme_numbers.py`.

1. Expose curated investigation-family metadata from the NASA challenge brief with source
   attribution and explicit unknown experimental conditions.
2. Rank that catalog with a deterministic, explained topic relevance method per mission
   and prevention, detection or suppression focus. Keep partial-gravity gaps visible.
3. Offer scenario selection, text search and side-by-side investigation comparison in the
   existing plain HTML frontend. Preserve the design agent and its simulation interfaces.
4. Verify validation, ranking, search, counts, comparison and existing workspace tests
   before pushing the integrated change to main.

Next data milestone: ingest original PSI datasets with dataset-level citations, units,
measurement provenance and supported condition ranges. Only then add quantitative plots
and validated modeling. Any future AI interpretation should cite that evidence and expose
uncertainty. Current summaries and rankings run without an AI service.
