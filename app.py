import streamlit as st
from automationScriptVersion1 import process_pkg_content, find_non_pk_updates
from automationScriptRollback import generate_rollback_pkg  # NEW

st.set_page_config(page_title="DataFix SQL Generator", layout="wide")

MANUAL_OPTION = "✏️ Enter manually"


def render_fk_picker(issues):
    """One entry per table (even if several UPDATEs hit it). Returns
    {table_lower: expression} for the tables where the user chose something
    other than the default hmy/hmyperson."""
    overrides = {}
    st.markdown("#### 🔑 hForeignKey for UPDATEs without hmy in the WHERE clause")
    st.caption(
        "These tables are updated without hmy in the WHERE clause. If you are using a different "
        "value instead of hmy, choose which column should go into hForeignKey in DataFixHistory. "
        "hForeignKey is numeric, so pick a handle column (h...) or enter an expression manually."
    )

    for table_lower, info in issues.items():
        pk_col = info["pk_col"]
        default_label = f"Keep {pk_col} (default)"
        options = [default_label] + info["where_columns"] + [MANUAL_OPTION]

        count = info["query_count"]
        label = f"**{info['table']}** — used in {count} UPDATE{'s' if count > 1 else ''}"
        choice = st.radio(label, options, key=f"fk_choice_{table_lower}", horizontal=True)

        if choice == MANUAL_OPTION:
            manual = st.text_input(
                f"hForeignKey expression for {info['table']}",
                placeholder="e.g. p.hmy or u.hProperty",
                key=f"fk_manual_{table_lower}",
            )
            if manual.strip():
                overrides[table_lower] = manual.strip()
        elif choice != default_label:
            overrides[table_lower] = choice

    return overrides


# ---------------------------
# 🧭 Sidebar Navigation
# ---------------------------
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio(
    "Select Action:",
    ["🧩 Generate DataFix Package", "🔁 Generate Rollback Package"]
)

# ============================================================
# 🧩 EXISTING FORWARD GENERATOR
# ============================================================
if page == "🧩 Generate DataFix Package":

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
    modified_by = st.text_input("👤 Created By", placeholder="Alex Albon")
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
            st.session_state.pop("fwd_params", None)
        elif not case_id:
            st.error("Please provide a Case ID.")
            st.session_state.pop("fwd_params", None)
        else:
            # Keep the inputs so the result survives reruns caused by the
            # hForeignKey radio buttons / text boxes below.
            st.session_state["fwd_params"] = dict(
                content=content,
                case_id=case_id,
                client_pin=client_pin,
                client_name=client_name,
                user_name=user_name,
                password=password,
                db_server=db_server,
                instance=instance,
                db_name=db_name,
                modified_by=modified_by,
                description=description,
            )

    params = st.session_state.get("fwd_params")

    if params:
        try:
            success_box = st.container()
            warning_box = st.container()

            # List below the warnings: one row per table, never repeated
            issues = find_non_pk_updates(params["content"])
            overrides = render_fk_picker(issues) if issues else {}

            p = dict(params)
            output_sql, warnings = process_pkg_content(
                p.pop("content"),
                p.pop("case_id"),
                fk_overrides=overrides,
                **p,
            )

            with success_box:
                st.success("✅ SQL generated successfully!")

            with warning_box:
                if warnings:
                    st.warning("⚠️ Some syntax warnings detected:")
                    for w in warnings:
                        st.text(w)

            st.download_button(
                label="💾 Download SQL File",
                data=output_sql,
                file_name=f"case_{params['case_id']}_datafix.pkg",
                mime="text/sql",
            )

            with st.expander("📄 Preview Generated SQL"):
                st.code(output_sql, language="sql")

        except Exception as e:
            st.exception(e)
    else:
        st.info("👆 Please upload a SQL file OR paste SQL content, and enter a Case ID to proceed.")


# ============================================================
# 🔁 NEW ROLLBACK GENERATOR
# ============================================================
elif page == "🔁 Generate Rollback Package":

    st.title("🔁 Rollback Package Generator")

    st.markdown(
        "Generate rollback SQL using `DataFixHistory` to restore original values."
    )

    uploaded_file = st.file_uploader("📂 Upload original .pkg / .sql file", type=["pkg", "sql", "txt"], key="rollback_upload")

    st.markdown("---")

    pasted_sql = st.text_area(
        "✏️ Or Paste SQL Content",
        placeholder="Paste original SQL here...",
        height=200,
        key="rollback_text"
    )

    case_id = st.text_input("🔢 Case ID (Required)", key="rollback_case")
    modified_by = st.text_input("👤 Modified By", key="rollback_user")
    description = st.text_area("📝 Description", key="rollback_desc")

    st.markdown("---")

    st.subheader("💾 Client & Database Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        client_pin = st.text_input("Client Pin", key="rb_client_pin")
        user_name = st.text_input("User Name", key="rb_user_name")
        db_server = st.text_input("DB Server", key="rb_db_server")

    with col2:
        client_name = st.text_input("Client Name", key="rb_client_name")
        password = st.text_input("Password", key="rb_password")
        instance = st.text_input("Instance", key="rb_instance")

    with col3:
        db_name = st.text_input("DB Name", key="rb_db_name")

    content = None

    if uploaded_file is not None:
        try:
            raw = uploaded_file.read()
            content = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
        except Exception as e:
            st.error(f"Failed to read uploaded file: {e}")
    elif pasted_sql.strip():
        content = pasted_sql.strip()

    if st.button("🔁 Generate Rollback SQL"):
        if not content:
            st.error("Please upload or paste SQL content.")
        elif not case_id:
            st.error("Case ID is required.")
        else:
            try:
                rollback_sql, warnings = generate_rollback_pkg(
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
                    description=description or "Rollback package"
                )

                st.success("✅ Rollback SQL generated!")

                if warnings:
                    st.warning("⚠️ Warnings:")
                    for w in warnings:
                        st.text(w)

                st.download_button(
                    label="💾 Download Rollback Package",
                    data=rollback_sql,
                    file_name=f"rollback_{case_id}.pkg",
                    mime="text/sql",
                )

                with st.expander("📄 Preview Rollback SQL"):
                    st.code(rollback_sql, language="sql")

            except Exception as e:
                st.exception(e)
