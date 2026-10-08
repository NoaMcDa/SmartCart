Test fixtures for the Wikidata parser (services/ingest/tests/test_geocode_sources.py).

These files follow the documented SPARQL JSON result format of query.wikidata.org. They were
written by hand, NOT recorded: the build box has no route to Wikidata. The property ids (P88888,
P99999), the Q-ids of the odd rows and the coordinates are placeholders for testing the parser. Replace
them with a recorded response when one is available (the "Geocode stores" workflow log prints
the property id it found and the query result's row count).
