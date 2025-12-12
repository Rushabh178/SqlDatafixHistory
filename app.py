import re
import streamlit as st
from automationScriptVersion1 import process_pkg_content

st.set_page_config(page_title="DataFix SQL Generator", layout="wide")
st.title("🧩 DataFix History Automation Tool")

st.markdown(
    "Generate ready-to-run SQL scripts with automatically generated `DataFixHistory` inserts, "
    "including Notes, Case ID, and Database details."
)

CRED_FIELDS = [
    ("client_pin", r"Client\s*Pin\s*[:\-]?\s*(\S+)"),
    ("client_name", r"Client\s*Name\s*[:\-]?\s*(.+)"),
    ("user_name", r"User\s*Name\s*[:\-]?\s*(\S+)"),
    ("password", r"Password\s*[:\-]?\s*(\S+)"),
    ("db_server", r"DB\s*Server\s*[:\-]?\s*(\S+)"),
    ("instance", r"Instance\s*[:\-]?\s*(\S+)"),
    ("db_name", r"DB\s*Name\s*[:\-]?\s*(\S+)")
]

def parse_credentials_block(text: str) -> dict:
    result = {}
    if not text:
        return result
    for key, pattern in CRED_FIELDS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            result[key] = m.group(1).strip()
    return result

uploaded_file = st.file_uploader("📂 Upload your .txt or .pkg or .sql file", type=["pkg", "sql", "txt"])

st.markdown("### ✏️ Or Paste SQL Manually")
pasted_sql = st.text_area("Paste SQL Content", height=200, key="pasted_sql")

st.markdown("---")
st.subheader("💾 Client & Database Information")

if "client_pin" not in st.session_state:
    st.session_state.update({
        "client_pin": "",
        "user_name": "",
        "db_server": "",
        "client_name": "",
        "password": "",
        "instance": "",
        "db_name": ""
    })

col1, col2, col3 = st.columns(3)

with col1:
    client_pin = st.text_input("Client Pin", value=st.session_state.client_pin, key="client_pin")
    user_name = st.text_input("User Name", value=st.session_state.user_name, key="user_name")
    db_server = st.text_input("DB Server", value=st.session_state.db_server, key="db_server")

with col2:
    client_name = st.text_input("Client Name", value=st.session_state.client_name, key="client_name")
    password = st.text_input("Password", value=st.session_state.password, key="password")
    instance = st.text_input("Instance", value=st.session_state.instance, key="instance")

with col3:
    db_name = st.text_input("DB Name", value=st.session_state.db_name, key="db_name")

st.markdown("---")
st.markdown("### 🔁 Quick-paste credentials (auto-populates fields)")

cred_col1, cred_col2 = st.columns([4, 1])
with cred_col1:
    creds_block = st.text_area("Paste credential block here", height=140, key="creds_block")

with cred_col2:
    if st.button("Parse Credentials"):
        parsed = parse_credentials_block(st.session_state.creds_block)
        if parsed:
            st.session_state.update(parsed)
            st.success("Credentials parsed and applied.")
        else:
            st.warning("No valid credentials detected.")

st.markdown("---")

case_id = st.text_input("🔢 Case ID")
modified_by = st.text_input("👤 Modified By")
description = st.text_area("📝 Description", height=80)

st.markdown("---")

content = None
if uploaded_file:
    raw = uploaded_file.read()
    content = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
elif pasted_sql.strip():
    content = pasted_sql.strip()

generate_disabled = not (content and case_id)

if st.button("🚀 Generate DataFix SQL", disabled=generate_disabled):
    try:
        output_sql, warnings = process_pkg_content(
            content,
            case_id,
            client_pin=st.session_state.client_pin,
            client_name=st.session_state.client_name,
            user_name=st.session_state.user_name,
            password=st.session_state.password,
            db_server=st.session_state.db_server,
            instance=st.session_state.instance,
            db_name=st.session_state.db_name,
            modified_by=modified_by,
            description=description
        )

        st.success("SQL generated successfully.")

        if warnings:
            st.warning("Warnings detected:")
            for w in warnings:
                st.text(w)

        st.download_button(
            label="💾 Download SQL File",
            data=output_sql,
            file_name=f"case_{case_id}_datafix.pkg",
            mime="text/sql"
        )

        with st.expander("📄 Preview Generated SQL"):
            st.code(output_sql, language="sql")

    except Exception as e:
        st.exception(e)
else:
    if not content or not case_id:
        st.info("Upload a file or paste SQL content, and enter Case ID.")

st.markdown("---")
st.markdown(
    "Paste a full credential block to auto-fill fields. Uploaded file takes priority over pasted SQL."
)
