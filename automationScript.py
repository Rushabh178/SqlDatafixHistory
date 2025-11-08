import re
import sys

def process_pkg_file(input_file, output_file, case_id):
    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    output_lines = []

    for line in lines:
        q_clean = line.strip()
        if not q_clean:
            continue  

        if q_clean.lower().startswith("update"):
            output_lines.append("-- Auto-generated History Inserts")

            table_match = re.match(r"update\s+([A-Za-z0-9_#]+)\s+set\s+(.*)\s+where\s+(.*)", q_clean, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1)
                set_part = table_match.group(2)
                where_part = table_match.group(3)

                updates = [u.strip() for u in set_part.split(",")]

                for upd in updates:
                    if "=" in upd:
                        col, new_val = [x.strip() for x in upd.split("=", 1)]
                        history_insert = f"""
INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '{case_id}', '{table_name}', '{col}', hmy, 'updated {table_name}', {new_val}, {col}, GETDATE() from {table_name} where {where_part});
"""
                        output_lines.append(history_insert.strip())

            output_lines.append("-- Original Query")
            output_lines.append(q_clean)

        elif q_clean.lower().startswith("delete"):
            output_lines.append("-- Auto-generated History Insert")
            table_match = re.search(r"delete from\s+([A-Za-z0-9_#]+)", q_clean, re.IGNORECASE)
            table_name = table_match.group(1) if table_match else "UnknownTable"

            history_insert = f"""
INSERT INTO DatafixHistory
(hycrm, sTableName, sColumnName, hForeignKey, sNotes, sNewValue, sOldValue, dtDate)
VALUES
(select '{case_id}', '{table_name}', '', hmy, 'delete {table_name}', '', '', GETDATE() from {table_name} where {where_part});
"""
            output_lines.append(history_insert.strip())


            temp_table = f"case#{case_id}_{table_name}"
            backup_stmt = f"SELECT * INTO {temp_table} FROM {table_name} where {where_part};"
            output_lines.append("-- Backup Before Delete")
            output_lines.append(backup_stmt)

            output_lines.append("-- Original Query")
            output_lines.append(q_clean)

        else:

            output_lines.append("-- Original Query")
            output_lines.append(q_clean)


    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(output_lines))

    print(f"✅ Output written to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python automationScript.py <input.pkg> <output.sql> <case_id>")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        case_id = sys.argv[3]
        process_pkg_file(input_file, output_file, case_id)
