import re

def process_pkg_content(content, case_id):
    warnings = []
    output_lines = []

    # DataFixHistory Table Creation Header
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

    # Clean content
    content = re.sub(r"--.*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"[ \t]+", " ", content).strip()

    # Split at every new UPDATE or DELETE keyword
    queries = re.split(r"(?i)(?=(?:\bupdate\b|\bdelete\b))", content)
    queries = [q.strip() for q in queries if q.strip()]

    for q in queries:
        q_clean = q.strip()
        q_lower = q_clean.lower()

        if not (q_lower.startswith("update") or q_lower.startswith("delete")):
            continue

        output_lines.append("-- ----------------------------")
        output_lines.append(f"-- Processing Query: {q_clean[:120]}")
        output_lines.append("-- ----------------------------")

        # UPDATE Section
        if q_lower.startswith("update"):
            output_lines.append("-- Auto-generated History Inserts")
            is_complex = " from " in q_lower

            if not is_complex:
                match = re.match(
                    r"update\s+([A-Za-z0-9_#]+)\s+set\s+(.*?)\s+where\s+(.*)",
                    q_clean,
                    re.IGNORECASE,
                )
                if not match:
                    warnings.append(f"⚠️ Invalid UPDATE syntax: {q_clean[:120]}")
                    output_lines.append("-- ⚠️ WARNING: Invalid UPDATE syntax")
                    continue
                table_name = match.group(1)
                set_part = match.group(2)
                where_part = match.group(3)
            else:
                match = re.match(
                    r"update\s+([A-Za-z0-9_#]+)\s+set\s+(.*?)\s+from\s+([A-Za-z0-9_#]+).*?\bwhere\b\s+(.*)",
                    q_clean,
                    re.IGNORECASE,
                )
                if not match:
                    warnings.append(f"⚠️ Invalid complex UPDATE syntax: {q_clean[:120]}")
                    output_lines.append("-- ⚠️ WARNING: Invalid complex UPDATE syntax")
                    continue
                alias = match.group(1)
                set_part = match.group(2)
                table_name = match.group(3)
                where_part = match.group(4)

            updates = [u.strip() for u in re.split(r",\s*(?![^()]*\))", set_part)]

            for upd in updates:
                if "=" not in upd:
                    warnings.append(f"⚠️ Skipped malformed SET clause: {upd}")
                    continue
                col, new_val = [x.strip() for x in upd.split("=", 1)]
                history_insert = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '{case_id}', '{table_name}', '{col}', hmy, 'updated {table_name}', {new_val}, {col}, GETDATE() from {table_name} where {where_part});
GO
""".strip()
                output_lines.append(history_insert)

            output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

        # DELETE Section
        elif q_lower.startswith("delete"):
            output_lines.append("-- Auto-generated History Insert")
            match = re.match(
                r"delete\s+from\s+([A-Za-z0-9_#]+)\s*(?:where\s+(.*))?",
                q_clean,
                re.IGNORECASE,
            )
            if not match:
                warnings.append(f"⚠️ Invalid DELETE syntax: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: Invalid DELETE syntax")
                continue

            table_name = match.group(1)
            where_part = match.group(2) or "1=1"
            if where_part == "1=1":
                warnings.append(f"⚠️ DELETE without WHERE clause: {q_clean[:120]}")
                output_lines.append("-- ⚠️ WARNING: DELETE without WHERE clause")

            history_insert = f"""
INSERT INTO DataFixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '{case_id}', '{table_name}', '', hmy, 'delete {table_name}', '', '', GETDATE() from {table_name} where {where_part});
GO
""".strip()
            output_lines.append(history_insert)

            temp_table = f"case#{case_id}_{table_name}"
            backup_stmt = f"SELECT * INTO {temp_table} FROM {table_name} where {where_part};"
            output_lines.append("-- Backup Before Delete")
            output_lines.append(backup_stmt)
            output_lines.append("GO")

            output_lines.append("-- Original Query")
            output_lines.append(q_clean)
            output_lines.append("GO")

    return "\n\n".join(output_lines), warnings
