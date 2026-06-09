"""Query the unified FTS5 index, optionally filtered by source."""
from db import SOURCE_PREFIXES, source_of


def _source_clause(source):
    """Return (sql_fragment, extra_params) for an optional source filter.
    Prefixes are hardcoded constants, so the 'note' clause interpolates them safely."""
    if not source:
        return "", []
    if source == "note":
        clause = "".join(f" AND path NOT LIKE '{p}%'" for p in SOURCE_PREFIXES.values())
        return clause, []
    prefix = SOURCE_PREFIXES.get(source)
    if not prefix:
        return "", []  # unknown source → no filter
    return " AND path LIKE ?", [prefix + "%"]


def search_index(conn, q, source=None, limit=20):
    clause, extra = _source_clause(source)
    sql = f"""
        SELECT path, title,
               snippet(notes_fts, 2, '<mark>', '</mark>', '…', 24) AS snippet,
               bm25(notes_fts) AS score
        FROM notes_fts
        WHERE notes_fts MATCH ?{clause}
        ORDER BY score
        LIMIT ?
    """
    rows = conn.execute(sql, [q, *extra, limit]).fetchall()
    return [
        {
            "path": r["path"],
            "title": r["title"],
            "snippet": r["snippet"],
            # bm25() is negative (more negative = better). Flip so higher = more relevant.
            "score": round(-r["score"], 4),
            "source": source_of(r["path"]),
        }
        for r in rows
    ]
