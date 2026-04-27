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
    description="Rollback package"
):
    warnings = []
    output_lines = []

    current_date = datetime.now().strftime("%m/%d/%Y")

    # ---------------------------
    # 📝 Notes Block
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
    # 🔍 Clean SQL
    # ---------------------------
    content = re.sub(r"--.*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"[ \t]+", " ", content).strip()

    queries = re.split(r"(?i)(?=\bupdate\b)", content)
    queries = [q.strip() for q in queries if q.strip().lower().startswith("update")]

    # ---------------------------
    # 🔁 Process Each UPDATE
    # ---------------------------
    for q in queries:
        q_clean = q.strip()

        # Extract alias
        m = re.match(r"update\s+([A-Za-z0-9_#]+)", q_clean, re.IGNORECASE)
        if not m:
            warnings.append(f"⚠️ Could not parse UPDATE: {q_clean[:100]}")
            continue

        alias = m.group(1)

        # Extract FROM
        from_match = re.search(r"\bfrom\b(.*?)(\bwhere\b|$)", q_clean, re.IGNORECASE)
        if not from_match:
            warnings.append(f"⚠️ No FROM found: {q_clean[:100]}")
            continue

        from_part = from_match.group(1).strip()
        alias_map = extract_alias_map(from_part)

        table_name = alias_map.get(alias.lower(), alias)

        # Extract SET
        set_match = re.search(r"\bset\b(.*?)\bfrom\b", q_clean, re.IGNORECASE | re.DOTALL)
        if not set_match:
            warnings.append(f"⚠️ No SET found: {q_clean[:100]}")
            continue

        set_part = set_match.group(1)
        updates = [u.strip() for u in re.split(r",\s*(?![^()]*\))", set_part)]

        pk_col = "hmyperson" if table_name.lower() in ["tenant", "vendor"] else "hmy"

        for upd in updates:
            if "=" not in upd:
                continue

            col, _ = upd.split("=", 1)
            col = col.strip()

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

    output_lines.append("// End SQL")

    return "\n\n".join(output_lines), warnings
