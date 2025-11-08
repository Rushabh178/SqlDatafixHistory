import streamlit as st
from automationScriptVersion1 import process_pkg_content

st.set_page_config(page_title="Datafix Automation Tool", layout="wide")

st.title("🧩 SQL Datafix Automation Tool")
st.markdown("""
Automatically generate **DatafixHistory** inserts and backups  
from your `.pkg` SQL scripts. Handles complex `UPDATE`/`DELETE` safely.
""")

uploaded_file = st.file_uploader("📂 Upload your .pkg or .sql file", type=["pkg", "sql"])
case_id = st.text_input("🔢 Enter Case ID", value="123456")

if uploaded_file and case_id:
    content = uploaded_file.read().decode("utf-8")

    if st.button("🚀 Generate Datafix SQL"):
        with st.spinner("Processing SQL..."):
            output_sql, warnings = process_pkg_content(content, case_id)

        st.success("✅ Successfully generated output!")

        st.subheader("📜 Generated SQL Script:")
        st.code(output_sql, language="sql")

        if warnings:
            st.warning("⚠️ Some issues were detected:")
            for w in warnings:
                st.text(w)

        st.download_button(
            label="💾 Download Output File",
            data=output_sql,
            file_name=f"Datafix_{case_id}.pkq",
            mime="text/sql",
        )
else:
    st.info("Please upload a .pkg file and enter a case ID to begin.")
