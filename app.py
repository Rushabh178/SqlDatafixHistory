import streamlit as st
from automationScriptVersion1 import process_pkg_content

st.set_page_config(page_title="DataFix SQL Generator", layout="wide")
st.title("🧩 DataFix History Automation Tool")

st.markdown(
    "Generate ready-to-run SQL scripts with automatically generated `DataFixHistory` inserts, "
    "including Notes, Case ID, and Database details."
)

uploaded_file = st.file_uploader("📂 Upload your .pkg or .sql file", type=["pkg", "sql", "txt"])
st.markdown("---")

st.markdown("### ✏️ Or Paste SQL Manually")
pasted_sql = st.text_area(
    "Paste SQL Content",
    placeholder="Paste your SQL or .pkg content here...",
    height=200
)

case_id = st.text_input("🔢 Case ID", placeholder="Enter Case ID (e.g. 17269907)")
modified_by = st.text_input("👤 Modified By", placeholder="Alex Albon")
description = st.text_area(
    "📝 Description",
    placeholder="Package to set industry according to lease type for property list '.dmprop'."
)

st.markdown("---")

st.subheader("💾 Client & Database Information")

col1, col2, col3 = st.columns(3)

with col1:
    client_pin = st.text_input("Client Pin", placeholder="100089812")
    user_name = st.text_input("User Name", placeholder="24931387_110325")
    db_server = st.text_input("DB Server", placeholder="PCZ001DB102")

with col2:
    client_name = st.text_input("Client Name", placeholder="Ciminelli Real Estate Corporation")
    password = st.text_input("Password", placeholder="QDJ1WW9NmlfZrkdp")
    instance = st.text_input("Instance", placeholder="PCZ001DB102")

with col3:
    db_name = st.text_input("DB Name", placeholder="obtmqcwwa_dmtest_110325")


content = None

if uploaded_file is not None:
    try:
        raw = uploaded_file.read()
        content = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
    except Exception as e:
        st.error(f"Failed to read uploaded file: {e}")
elif pasted_sql.strip():
    content = pasted_sql.strip()

if st.button("🚀 Generate DataFix SQL"):
    if not content:
        st.error("Please upload a file or paste SQL content first.")
    elif not case_id:
        st.error("Please provide a Case ID.")
    else:
        try:
            output_sql, warnings = process_pkg_content(
                content,
                case_id,
                client_pin=client_pin,
                client_name=client_name,
                user_name=user_name,
                password=password,
                db_server=db_server,
                instance=instance,
                db_name=db_name,
                modified_by=modified_by,
                description=description
            )

            st.success("✅ SQL generated successfully!")

            if warnings:
                st.warning("⚠️ Some syntax warnings detected:")
                for w in warnings:
                    st.text(w)

            st.download_button(
                label="💾 Download SQL File",
                data=output_sql,
                file_name=f"case_{case_id}_datafix.pkg",
                mime="text/sql",
            )

            with st.expander("📄 Preview Generated SQL"):
                st.code(output_sql, language="sql")

        except Exception as e:
            st.exception(e)
else:
    st.info("👆 Please upload a SQL file OR paste SQL content, and enter a Case ID to proceed.")
