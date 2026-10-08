import re
from datetime import datetime


# ---------------------------------------------------------------------------
# String-literal masking
# ---------------------------------------------------------------------------
# Values like 'Smith, John' or 'O''Brien' used to break the script because the
# SET clause was split on every comma and the query splitter / keyword finder
# did not know they were inside quotes. Now every '...' literal is swapped for
# a placeholder before parsing and put back at the very end, so commas, quotes,
# keywords (update/delete/from/where) and "--" inside strings are left alone.

_PLACEHOLDER_RE = re.compile(r"__STRLIT_(\d+)__")


def mask_literals_and_strip_comments(sql: str):
    """Single pass: strip -- and /* */ comments, replace '...' literals with
    placeholders. Handles '' escapes inside literals. Returns (masked_sql,
    literals, unterminated_flag)."""
    literals = []
    out = []
    i, n = 0, len(sql)
    unterminated = False
    while i < n:
        ch = sql[i]
        if ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":  # escaped quote ''
                        j += 2
                        continue
                    break
                j += 1
            if j >= n:
                unterminated = True
            literal = sql[i:j + 1]
            out.append(f"__STRLIT_{len(literals)}__")
            literals.append(literal)
            i = j + 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            if j == -1:
                break
            i = j  # keep the newline
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j == -1:
                break
            out.append(" ")
            i = j + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out), literals, unterminated


def restore_literals(text: str, literals) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: literals[int(m.group(1))], text)


def split_top_level_commas(s: str):
    """Split on commas that are not inside parentheses (any nesting depth)."""
    parts, depth, buf = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------------------

def extract_alias_map(from_block: str):
    alias_map = {}
    f = re.sub(r"\s+", " ", from_block)
    parts = re.split(r"\bjoin\b", f, flags=re.IGNORECASE)
    for p in parts:
        m = re.search(r"([A-Za-z0-9_#]+)\s+(?:as\s+)?([A-Za-z0-9_#]+)", p, flags=re.IGNORECASE)
        if m:
            tbl, als = m.groups()
            alias_map[als.lower()] = tbl
        else:
            m2 = re.match(r"^\s*([A-Za-z0-9_#]+)\s*$", p.strip())
            if m2:
                tbl = m2.group(1)
                alias_map[tbl.lower()] = tbl
    return alias_map


def find_top_level_kw(sql: str, word: str, start: int = 0) -> int:
    sql_lower = sql.lower()
    word = word.lower()
    wlen = len(word)
    depth = 0
    n = len(sql)
    i = start
    while i <= n - wlen:
        ch = sql[i]
        if ch == '(':
            depth += 1
            i += 1
            continue
        elif ch == ')':
            depth -= 1
            i += 1
            continue
        if depth == 0 and sql_lower[i:i + wlen] == word:
            before_ok = (i == 0) or sql[i - 1].isspace()
            after_ok = (i + wlen == n) or sql[i + wlen].isspace()
            if before_ok and after_ok:
                return i
        i += 1
    return -1


def get_pk_col(table_name: str) -> str:
    return "hmyperson" if table_name.lower() in ("tenant", "vendor") else "hmy"


def uses_pk(where_part: str, pk_col: str) -> bool:
    """True if the (masked) WHERE clause references the primary key column."""
    return bool(re.search(rf"\b{pk_col}\b", where_part, re.IGNORECASE))


_WHERE_KW = {"and", "or", "not", "in", "is", "like", "between", "null",
             "exists", "select", "from", "where", "case", "when", "then", "else", "end"}

_WHERE_COL_RE = re.compile(
    r"(?<![\w.#])([A-Za-z_#][\w#]*(?:\.[A-Za-z_#][\w#]*)?)\s*"
    r"(?:<>|!=|<=|>=|=|<|>|\bnot\s+in\b|\bin\b|\bnot\s+like\b|\blike\b|\bbetween\b|\bis\b)",
    re.IGNORECASE,
)


def extract_where_columns(where_part: str):
    """Columns that are compared against something in the (masked) WHERE clause,
    in order of appearance, without duplicates."""
    cols, seen = [], set()
    for m in _WHERE_COL_RE.finditer(where_part):
        c = m.group(1)
        if c.lower() in _WHERE_KW or c.startswith("__STRLIT_"):
            continue
        if c.lower() not in seen:
            seen.add(c.lower())
            cols.append(c)
    return cols


def _mask_and_split(content: str):
    content, literals, unterminated = mask_literals_and_strip_comments(content)
    content = re.sub(r"[ \t]+", " ", content).strip()
    queries = re.split(r"(?i)(?=(?:\bupdate\b|\bdelete\b))", content)
    queries = [q.strip() for q in queries if q.strip()]
    return queries, literals, unterminated


def _parse_update(q_clean: str, warnings: list):
    """Parse one masked UPDATE. Returns dict(table_name, set_part, full_from,
    where_part) or None if the syntax isn't recognised."""
    m = re.match(r"update\s+([A-Za-z0-9_#]+)\s+set\s+", q_clean, re.IGNORECASE)
    if not m:
        return None

    alias = m.group(1)
    set_start = m.end()

    from_idx = find_top_level_kw(q_clean, "from", set_start)
    where_idx = find_top_level_kw(q_clean, "where", set_start)

    if from_idx != -1 and (where_idx == -1 or from_idx < where_idx):
        set_part = q_clean[set_start:from_idx].strip()
        if where_idx != -1:
            from_part = q_clean[from_idx + len("from"):where_idx].strip()
            where_part = q_clean[where_idx + len("where"):].strip()
        else:
            from_part = q_clean[from_idx + len("from"):].strip()
            where_part = "1=1"
        alias_map = extract_alias_map(from_part)
        table_name = alias_map.get(alias.lower())
        if not table_name:
            warnings.append(f"⚠️ Alias '{alias}' not found in FROM clause. Defaulting to alias name.")
            table_name = alias
        full_from = "from " + from_part
    else:
        table_name = alias
        if where_idx != -1:
            set_part = q_clean[set_start:where_idx].strip()
            where_part = q_clean[where_idx + len("where"):].strip()
        else:
            set_part = q_clean[set_start:].strip()
            where_part = "1=1"
        full_from = f"from {table_name}"

    return {"table_name": table_name, "set_part": set_part,
            "full_from": full_from, "where_part": where_part}


def find_non_pk_updates(content: str):
    """Tables whose UPDATE statements don't use hmy/hmyperson in the WHERE clause.

    Returns a dict keyed by lower-case table name (each table appears once, even
    if several UPDATEs hit it):
        {"table": name, "pk_col": "hmy", "where_columns": [...], "query_count": n}
    """
    queries, _, _ = _mask_and_split(content)
    result = {}
    for q in queries:
        if not q.lower().startswith("update"):
            continue
        parsed = _parse_update(q, [])
        if not parsed:
            continue
        table = parsed["table_name"]
        pk_col = get_pk_col(table)
        if uses_pk(parsed["where_part"], pk_col):
            continue
        entry = result.setdefault(table.lower(), {
            "table": table, "pk_col": pk_col, "where_columns": [], "query_count": 0})
        entry["query_count"] += 1
        known = {c.lower() for c in entry["where_columns"]}
        for c in extract_where_columns(parsed["where_part"]):
            if c.lower() not in known and c.lower() != pk_col:
                known.add(c.lower())
                entry["where_columns"].append(c)
    return result


def process_pkg_content(content, case_id, client_pin="100089812",
                        client_name="Ciminelli Real Estate Corporation",
                        user_name="24931387_110325",
                        password="QDJ1WW9NmlfZrkdp",
                        db_server="PCZ001DB102",
                        instance="PCZ001DB102",
                        db_name="obtmqcwwa_dmtest_110325",
                        modified_by="Priyesh Sahijwani",
                        description="Package to set industry according to lease type for property list '.dmprop'.",
                        fk_overrides=None):
    """fk_overrides: optional {table_name_lower: expression} used as hForeignKey
    in the DataFixHistory inserts for UPDATEs on that table, instead of hmy."""

    fk_overrides = {k.lower(): v for k, v in (fk_overrides or {}).items() if v and v.strip()}
    warnings, output_lines = [], []
    current_date = datetime.now().strftime("%m/%d/%Y")

    notes_block = f"""// Notes
Client Pin: {client_pin}
Client Name: {client_name}
User Name: {user_name}
Password: {password}
DB Server: {db_server}
Instance: {instance}
DB Name: {db_name}

Case#: {case_id} - {modified_by}
Date: {current_date}
Description: {description}
Created By: {modified_by}
// End Notes

// SQL
"""
    output_lines.append(notes_block)

    header_sql = """If Not Exists (Select Name From SysObjects Where Name = 'DataFixHistory')
    Create Table DataFixHistory
    (
        hMy NUMERIC(18,0) IDENTITY(1,1) Not Null,
        hyCRM NUMERIC (18,0) Not Null,
        sTableName VARCHAR(400) Not Null,
        sColumnName VARCHAR(400) Not Null,
        hForeignKey NUMERIC(18,0) Not Null,
        sNotes VarChar(2000) Not Null,
        sNewValue VARCHAR(100),
        sOldValue VARCHAR(100),
        dtDate DATETIME
    )
Else If Not Exists (Select * From INFORMATION_SCHEMA.COLUMNS Where Table_Name = 'DataFixHistory' and Column_Name = 'sColumnName')
    Alter Table DataFixHistory Add sColumnName VARCHAR(400) Null
GO
"""
    output_lines.append(header_sql)

    # Mask string literals + strip comments in one quote-aware pass
    queries, literals, unterminated = _mask_and_split(content)
    if unterminated:
        warnings.append("⚠️ Unterminated string literal (missing closing ') detected in input SQL.")

    # Pre-scan: count how many times each table appears in DELETE queries
    delete_table_counts = {}
    for q in queries:
        q_s = q.strip()
        if q_s.lower().startswith("delete"):
            m = re.match(r"delete\s+from\s+([A-Za-z0-9_#]+)", q_s, re.IGNORECASE)
            if m:
                tbl = m.group(1).lower()
                delete_table_counts[tbl] = delete_table_counts.get(tbl, 0) + 1

    delete_table_occurrence = {}  # tracks current occurrence index per table

    for q in queries:
        q_clean = q.strip()
        q_lower = q_clean.lower()

        if not (q_lower.startswith("update") or q_lower.startswith("delete")):
            continue

        if q_lower.startswith("update"):
            #output_lines.append("-- Auto-generated History Inserts")

            parsed = _parse_update(q_clean, warnings)
            if not parsed:
                warnings.append(f"⚠️ Invalid UPDATE syntax: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: Invalid UPDATE syntax")
                continue

            table_name = parsed["table_name"]
            set_part = parsed["set_part"]
            full_from = parsed["full_from"]
            where_part = parsed["where_part"]

            pk_col = get_pk_col(table_name)
            fk_expr = pk_col

            # Warn when the WHERE clause does not filter on the primary key
            # (checked on the masked text, so 'hmy' inside a string doesn't count).
            # The user's hForeignKey choice only applies to these UPDATEs.
            if not uses_pk(where_part, pk_col):
                fk_expr = fk_overrides.get(table_name.lower(), pk_col)
                warnings.append(
                    f"⚠️ UPDATE on '{table_name}' does not use {pk_col} in the WHERE clause. "
                    f"Verify hForeignKey in DataFixHistory and set it explicitly if needed: "
                    f"{q_clean[:120]}"
                )

            updates = split_top_level_commas(set_part)
            for upd in updates:
                if "=" not in upd:
                    warnings.append(f"⚠️ Skipped malformed SET clause: {upd}")
                    continue
                col, new_val = [x.strip() for x in upd.split("=", 1)]
                if not col or not new_val:
                    warnings.append(f"⚠️ Missing column or value in SET: {upd}")
                    continue
                insert_stmt = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
(select '{case_id}', '{table_name}', '{col}', {fk_expr}, 'updated {table_name}', {new_val}, {col}, GETDATE() {full_from} where {where_part});
GO
""".strip()
                output_lines.append(insert_stmt)

            #output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

        elif q_lower.startswith("delete"):
            #output_lines.append("-- Auto-generated History Insert")

            match = re.match(r"delete\s+from\s+([A-Za-z0-9_#]+)\s*(?:where\s+(.*))?", q_clean,
                             re.IGNORECASE | re.DOTALL)
            if not match:
                warnings.append(f"⚠️ Invalid DELETE syntax: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: Invalid DELETE syntax")
                continue

            table_name = match.group(1)
            where_part = match.group(2) or "1=1"
            if where_part == "1=1":
                warnings.append(f"⚠️ DELETE without WHERE clause detected: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: DELETE without WHERE clause")

            table_lower = table_name.lower()
            is_duplicate = delete_table_counts.get(table_lower, 1) > 1
            if is_duplicate:
                delete_table_occurrence[table_lower] = delete_table_occurrence.get(table_lower, 0) + 1
                occurrence_num = delete_table_occurrence[table_lower]
                temp_table = f"case{case_id}_{table_name}{occurrence_num}"
                notes = f"delete {temp_table} ({table_name})"
            else:
                temp_table = f"case{case_id}_{table_name}"
                notes = f"delete {table_name}"

            pk_col = get_pk_col(table_name)
            insert_stmt = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
(select '{case_id}', '{table_name}', '', {pk_col}, '{notes}', '', '', GETDATE() from {table_name} where {where_part});
GO
""".strip()
            output_lines.append(insert_stmt)

            backup_stmt = f"SELECT * INTO {temp_table} FROM {table_name} where {where_part};"
            #output_lines.append("-- Backup Before Delete")
            output_lines.append(backup_stmt)
            output_lines.append("GO")
            #output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

    output_lines.append("// End SQL")

    # Put the original string literals back
    result = restore_literals("\n\n".join(output_lines), literals)
    warnings = [restore_literals(w, literals) for w in warnings]
    return result, warnings
