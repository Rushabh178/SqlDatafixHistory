import re
from datetime import datetime


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


def process_pkg_content(content, case_id, client_pin="100089812",
                        client_name="Ciminelli Real Estate Corporation",
                        user_name="24931387_110325",
                        password="QDJ1WW9NmlfZrkdp",
                        db_server="PCZ001DB102",
                        instance="PCZ001DB102",
                        db_name="obtmqcwwa_dmtest_110325",
                        modified_by="Priyesh Sahijwani",
                        description="Package to set industry according to lease type for property list '.dmprop'."):

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
Modified By: {modified_by}
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

    content = re.sub(r"--.*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"[ \t]+", " ", content).strip()
    queries = re.split(r"(?i)(?=(?:\bupdate\b|\bdelete\b))", content)
    queries = [q.strip() for q in queries if q.strip()]

    for q in queries:
        q_clean = q.strip()
        q_lower = q_clean.lower()

        if not (q_lower.startswith("update") or q_lower.startswith("delete")):
            continue

        if q_lower.startswith("update"):
            #output_lines.append("-- Auto-generated History Inserts")

            m = re.match(r"update\s+([A-Za-z0-9_#]+)\s+set\s+", q_clean, re.IGNORECASE)
            if not m:
                warnings.append(f"⚠️ Invalid UPDATE syntax: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: Invalid UPDATE syntax")
                continue

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

            updates = [u.strip() for u in re.split(r",\s*(?![^()]*\))", set_part)]
            for upd in updates:
                if "=" not in upd:
                    warnings.append(f"⚠️ Skipped malformed SET clause: {upd}")
                    continue
                col, new_val = [x.strip() for x in upd.split("=", 1)]
                if not col or not new_val:
                    warnings.append(f"⚠️ Missing column or value in SET: {upd}")
                    continue
                pk_col = "hmyperson" if table_name.lower() == "tenant" or table_name.lower() == "vendor" else "hmy"
                insert_stmt = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
(select '{case_id}', '{table_name}', '{col}', {pk_col}, 'updated {table_name}', {new_val}, {col}, GETDATE() {full_from} where {where_part});
GO                
""".strip()
                output_lines.append(insert_stmt)

            #output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

        elif q_lower.startswith("delete"):
            #output_lines.append("-- Auto-generated History Insert")

            match = re.match(r"delete\s+from\s+([A-Za-z0-9_#]+)\s*(?:where\s+(.*))?", q_clean, re.IGNORECASE)
            if not match:
                warnings.append(f"⚠️ Invalid DELETE syntax: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: Invalid DELETE syntax")
                continue

            table_name = match.group(1)
            where_part = match.group(2) or "1=1"
            if where_part == "1=1":
                warnings.append(f"⚠️ DELETE without WHERE clause detected: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: DELETE without WHERE clause")

            pk_col = "hmyperson" if table_name.lower() == "tenant" or table_name.lower() == "vendor" else "hmy"
            insert_stmt = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
(select '{case_id}', '{table_name}', '', {pk_col}, 'delete {table_name}', '', '', GETDATE() from {table_name} where {where_part});
GO
""".strip()
            output_lines.append(insert_stmt)

            temp_table = f"case{case_id}_{table_name}"
            backup_stmt = f"SELECT * INTO {temp_table} FROM {table_name} where {where_part};"
            #output_lines.append("-- Backup Before Delete")
            output_lines.append(backup_stmt)
            output_lines.append("GO")
            #output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

    output_lines.append("// End SQL")
    return "\n\n".join(output_lines), warnings
