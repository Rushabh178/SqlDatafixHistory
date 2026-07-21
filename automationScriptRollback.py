import re
from datetime import datetime


def extract_alias_map(from_block: str):
    alias_map = {}
    f = re.sub(r"\s+", " ", from_block)

    parts = re.split(r"\bjoin\b", f, flags=re.IGNORECASE)

    for p in parts:
        m = re.search(r"([A-Za-z0-9_#]+)\s+(?:as\s+)?([A-Za-z0-9_#]+)", p, flags=re.IGNORECASE)
        if m:
            table, alias = m.groups()
            alias_map[alias.lower()] = table
        else:
            m2 = re.match(r"^\s*([A-Za-z0-9_#]+)\s*$", p.strip())
            if m2:
                table = m2.group(1)
                alias_map[table.lower()] = table

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


def _pk_col_for(table_name: str) -> str:
    return "hmyperson" if table_name.lower() in ("tenant", "vendor") else "hmy"


def _parse_update_chunk(q_clean: str, warnings: list):
    """Parse a single 'update table set ... [from ...] [where ...]' chunk.
    Returns dict(table_name, alias, pk_col, cols) or None."""
    m = re.match(r"update\s+([A-Za-z0-9_#]+)\s+set\s+", q_clean, re.IGNORECASE)
    if not m:
        warnings.append(f"⚠️ Could not parse UPDATE: {q_clean[:100]}")
        return None

    alias = m.group(1)
    set_start = m.end()

    from_idx = find_top_level_kw(q_clean, "from", set_start)
    where_idx = find_top_level_kw(q_clean, "where", set_start)

    if from_idx != -1 and (where_idx == -1 or from_idx < where_idx):
        set_part = q_clean[set_start:from_idx].strip()
        from_end = where_idx if where_idx != -1 else len(q_clean)
        from_part = q_clean[from_idx + len("from"):from_end].strip()
        alias_map = extract_alias_map(from_part)
        table_name = alias_map.get(alias.lower(), alias)
    else:
        # No FROM clause -- plain "UPDATE table SET ... WHERE ..." form.
        table_name = alias
        set_end = where_idx if where_idx != -1 else len(q_clean)
        set_part = q_clean[set_start:set_end].strip()

    if not set_part:
        warnings.append(f"⚠️ No SET clause found: {q_clean[:100]}")
        return None

    updates = [u.strip() for u in re.split(r",\s*(?![^()]*\))", set_part)]
    cols = []
    for upd in updates:
        if "=" not in upd:
            continue
        col, _ = upd.split("=", 1)
        col = col.strip()
        if col:
            cols.append(col)

    if not cols:
        warnings.append(f"⚠️ No columns parsed from SET clause: {q_clean[:100]}")
        return None

    return {
        "table_name": table_name,
        "alias": alias,
        "pk_col": _pk_col_for(table_name),
        "cols": cols,
    }


def _parse_select_into_chunk(q_clean: str, warnings: list):
    """Parse a 'select * into <backup_table> from <table> ...' chunk (the
    backup a delete-fix takes before removing rows). Returns
    dict(backup_table, table_name) or None."""
    m = re.match(
        r"select\s+\*\s+into\s+([A-Za-z0-9_#]+)\s+from\s+([A-Za-z0-9_#]+)",
        q_clean,
        re.IGNORECASE,
    )
    if not m:
        warnings.append(f"⚠️ Could not parse SELECT INTO backup: {q_clean[:100]}")
        return None

    backup_table, table_name = m.groups()
    return {"backup_table": backup_table, "table_name": table_name}


def _parse_delete_chunk(q_clean: str, warnings: list):
    """Parse a 'delete from <table> ...' chunk, used only to validate that a
    matching backup exists -- the actual rollback action comes from the
    SELECT INTO backup, not from this statement."""
    m = re.match(r"delete\s+from\s+([A-Za-z0-9_#]+)", q_clean, re.IGNORECASE)
    if not m:
        warnings.append(f"⚠️ Could not parse DELETE: {q_clean[:100]}")
        return None
    return {"table_name": m.group(1)}


def generate_rollback_pkg(
    content,
    case_id,
    client_pin="",
    client_name="",
    user_name="",
    password="",
    db_server="",
    instance="",
    db_name="",
    modified_by="",
    description="Rollback package",
    use_identity_insert=True,
):
    warnings = []
    output_lines = []

    current_date = datetime.now().strftime("%m/%d/%Y")

    # ---------------------------
    # Notes Block
    # ---------------------------
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
Modified By: {modified_by}
// End Notes

// SQL
"""
    output_lines.append(notes_block)

    # ---------------------------
    # Clean SQL
    # ---------------------------
    content = re.sub(r"--.*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"[ \t]+", " ", content).strip()

    # Split into statement chunks at every top-level UPDATE / DELETE /
    # SELECT * INTO keyword so we can walk the package in document order.
    # (INSERT INTO DataFixHistory logging blocks fall through untouched --
    # they're audit rows and are intentionally left alone by a rollback.)
    chunks = re.split(
        r"(?i)(?=\bupdate\b|\bdelete\s+from\b|\bselect\s+\*\s+into\b)",
        content,
    )
    chunks = [c.strip() for c in chunks if c.strip()]

    # ---------------------------
    # Walk chunks in order, building an ordered undo log. Deletes are
    # validated against their backup (FIFO per table) so we can warn if a
    # delete has no matching SELECT INTO to restore from.
    # ---------------------------
    ops = []
    pending_backups = {}  # table_name.lower() -> [backup_table, ...]

    for q in chunks:
        q_lower = q.lower()

        if q_lower.startswith("update"):
            parsed = _parse_update_chunk(q, warnings)
            if parsed:
                ops.append({"type": "update", **parsed})

        elif q_lower.startswith("select"):
            parsed = _parse_select_into_chunk(q, warnings)
            if parsed:
                ops.append({"type": "delete", **parsed})
                pending_backups.setdefault(parsed["table_name"].lower(), []).append(
                    parsed["backup_table"]
                )

        elif q_lower.startswith("delete"):
            parsed = _parse_delete_chunk(q, warnings)
            if parsed:
                key = parsed["table_name"].lower()
                queue = pending_backups.get(key, [])
                if queue:
                    queue.pop(0)
                else:
                    warnings.append(
                        f"⚠️ DELETE FROM {parsed['table_name']} has no matching "
                        "SELECT INTO backup -- cannot generate a rollback for it."
                    )

    if not ops:
        warnings.append("⚠️ No UPDATE or DELETE (with backup) statements found to roll back.")

    # ---------------------------
    # Emit rollback statements in reverse chronological order (LIFO),
    # so the most recent change is undone first.
    # ---------------------------
    for op in reversed(ops):
        if op["type"] == "update":
            table_name = op["table_name"]
            alias = op["alias"]
            pk_col = op["pk_col"]

            for col in op["cols"]:
                rollback_stmt = f"""
UPDATE {alias}
SET {col} = dfh.sOldValue
FROM {table_name} {alias}
JOIN DataFixHistory dfh
    ON dfh.hForeignKey = {alias}.{pk_col}
WHERE dfh.hyCRM = '{case_id}'
  AND dfh.sTableName = '{table_name}'
  AND dfh.sColumnName = '{col}';
GO
""".strip()
                output_lines.append(rollback_stmt)

        elif op["type"] == "delete":
            table_name = op["table_name"]
            backup_table = op["backup_table"]

            lines = []
            if use_identity_insert:
                lines.append(f"SET IDENTITY_INSERT {table_name} ON;")
                lines.append("GO")
                lines.append("")

            lines.append(f"INSERT INTO {table_name}")
            lines.append(f"SELECT * FROM {backup_table};")
            lines.append("GO")

            if use_identity_insert:
                lines.append("")
                lines.append(f"SET IDENTITY_INSERT {table_name} OFF;")
                lines.append("GO")

            output_lines.append("\n".join(lines))

    has_delete_ops = any(op["type"] == "delete" for op in ops)
    if use_identity_insert and has_delete_ops:
        warnings.append(
            "ℹ️ Delete-rollback INSERTs are wrapped in SET IDENTITY_INSERT ON/OFF to "
            "preserve original hMy/PK values. Remove those lines for any table that has no "
            "identity column (SQL Server will error otherwise)."
        )

    output_lines.append("// End SQL")

    return "\n\n".join(output_lines), warnings
