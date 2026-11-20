"""PayRecon – Intelligent Payment Reconciliation System.

Enterprise Fintech SaaS Streamlit application for payment platform vs bank settlement reconciliation.
"""

import io
import os
from decimal import Decimal
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_generator import generate_datasets
from src.data_validator import (
    validate_transactions,
    validate_settlements,
    ValidationResult,
)
from src.reconciliation import (
    ReconciliationEngine,
    ReconciliationItem,
    ReconciliationStatus,
    ReconciliationSummary,
)
from src.report_generator import (
    generate_reconciliation_csv,
    generate_discrepancy_csv,
    generate_summary_csv,
    generate_matched_csv,
    generate_unmatched_csv,
    generate_duplicates_csv,
    generate_refunds_csv,
)

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="PayRecon – Intelligent Payment Reconciliation",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "reconcile_trigger" not in st.session_state:
    st.session_state.reconcile_trigger = 0

# ---------------------------------------------------------
# Theme & Custom Fintech SaaS CSS Styling
# ---------------------------------------------------------
is_dark = st.session_state.theme == "dark"

bg_color = "#0b0f19" if is_dark else "#f8fafc"
card_bg = "#111827" if is_dark else "#ffffff"
text_primary = "#f3f4f6" if is_dark else "#0f172a"
text_secondary = "#9ca3af" if is_dark else "#64748b"
border_color = "#1f2937" if is_dark else "#e2e8f0"
table_header_bg = "#1f2937" if is_dark else "#f1f5f9"
table_row_alt = "#161f30" if is_dark else "#f8fafc"

st.markdown(
    f"""
    <style>
    /* Global Base */
    .stApp {{
        background-color: {bg_color};
        color: {text_primary};
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    }}
    
    /* Header Container */
    .payrecon-header {{
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%);
        padding: 24px 32px;
        border-radius: 14px;
        color: #ffffff;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .payrecon-header h1 {{
        color: #ffffff !important;
        font-size: 28px;
        font-weight: 700;
        margin: 0;
        padding: 0;
        letter-spacing: -0.5px;
    }}
    .payrecon-header p {{
        color: #cbd5e1;
        font-size: 14px;
        margin-top: 6px;
        margin-bottom: 0;
    }}
    .badge-pill {{
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.25);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        color: #f8fafc;
        margin-right: 8px;
        margin-top: 10px;
    }}

    /* KPI Cards */
    .kpi-card {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        margin-bottom: 12px;
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.08);
    }}
    .kpi-title {{
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: {text_secondary};
        margin-bottom: 6px;
    }}
    .kpi-value {{
        font-size: 22px;
        font-weight: 800;
        color: {text_primary};
        margin-bottom: 4px;
        letter-spacing: -0.5px;
    }}
    .kpi-subtitle {{
        font-size: 12px;
        color: {text_secondary};
    }}
    .border-blue {{ border-left: 4px solid #3b82f6 !important; }}
    .border-green {{ border-left: 4px solid #10b981 !important; }}
    .border-amber {{ border-left: 4px solid #f59e0b !important; }}
    .border-red {{ border-left: 4px solid #ef4444 !important; }}
    .border-purple {{ border-left: 4px solid #8b5cf6 !important; }}

    /* Financial Ledger Table */
    .fin-ledger-table {{
        width: 100%;
        border-collapse: collapse;
        background: {card_bg};
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid {border_color};
        font-size: 13.5px;
        margin-top: 8px;
    }}
    .fin-ledger-table th {{
        background-color: {table_header_bg};
        color: {text_primary};
        font-weight: 700;
        text-align: left;
        padding: 12px 18px;
        border-bottom: 2px solid {border_color};
    }}
    .fin-ledger-table td {{
        padding: 11px 18px;
        border-bottom: 1px solid {border_color};
        color: {text_primary};
    }}
    .ledger-row-highlight {{
        font-weight: 700;
        background-color: {table_row_alt};
    }}

    /* Card Panels */
    .panel-box {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 18px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_or_generate_sample_data(seed: int = 42):
    """Ensure data files exist and load reproducible sample datasets."""
    os.makedirs("data", exist_ok=True)
    txn_path = os.path.join("data", "transactions.csv")
    settle_path = os.path.join("data", "settlements.csv")

    if not os.path.exists(txn_path) or not os.path.exists(settle_path):
        generate_datasets(output_dir="data", seed=seed)

    df_t = pd.read_csv(txn_path)
    df_s = pd.read_csv(settle_path)
    return df_t, df_s


# ---------------------------------------------------------
# SIDEBAR: Navigation & Engine Controls
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
            <div style="background: #2563eb; width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px;">💳</div>
            <div>
                <span style="font-size: 18px; font-weight: 800; letter-spacing: -0.5px;">PayRecon</span><br>
                <span style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Fintech Recon Engine</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_section = st.radio(
        "Navigation",
        [
            "📊 Executive Overview",
            "📁 Data Management",
            "⚖️ Reconciliation Ledger",
            "⚠️ Discrepancy Analysis",
            "🔍 Transaction Explorer",
            "📥 Reports & Export",
            "📖 Assumptions & Methodology",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("⚙️ RECONCILIATION CONTROLS")

    data_source_mode = st.radio(
        "Data Mode",
        ["Synthetic Nov 2026 Dataset", "Upload Custom CSV Files"],
        help="Use deterministic November 2026 sample data or upload platform and bank CSVs.",
    )

    rounding_tolerance = st.slider(
        "Rounding Tolerance (₹)",
        min_value=0.00,
        max_value=1.00,
        value=0.05,
        step=0.01,
        help="Allowable variance between platform amount and bank settlement before flagging as an amount mismatch.",
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Reset Seed", use_container_width=True):
            generate_datasets(output_dir="data", seed=42)
            st.cache_data.clear()
            st.rerun()
    with col_btn2:
        new_theme = "dark" if st.session_state.theme == "light" else "light"
        theme_label = "🌙 Dark" if st.session_state.theme == "light" else "☀️ Light"
        if st.button(theme_label, use_container_width=True):
            st.session_state.theme = new_theme
            st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 11px; color: #64748b;">
            <strong>Period:</strong> November 2026<br>
            <strong>Currency:</strong> INR (₹)<br>
            <strong>Precision:</strong> Python Decimal
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# Load Data & Validation
# ---------------------------------------------------------
df_transactions = None
df_settlements = None
custom_upload_active = data_source_mode == "Upload Custom CSV Files"

if not custom_upload_active:
    df_transactions, df_settlements = load_or_generate_sample_data(seed=42)
else:
    # If custom files uploaded via Data Management or session, use them
    if "custom_txn_df" in st.session_state and "custom_set_df" in st.session_state:
        df_transactions = st.session_state.custom_txn_df
        df_settlements = st.session_state.custom_set_df
    else:
        # Fallback to sample data with a banner prompt in Data Management tab
        df_transactions, df_settlements = load_or_generate_sample_data(seed=42)

# Execute Data Validation
val_txn = validate_transactions(df_transactions)
val_set = validate_settlements(df_settlements)

# Run Reconciliation Engine
engine = ReconciliationEngine(
    rounding_tolerance=Decimal(str(rounding_tolerance)),
    period_start="2026-11-01",
    period_end="2026-11-30",
)
items, summary = engine.reconcile(
    df_transactions,
    df_settlements,
    val_txn=val_txn,
    val_set=val_set,
)
df_items = pd.DataFrame([it.to_dict() for it in items])

# ---------------------------------------------------------
# HEADER COMPONENT
# ---------------------------------------------------------
header_status_text = (
    f"● Audit Complete: {summary.total_platform_transactions} Platform Records | {summary.total_discrepancies_count} Exceptions Detected"
    if summary.total_discrepancies_count > 0
    else "● All Platform Transactions Reconciled (0 Exceptions)"
)

st.markdown(
    f"""
    <div class="payrecon-header">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
            <div>
                <h1>💳 PayRecon</h1>
                <p>Intelligent Payment Reconciliation System — High-Precision Platform vs Bank Settlement Audit</p>
                <div>
                    <span class="badge-pill">📅 Accounting Period: November 2026</span>
                    <span class="badge-pill">💱 Currency: INR (₹)</span>
                    <span class="badge-pill">⚙️ Tolerance: ₹{rounding_tolerance:.2f}</span>
                    <span class="badge-pill" style="background: rgba(16, 185, 129, 0.25); border-color: rgba(16, 185, 129, 0.4);">{header_status_text}</span>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Header Run Action Bar
h_col1, h_col2 = st.columns([5, 1])
with h_col2:
    if st.button("🚀 Re-Run Audit", use_container_width=True, type="primary"):
        st.session_state.reconcile_trigger += 1
        st.toast("Reconciliation Engine re-executed with updated parameters!", icon="✅")
        st.rerun()

# =========================================================
# SECTION 1: EXECUTIVE OVERVIEW
# =========================================================
if nav_section == "📊 Executive Overview":
    st.subheader("Executive Financial Summary & KPI Cards")

    # 9 Core KPI Cards
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
    with r1_col1:
        st.markdown(
            f"""
            <div class="kpi-card border-blue">
                <div class="kpi-title">1. Total Platform Transactions</div>
                <div class="kpi-value">{summary.total_platform_transactions}</div>
                <div class="kpi-subtitle">Total platform ledger records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1_col2:
        st.markdown(
            f"""
            <div class="kpi-card border-blue">
                <div class="kpi-title">2. Expected Payment Amount</div>
                <div class="kpi-value">₹{summary.expected_payment_amount:,.2f}</div>
                <div class="kpi-subtitle">Success payments in Nov 2026</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1_col3:
        st.markdown(
            f"""
            <div class="kpi-card border-green">
                <div class="kpi-title">3. Valid Bank Settlements</div>
                <div class="kpi-value">₹{summary.actual_valid_settlement_amount:,.2f}</div>
                <div class="kpi-subtitle">Cleared in Nov (excl. dups/Dec)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1_col4:
        diff_color = "border-red" if summary.total_net_difference > 0 else "border-green"
        st.markdown(
            f"""
            <div class="kpi-card {diff_color}">
                <div class="kpi-title">9. Total Financial Discrepancy</div>
                <div class="kpi-value">₹{summary.total_net_difference:,.2f}</div>
                <div class="kpi-subtitle">Gross expected vs actual variance</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    r2_col1, r2_col2, r2_col3, r2_col4, r2_col5 = st.columns(5)
    with r2_col1:
        st.markdown(
            f"""
            <div class="kpi-card border-green">
                <div class="kpi-title">4. Matched Transactions</div>
                <div class="kpi-value">{summary.matched_count}</div>
                <div class="kpi-subtitle">₹{summary.matched_amount:,.2f} reconciled</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_col2:
        st.markdown(
            f"""
            <div class="kpi-card border-amber">
                <div class="kpi-title">5. Late Settlements</div>
                <div class="kpi-value">{summary.late_settlement_count}</div>
                <div class="kpi-subtitle">Timing diff: ₹{summary.late_settlement_amount:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_col3:
        st.markdown(
            f"""
            <div class="kpi-card border-red">
                <div class="kpi-title">6. Missing Settlements</div>
                <div class="kpi-value">{summary.missing_settlement_count}</div>
                <div class="kpi-subtitle">Pending: ₹{summary.missing_settlement_amount:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_col4:
        st.markdown(
            f"""
            <div class="kpi-card border-purple">
                <div class="kpi-title">7. Duplicate Entries</div>
                <div class="kpi-value">{summary.duplicate_settlement_count}</div>
                <div class="kpi-subtitle">Protected: ₹{summary.duplicate_settlement_amount_prevented:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_col5:
        st.markdown(
            f"""
            <div class="kpi-card border-red">
                <div class="kpi-title">8. Unmatched Refunds</div>
                <div class="kpi-value">{summary.unmatched_refund_count}</div>
                <div class="kpi-subtitle">Orphans: ₹{summary.unmatched_refund_amount:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 5 Interactive Plotly Visualizations
    st.subheader("📈 Interactive Analytics & Clearing Trends")
    c_row1_col1, c_row1_col2 = st.columns(2)

    with c_row1_col1:
        # Chart 1: Matched vs Unmatched Transactions
        matched_total = summary.matched_count + summary.rounding_discrepancy_count
        labels = [
            "Fully Matched",
            "Late Settlement (Timing)",
            "Missing Settlement",
            "Amount Mismatch",
            "Duplicate Settlement",
            "Unmatched Refund",
        ]
        values = [
            matched_total,
            summary.late_settlement_count,
            summary.missing_settlement_count,
            summary.amount_mismatch_count,
            summary.duplicate_settlement_count,
            summary.unmatched_refund_count,
        ]
        colors = ["#10b981", "#f59e0b", "#ef4444", "#f97316", "#8b5cf6", "#06b6d4"]

        if sum(values) > 0:
            fig_donut = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.55,
                        marker=dict(colors=colors),
                        textinfo="label+percent",
                        insidetextorientation="radial",
                    )
                ]
            )
            fig_donut.update_layout(
                title="1. Matched vs Unmatched Transactions",
                title_font_size=15,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25),
                margin=dict(l=20, r=20, t=40, b=20),
                height=360,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No transaction data available.")

    with c_row1_col2:
        # Chart 2: Discrepancy Categories
        cat_counts = (
            df_items[df_items["Is Discrepancy"] == True]["Issue Category"]
            .value_counts()
            .reset_index()
        )
        cat_counts.columns = ["Issue Category", "Count"]

        if not cat_counts.empty:
            fig_bar = px.bar(
                cat_counts,
                x="Count",
                y="Issue Category",
                orientation="h",
                color="Issue Category",
                color_discrete_sequence=["#ef4444", "#f59e0b", "#8b5cf6", "#06b6d4", "#eab308", "#ec4899"],
                title="2. Discrepancy Categories Distribution",
            )
            fig_bar.update_layout(
                title_font_size=15,
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
                height=360,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.success("🎉 All records matched cleanly! Zero discrepancies.")

    c_row2_col1, c_row2_col2 = st.columns(2)

    with c_row2_col1:
        # Chart 3: Daily Transaction vs Settlement Trends
        df_txn_daily = df_transactions.copy()
        df_txn_daily["transaction_date"] = pd.to_datetime(df_txn_daily["transaction_date"], errors="coerce")
        txn_day_counts = (
            df_txn_daily.groupby(df_txn_daily["transaction_date"].dt.strftime("%Y-%m-%d"))
            .size()
            .reset_index(name="Platform Transactions")
        )

        df_set_daily = df_settlements.copy()
        df_set_daily["settlement_date"] = pd.to_datetime(df_set_daily["settlement_date"], errors="coerce")
        set_day_counts = (
            df_set_daily.groupby(df_set_daily["settlement_date"].dt.strftime("%Y-%m-%d"))
            .size()
            .reset_index(name="Bank Settlements")
        )

        daily_merged = pd.merge(
            txn_day_counts,
            set_day_counts,
            left_on="transaction_date",
            right_on="settlement_date",
            how="outer",
        )
        daily_merged["Date"] = daily_merged["transaction_date"].combine_first(daily_merged["settlement_date"]).astype(str)
        daily_merged["Platform Transactions"] = daily_merged["Platform Transactions"].fillna(0).astype(int)
        daily_merged["Bank Settlements"] = daily_merged["Bank Settlements"].fillna(0).astype(int)
        daily_merged = daily_merged.sort_values("Date")

        if not daily_merged.empty and len(daily_merged["Date"].dropna()) > 0:
            fig_timeline = go.Figure()
            fig_timeline.add_trace(
                go.Scatter(
                    x=daily_merged["Date"],
                    y=daily_merged["Platform Transactions"],
                    mode="lines+markers",
                    name="Platform Transactions",
                    line=dict(color="#2563eb", width=2.5),
                )
            )
            fig_timeline.add_trace(
                go.Scatter(
                    x=daily_merged["Date"],
                    y=daily_merged["Bank Settlements"],
                    mode="lines+markers",
                    name="Bank Settlements",
                    line=dict(color="#10b981", width=2.5, dash="dash"),
                )
            )
            fig_timeline.update_layout(
                title="3. Daily Transaction vs Settlement Clearing Trends",
                title_font_size=15,
                xaxis_title="Date",
                yaxis_title="Record Count",
                margin=dict(l=20, r=20, t=40, b=20),
                height=360,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("No timeline trend data available.")

    with c_row2_col2:
        # Chart 4: Expected vs Actual Settlement Amount
        comp_categories = [
            "Expected Platform Volume",
            "Valid Bank Settled",
            "Matched Principal",
            "Late (Dec Timing)",
            "Missing Unsettled",
            "Duplicates Prevented",
        ]
        comp_values = [
            float(summary.expected_payment_amount),
            float(summary.actual_valid_settlement_amount),
            float(summary.matched_amount),
            float(summary.late_settlement_amount),
            float(summary.missing_settlement_amount),
            float(summary.duplicate_settlement_amount_prevented),
        ]
        bar_colors = ["#1e3a8a", "#10b981", "#059669", "#f59e0b", "#ef4444", "#8b5cf6"]

        fig_compare = go.Figure(
            go.Bar(
                x=comp_categories,
                y=comp_values,
                marker=dict(color=bar_colors),
                text=[f"₹{v:,.0f}" for v in comp_values],
                textposition="auto",
            )
        )
        fig_compare.update_layout(
            title="4. Expected vs Actual Settlement Amount Comparison (₹)",
            title_font_size=15,
            yaxis_title="Amount (INR)",
            margin=dict(l=20, r=20, t=40, b=20),
            height=360,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    # Chart 5: Financial Reconciliation Summary (Component Waterfall)
    st.markdown("#### 5. Financial Reconciliation Ledger Breakdown")
    fig_waterfall = go.Figure(
        go.Waterfall(
            name="Ledger Flow",
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "relative", "total"],
            x=[
                "Matched Principal",
                "Late Settlement (Dec)",
                "Missing Settlement",
                "Amount Mismatches",
                "Rounding Variances",
                "Total Expected Volume",
            ],
            textposition="outside",
            text=[
                f"+₹{float(summary.matched_amount):,.0f}",
                f"+₹{float(summary.late_settlement_amount):,.0f}",
                f"+₹{float(summary.missing_settlement_amount):,.0f}",
                f"+₹{abs(float(summary.amount_mismatch_diff)):,.0f}",
                f"{float(summary.aggregate_rounding_discrepancy):+,.2f}",
                f"₹{float(summary.expected_payment_amount):,.0f}",
            ],
            y=[
                float(summary.matched_amount),
                float(summary.late_settlement_amount),
                float(summary.missing_settlement_amount),
                abs(float(summary.amount_mismatch_diff)),
                float(summary.aggregate_rounding_discrepancy),
                0,
            ],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    )
    fig_waterfall.update_layout(
        title="Financial Volume Reconciliation Walk (INR)",
        title_font_size=14,
        height=340,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_waterfall, use_container_width=True)

# =========================================================
# SECTION 2: DATA MANAGEMENT & INGESTION
# =========================================================
elif nav_section == "📁 Data Management":
    st.subheader("📁 Dataset Management, Preview & Upload Center")
    st.markdown(
        "Manage, preview, validate, and download synthetic sample files or upload enterprise custom datasets."
    )

    dm_tab1, dm_tab2 = st.tabs(["⚡ Synthetic Generator & Downloads", "📤 Custom CSV Upload & Validation"])

    with dm_tab1:
        st.markdown("#### Generate & Download Reproducible November 2026 Datasets")
        st.markdown(
            "Use the built-in generator with fixed seed 42 to plant all 4 assessment anomalies: "
            "**Late Settlement**, **Aggregate Rounding Difference**, **Duplicate Entry**, and **Unmatched Refund**."
        )

        gen_c1, gen_c2, gen_c3 = st.columns([2, 2, 2])
        with gen_c1:
            seed_val = st.number_input("Random Generator Seed", min_value=1, max_value=99999, value=42)
        with gen_c2:
            num_txns = st.number_input("Base Normal Transactions", min_value=10, max_value=200, value=45)
        with gen_c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚙️ Generate Datasets", use_container_width=True):
                generate_datasets(output_dir="data", seed=int(seed_val), num_normal_txns=int(num_txns))
                st.cache_data.clear()
                st.success(f"Datasets generated successfully with seed {seed_val}!")
                st.rerun()

        st.markdown("---")
        st.markdown("##### 📥 Direct Sample CSV Downloads")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            with open("data/transactions.csv", "rb") as f:
                st.download_button(
                    label="⬇️ Download Sample transactions.csv",
                    data=f.read(),
                    file_name="transactions.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        with d_col2:
            with open("data/settlements.csv", "rb") as f:
                st.download_button(
                    label="⬇️ Download Sample settlements.csv",
                    data=f.read(),
                    file_name="settlements.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        st.markdown("---")
        st.markdown("##### 👁️ Sample Datasets Live Preview")
        prev_col1, prev_col2 = st.columns(2)
        with prev_col1:
            st.markdown(f"**Platform Transactions (`transactions.csv`)** — {len(df_transactions)} rows")
            st.dataframe(df_transactions.head(10), use_container_width=True, hide_index=True)
        with prev_col2:
            st.markdown(f"**Bank Settlements (`settlements.csv`)** — {len(df_settlements)} rows")
            st.dataframe(df_settlements.head(10), use_container_width=True, hide_index=True)

    with dm_tab2:
        st.markdown("#### Upload Custom Platform & Bank Settlement CSVs")
        st.markdown(
            "Upload your own enterprise transaction and settlement files. The validator performs non-destructive schema, "
            "currency, date, and duplicate checks without modifying or dropping any invalid records."
        )

        up_c1, up_c2 = st.columns(2)
        with up_c1:
            up_txn_file = st.file_uploader("1. Platform Transactions CSV", type=["csv"], key="up_txn_key")
        with up_c2:
            up_set_file = st.file_uploader("2. Bank Settlements CSV", type=["csv"], key="up_set_key")

        if up_txn_file and up_set_file:
            try:
                custom_df_t = pd.read_csv(up_txn_file)
                custom_df_s = pd.read_csv(up_set_file)

                # Validate uploaded files
                v_res_t = validate_transactions(custom_df_t)
                v_res_s = validate_settlements(custom_df_s)

                st.markdown("##### Ingestion Validation Results")
                val_res_c1, val_res_c2 = st.columns(2)
                with val_res_c1:
                    if v_res_t.is_valid:
                        st.success(f"✓ Platform Transactions: {v_res_t.summary()}")
                    else:
                        st.warning(f"⚠ Platform Transactions: {v_res_t.summary()}")
                        if v_res_t.errors:
                            st.dataframe(
                                pd.DataFrame([{"Row": e.row_index, "Col": e.column, "Error": e.message} for e in v_res_t.errors[:5]]),
                                use_container_width=True,
                                hide_index=True,
                            )
                with val_res_c2:
                    if v_res_s.is_valid:
                        st.success(f"✓ Bank Settlements: {v_res_s.summary()}")
                    else:
                        st.warning(f"⚠ Bank Settlements: {v_res_s.summary()}")
                        if v_res_s.errors:
                            st.dataframe(
                                pd.DataFrame([{"Row": e.row_index, "Col": e.column, "Error": e.message} for e in v_res_s.errors[:5]]),
                                use_container_width=True,
                                hide_index=True,
                            )

                if st.button("🚀 Reconcile Uploaded Datasets", type="primary", use_container_width=True):
                    st.session_state.custom_txn_df = custom_df_t
                    st.session_state.custom_set_df = custom_df_s
                    st.success("Uploaded files activated! Switch to Executive Overview to view results.")
                    st.rerun()

            except Exception as e:
                st.error(f"Error parsing uploaded files: {e}")
        else:
            st.info("Upload both files above to preview and reconcile.")

# =========================================================
# SECTION 3: RECONCILIATION LEDGER
# =========================================================
elif nav_section == "⚖️ Reconciliation Ledger":
    st.subheader("⚖️ Financial Ledger & Settlement Walk")

    l_col1, l_col2 = st.columns([3, 2])
    with l_col1:
        st.markdown("#### Complete Financial Reconciliation Ledger")
        st.markdown(
            f"""
            <table class="fin-ledger-table">
                <thead>
                    <tr>
                        <th>Financial Category</th>
                        <th>Amount (INR)</th>
                        <th>Operational Impact & Explanation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Expected Gross Platform Volume</strong></td>
                        <td><strong>₹{summary.expected_payment_amount:,.2f}</strong></td>
                        <td>Sum of all SUCCESS platform payments in November 2026</td>
                    </tr>
                    <tr>
                        <td>Actual Valid Bank Settlements</td>
                        <td>₹{summary.actual_valid_settlement_amount:,.2f}</td>
                        <td>Gross valid bank credit received within November 2026</td>
                    </tr>
                    <tr class="ledger-row-highlight">
                        <td><strong>Gross Month-End Variance</strong></td>
                        <td><strong>₹{summary.total_net_difference:,.2f}</strong></td>
                        <td>Expected volume minus November bank settlements</td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;↳ <em>Less: Late Settlement (Dec Spillover)</em></td>
                        <td>₹{summary.late_settlement_amount:,.2f}</td>
                        <td>Timing difference settled in December (Anomaly A)</td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;↳ <em>Less: Permanent Missing Settlements</em></td>
                        <td>₹{summary.missing_settlement_amount:,.2f}</td>
                        <td>Platform payments not settled by bank</td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;↳ <em>Less: Amount Mismatches</em></td>
                        <td>₹{abs(summary.amount_mismatch_diff):,.2f}</td>
                        <td>Differences exceeding tolerance of ₹{summary.rounding_tolerance}</td>
                    </tr>
                    <tr>
                        <td>&nbsp;&nbsp;↳ <em>Less: Aggregate Rounding Discrepancy</em></td>
                        <td>₹{summary.aggregate_rounding_discrepancy:+.2f}</td>
                        <td>Net accumulation of penny variances (Anomaly B)</td>
                    </tr>
                    <tr class="ledger-row-highlight">
                        <td><strong>Duplicate Settlements Prevented</strong></td>
                        <td><strong>₹{summary.duplicate_settlement_amount_prevented:,.2f}</strong></td>
                        <td>Prevented from inflating bank totals (Anomaly C)</td>
                    </tr>
                </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )

    with l_col2:
        st.markdown("#### 🔄 Refund Segregation (Reported Separately)")
        st.markdown(
            f"""
            <table class="fin-ledger-table">
                <thead>
                    <tr>
                        <th>Refund Category</th>
                        <th>Count</th>
                        <th>Amount (INR)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Valid Matched Bank Refunds</td>
                        <td>{summary.matched_refund_count}</td>
                        <td>₹{summary.matched_refund_amount:,.2f}</td>
                    </tr>
                    <tr style="background-color: rgba(239, 68, 68, 0.1);">
                        <td><strong>Unmatched Orphan Refunds (D)</strong></td>
                        <td><strong>{summary.unmatched_refund_count}</strong></td>
                        <td><strong>₹{summary.unmatched_refund_amount:,.2f}</strong></td>
                    </tr>
                    <tr class="ledger-row-highlight">
                        <td><strong>Total Bank Gross Refunds</strong></td>
                        <td><strong>{summary.matched_refund_count + summary.unmatched_refund_count}</strong></td>
                        <td><strong>₹{summary.total_refund_amount:,.2f}</strong></td>
                    </tr>
                </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )
        st.info(
            f"ℹ️ **Accounting Principle**: In accordance with fintech audit standards, bank refunds "
            f"(₹{summary.total_refund_amount:,.2f}) are reported separately and not netted against gross platform "
            f"payment collections."
        )

        st.metric(
            label="Reconciliation Success Rate",
            value=f"{summary.reconciliation_rate_pct:.1f}%",
            delta=f"{summary.matched_count + summary.rounding_discrepancy_count} of {summary.total_platform_transactions - summary.failed_txn_count} eligible",
        )

# =========================================================
# SECTION 4: DISCREPANCY ANALYSIS
# =========================================================
elif nav_section == "⚠️ Discrepancy Analysis":
    st.subheader("⚠️ Discrepancy Analysis & Root Cause Center")
    st.markdown(
        "Detailed inspection of all non-matching records, distinguishing timing differences, "
        "rounding variances, duplicate entries, and orphan refunds."
    )

    df_discrepancies = df_items[df_items["Is Discrepancy"] == True].copy()

    # Category Filter
    issue_cats = ["All Categories"] + sorted(list(df_discrepancies["Issue Category"].unique()))
    selected_cat = st.selectbox("Filter Discrepancies by Category:", issue_cats)

    if selected_cat != "All Categories":
        filtered_disc = df_discrepancies[df_discrepancies["Issue Category"] == selected_cat]
    else:
        filtered_disc = df_discrepancies

    st.markdown(f"**Showing {len(filtered_disc)} discrepancy record(s)**")

    display_disc_cols = [
        "Transaction ID",
        "Platform Amount (INR)",
        "Bank Amount (INR)",
        "Difference (INR)",
        "Transaction Date",
        "Settlement Date",
        "Issue Category",
        "Explanation",
    ]
    st.dataframe(
        filtered_disc[display_disc_cols],
        use_container_width=True,
        hide_index=True,
    )

    # 4 Mandatory Anomalies Audit Inspection Cards
    st.markdown("---")
    st.subheader("🎯 Mandatory Anomalies Audit Inspection")
    sc1, sc2 = st.columns(2)
    with sc1:
        with st.expander("📌 A. LATE SETTLEMENT (Timing Difference)", expanded=True):
            late_items = df_items[df_items["Reconciliation Status"] == ReconciliationStatus.LATE_SETTLEMENT]
            if not late_items.empty:
                for _, r in late_items.iterrows():
                    st.markdown(
                        f"""
                        - **Transaction ID**: `{r['Transaction ID']}`
                        - **Platform Date**: `{r['Transaction Date']}` (November 2026)
                        - **Settlement Date**: `{r['Settlement Date']}` (December 2026)
                        - **Amount**: ₹{float(r['Platform Amount (INR)'] or 0):,.2f}
                        - **Why it occurred**: Platform customer paid on month-end; bank batch clearing closed in December.
                        - **Audit Classification**: **Timing difference** — funds received in December, so transaction is not permanently missing.
                        """
                    )
            else:
                st.write("No late settlements detected.")

        with st.expander("📌 B. ROUNDING DIFFERENCE (Aggregate Variance)", expanded=True):
            rnd_items = df_items[df_items["Reconciliation Status"] == ReconciliationStatus.AGGREGATE_ROUNDING]
            st.markdown(
                f"""
                - **Configured Tolerance**: ₹{summary.rounding_tolerance:.2f} per transaction.
                - **Detected Records with Rounding Differences**: {len(rnd_items)}
                - **Net Aggregate Rounding Discrepancy**: **₹{summary.aggregate_rounding_discrepancy:+.2f}**
                - **Why it occurred**: Bank core clearing systems apply floating-point rounding or truncate fractional paisas per batch.
                - **Reconciliation Treatment**: Individual differences within tolerance are approved with a rounding variance tag; aggregate diff is posted to the ledger rounding adjustment account.
                """
            )
            if not rnd_items.empty:
                st.dataframe(
                    rnd_items[["Transaction ID", "Platform Amount (INR)", "Bank Amount (INR)", "Difference (INR)", "Explanation"]],
                    use_container_width=True,
                    hide_index=True,
                )

    with sc2:
        with st.expander("📌 C. DUPLICATE ENTRY (Double-Counting Prevention)", expanded=True):
            dup_items = df_items[df_items["Reconciliation Status"] == ReconciliationStatus.DUPLICATE_SETTLEMENT]
            if not dup_items.empty:
                for _, r in dup_items.iterrows():
                    st.markdown(
                        f"""
                        - **Duplicate Settlement ID**: `{r['Settlement ID']}`
                        - **Transaction ID**: `{r['Transaction ID']}`
                        - **Duplicated Amount**: ₹{float(r['Bank Amount (INR)'] or 0):,.2f}
                        - **Why it occurred**: Bank batch transmitted twice or re-cleared due to network timeout retry.
                        - **Engine Action**: **Double-counting prevented!** Duplicate entry is flagged and completely excluded from valid settlement totals.
                        """
                    )
            else:
                st.write("No duplicate settlements detected.")

        with st.expander("📌 D. UNMATCHED REFUND (Orphan Refund)", expanded=True):
            unmatched_ref = df_items[df_items["Reconciliation Status"] == ReconciliationStatus.UNMATCHED_REFUND]
            if not unmatched_ref.empty:
                for _, r in unmatched_ref.iterrows():
                    st.markdown(
                        f"""
                        - **Settlement ID**: `{r['Settlement ID']}`
                        - **Referenced Original Txn ID**: `{r['Original Txn ID']}`
                        - **Refund Amount**: ₹{float(r['Bank Amount (INR)'] or 0):,.2f}
                        - **Why it occurred**: Bank processed a chargeback/refund referencing an identifier not recorded on this platform.
                        - **Audit Classification**: **Orphan Refund** — requires bank operations escalation.
                        """
                    )
            else:
                st.write("No unmatched refunds detected.")

# =========================================================
# SECTION 5: TRANSACTION EXPLORER
# =========================================================
elif nav_section == "🔍 Transaction Explorer":
    st.subheader("🔍 Transaction Explorer & Drill-Down Audit Trail")
    st.markdown("Search, filter, sort, and inspect every platform transaction and settlement with an auditable trail.")

    e_col1, e_col2, e_col3, e_col4, e_col5 = st.columns(5)
    with e_col1:
        search_id = st.text_input("Search ID:", "", placeholder="e.g. TXN-202611-0001")
    with e_col2:
        all_statuses = ["All Statuses"] + sorted(list(df_items["Reconciliation Status"].unique()))
        selected_status = st.selectbox("Status:", all_statuses)
    with e_col3:
        all_cats = ["All Categories"] + sorted(list(df_items["Issue Category"].unique()))
        selected_cat_exp = st.selectbox("Category:", all_cats)
    with e_col4:
        disc_filter = st.selectbox("Filter:", ["All Records", "Discrepancies Only", "Matched Only"])
    with e_col5:
        sort_by = st.selectbox("Sort By:", ["Date (Asc)", "Date (Desc)", "Amount (High-Low)", "Amount (Low-High)"])

    # Filtering logic
    filtered_exp = df_items.copy()
    if search_id.strip():
        term = search_id.strip().lower()
        filtered_exp = filtered_exp[
            filtered_exp["Transaction ID"].str.lower().str.contains(term, na=False)
            | filtered_exp["Settlement ID"].str.lower().str.contains(term, na=False)
        ]
    if selected_status != "All Statuses":
        filtered_exp = filtered_exp[filtered_exp["Reconciliation Status"] == selected_status]
    if selected_cat_exp != "All Categories":
        filtered_exp = filtered_exp[filtered_exp["Issue Category"] == selected_cat_exp]
    if disc_filter == "Discrepancies Only":
        filtered_exp = filtered_exp[filtered_exp["Is Discrepancy"] == True]
    elif disc_filter == "Matched Only":
        filtered_exp = filtered_exp[filtered_exp["Is Discrepancy"] == False]

    # Sorting logic
    if sort_by == "Date (Asc)":
        filtered_exp = filtered_exp.sort_values("Transaction Date", ascending=True)
    elif sort_by == "Date (Desc)":
        filtered_exp = filtered_exp.sort_values("Transaction Date", ascending=False)
    elif sort_by == "Amount (High-Low)":
        filtered_exp = filtered_exp.sort_values("Platform Amount (INR)", ascending=False)
    elif sort_by == "Amount (Low-High)":
        filtered_exp = filtered_exp.sort_values("Platform Amount (INR)", ascending=True)

    st.markdown(f"**Showing {len(filtered_exp)} record(s)**")

    st.dataframe(
        filtered_exp[[
            "Transaction ID",
            "Settlement ID",
            "Platform Amount (INR)",
            "Bank Amount (INR)",
            "Difference (INR)",
            "Transaction Date",
            "Settlement Date",
            "Reconciliation Status",
            "Issue Category",
        ]],
        use_container_width=True,
        hide_index=True,
    )

    # Individual Record Drill-Down
    st.markdown("---")
    st.subheader("🔎 Individual Record Audit Drill-Down")
    available_ids = filtered_exp["Transaction ID"].unique().tolist()
    if available_ids:
        selected_tid = st.selectbox("Select a Transaction ID to view complete audit trail:", available_ids)
        rec_matches = df_items[df_items["Transaction ID"] == selected_tid]
        for _, rec in rec_matches.iterrows():
            p_val = rec.get("Platform Amount (INR)")
            b_val = rec.get("Bank Amount (INR)")
            d_val = rec.get("Difference (INR)")
            p_amt_disp = f"₹{float(p_val):,.2f}" if pd.notna(p_val) and p_val is not None else "N/A"
            b_amt_disp = f"₹{float(b_val):,.2f}" if pd.notna(b_val) and b_val is not None else "N/A"
            diff_disp = f"₹{float(d_val):,.2f}" if pd.notna(d_val) and d_val is not None else "₹0.00"

            st.markdown(
                f"""
                <div style="background: {card_bg}; border: 1px solid {border_color}; border-radius: 10px; padding: 20px; margin-top: 10px;">
                    <h4 style="margin-top:0; color: #2563eb;">Audit Details: {rec['Transaction ID']} ({rec['Reconciliation Status']})</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <p><strong>Platform Transaction Date:</strong> {rec['Transaction Date']}</p>
                            <p><strong>Platform Amount:</strong> {p_amt_disp}</p>
                            <p><strong>Bank Settlement ID:</strong> {rec['Settlement ID']}</p>
                            <p><strong>Bank Settlement Date:</strong> {rec['Settlement Date']}</p>
                        </div>
                        <div>
                            <p><strong>Bank Settled Amount:</strong> {b_amt_disp}</p>
                            <p><strong>Variance (Bank - Platform):</strong> {diff_disp}</p>
                            <p><strong>Issue Category:</strong> {rec['Issue Category']}</p>
                            <p><strong>Original Txn Reference:</strong> {rec['Original Txn ID']}</p>
                        </div>
                    </div>
                    <div style="margin-top: 15px; padding: 12px; background: {table_row_alt}; border-left: 4px solid #2563eb; border-radius: 4px;">
                        <strong>Audit Explanation:</strong><br>{rec['Explanation']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# =========================================================
# SECTION 6: REPORTS & EXPORT
# =========================================================
elif nav_section == "📥 Reports & Export":
    st.subheader("📥 Export Auditable Financial Reports")
    st.markdown(
        "Download dynamically generated CSV reports conforming to fintech month-end closing and compliance standards."
    )

    # 6 Reports Generated Dynamically
    full_rec_csv = generate_reconciliation_csv(items)
    matched_csv = generate_matched_csv(items)
    unmatched_csv = generate_unmatched_csv(items)
    duplicates_csv = generate_duplicates_csv(items)
    refunds_csv = generate_refunds_csv(items)
    summary_csv = generate_summary_csv(summary)

    rep_col1, rep_col2, rep_col3 = st.columns(3)
    with rep_col1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">1. Complete Reconciliation</div>
                <div class="kpi-value" style="font-size:16px;">Full Audit Ledger</div>
                <div class="kpi-subtitle">{len(items)} total records with statuses</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Full Reconciliation CSV",
            data=full_rec_csv,
            file_name="payrecon_full_reconciliation_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with rep_col2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">2. Matched Transactions</div>
                <div class="kpi-value" style="font-size:16px;">Verified 1:1 Matches</div>
                <div class="kpi-subtitle">{summary.matched_count + summary.rounding_discrepancy_count} matching records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Matched CSV",
            data=matched_csv,
            file_name="payrecon_matched_transactions_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with rep_col3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">3. Unmatched & Missing</div>
                <div class="kpi-value" style="font-size:16px;">Pending Bank Credits</div>
                <div class="kpi-subtitle">{summary.missing_settlement_count + summary.unmatched_settlement_count} missing records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Unmatched CSV",
            data=unmatched_csv,
            file_name="payrecon_unmatched_transactions_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    rep_col4, rep_col5, rep_col6 = st.columns(3)
    with rep_col4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">4. Duplicate Records</div>
                <div class="kpi-value" style="font-size:16px;">Excluded Double-Counts</div>
                <div class="kpi-subtitle">{summary.duplicate_settlement_count} duplicate settlement entries</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Duplicates CSV",
            data=duplicates_csv,
            file_name="payrecon_duplicate_records_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with rep_col5:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">5. Refund Discrepancies</div>
                <div class="kpi-value" style="font-size:16px;">Bank Refund Ledger</div>
                <div class="kpi-subtitle">{summary.matched_refund_count + summary.unmatched_refund_count} matched & orphan refunds</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Refunds CSV",
            data=refunds_csv,
            file_name="payrecon_refunds_discrepancy_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with rep_col6:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">6. Financial Summary</div>
                <div class="kpi-value" style="font-size:16px;">Executive Metrics</div>
                <div class="kpi-subtitle">High-level financial KPIs & aggregates</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download Summary CSV",
            data=summary_csv,
            file_name="payrecon_executive_summary_nov2026.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("📄 Live Report Preview")
    prev_type = st.radio(
        "Select Report to Preview:",
        ["Executive Summary", "Matched Transactions", "Duplicates Report", "Refunds Report"],
        horizontal=True,
    )
    if prev_type == "Executive Summary":
        st.dataframe(pd.read_csv(io.StringIO(summary_csv)), use_container_width=True, hide_index=True)
    elif prev_type == "Matched Transactions":
        st.dataframe(pd.read_csv(io.StringIO(matched_csv)).head(15), use_container_width=True, hide_index=True)
    elif prev_type == "Duplicates Report":
        st.dataframe(pd.read_csv(io.StringIO(duplicates_csv)), use_container_width=True, hide_index=True)
    elif prev_type == "Refunds Report":
        st.dataframe(pd.read_csv(io.StringIO(refunds_csv)), use_container_width=True, hide_index=True)

# =========================================================
# SECTION 7: ASSUMPTIONS & METHODOLOGY
# =========================================================
elif nav_section == "📖 Assumptions & Methodology":
    st.subheader("📖 Assumptions, Business Rules & Methodology")
    st.markdown(
        """
### 1. Reconciliation Period & Month-End Cutoff
- **Accounting Period**: November 1, 2026 to November 30, 2026.
- All successful platform payments recorded in November 2026 establish payment obligations expected to settle.
- Standard bank settlement operates on a **T+1 to T+2 clearing cycle**.

### 2. Settlement Timing & December Spillovers (Late Settlements)
- A payment authorized on November 29 or November 30 typically clears at the partner bank on December 1 or 2.
- **Rule**: When a successful November transaction matches a bank settlement dated in December 2026:
  - It is classified as a **Timing Difference (Late Settlement)**.
  - It is **not** flagged as permanently missing or defaulted.
  - It accounts for month-end in-transit funds.

### 3. Currency & High-Precision Decimal Math
- **Base Currency**: Indian Rupee (`INR`).
- All financial balances and calculations are evaluated strictly using Python's `decimal.Decimal` with 2 decimal places (`Decimal('0.01')`) and `ROUND_HALF_UP`.
- Standard IEEE floating-point representations (`float`) are prohibited in the core engine to avoid binary representation drift.

### 4. Rounding Tolerance & Aggregate Discrepancy
- **Individual Rounding Tolerance**: Configurable in the control panel (default: `₹0.05`).
- Transactions where `0 < |Difference| <= Tolerance` are classified as **Aggregate Rounding Discrepancy**.
- These variances represent penny differences arising from gateway service fees or rounding differences between platform ledger and bank core banking systems.
- The engine computes the **Aggregate Rounding Discrepancy** across all transactions to ensure small individual variances do not mask a large systemic leakage.

### 5. Treatment of Duplicate Bank Settlements
- When multiple bank settlements reference the same `transaction_id`:
  - The first settlement is accepted as the primary settlement.
  - Secondary settlements are classified as **Duplicate Bank Settlements**.
  - **Rule**: Duplicated amounts are excluded from valid settlement totals to prevent double-counting.

### 6. Treatment of Bank Refunds
- In compliance with financial accounting standards:
  - Bank refunds are **reported separately** from gross payment settlements.
  - Refunds are never subtracted directly from gross payment settlements without explicit categorization.
  - **Matched Refunds**: Refund records matching an original platform transaction ID.
  - **Unmatched Refunds (Orphan Refunds)**: Bank refunds referencing transaction IDs not found in platform records. These indicate manual bank adjustments, mistaken chargebacks, or external payments requiring operational escalation.

### 7. Treatment of Failed Platform Payments
- Transactions with platform status `FAILED` do not create payment settlement obligations.
- They are excluded from expected payment volume.
- If a bank unexpectedly settles a failed transaction, it is flagged as an **Unexpected Settlement for Failed Transaction**.

### 8. Known Limitations
- Multi-currency cross-border FX conversions are not currently modeled (single currency INR).
- Split partial settlements (e.g. 1 transaction settled across 2 distinct partial bank deposits) are treated as amount mismatches unless linked via a batch ID.
- Real-time instant UPI webhook reconciliation assumes T+0/T+1 bank ledger posting.
        """
    )
