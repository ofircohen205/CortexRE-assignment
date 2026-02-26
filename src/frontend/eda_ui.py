"""
frontend/eda_ui.py
==================
EDA interface components for the Streamlit frontend.
"""

from __future__ import annotations

import streamlit as st

def render_eda_tab(df):
    st.subheader("Exploratory Data Analysis")
    
    with st.expander("Data Quality Summary", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Records", len(df))
        missing_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
        c2.metric("Missing Values", f"{missing_pct:.2f}%")
        unique_props = df['property_name'].nunique()
        c3.metric("Properties Count", unique_props)

    properties = sorted([p for p in df['property_name'].unique() if p and p != 'None'])
    selected_property = st.selectbox("Focus on specific property", ["All Properties (Portfolio View)"] + properties)
    
    if selected_property == "All Properties (Portfolio View)":
        display_df = df
        is_all = True
    else:
        display_df = df[df['property_name'] == selected_property]
        is_all = False

    total_revenue = display_df.loc[display_df['ledger_type'] == 'revenue', 'profit'].sum()
    total_expenses = display_df.loc[display_df['ledger_type'] == 'expenses', 'profit'].sum()
    total_noi = total_revenue + total_expenses
    
    k1, k2, k3 = st.columns(3)
    if is_all:
        k1.metric("Total Properties", df['property_name'].nunique())
    else:
        k1.metric("Property Name", selected_property)
        
    k2.metric("Total Net Operating Income (NOI)", f"{total_noi:,.0f}")
    
    if is_all:
        k3.metric("Data Range", f"{df['date'].min().year} - {df['date'].max().year}")
    else:
        oer = (abs(total_expenses) / total_revenue * 100) if total_revenue != 0 else 0
        k3.metric("Operating Expense Ratio (OER)", f"{oer:.1f}%")

    st.divider()

    st.write(f"### {'Portfolio' if is_all else selected_property} Performance Over Time")
    monthly = display_df.groupby(['date', 'ledger_type'])['profit'].sum().unstack(fill_value=0).reset_index()
    monthly['NOI'] = monthly.get('revenue', 0) + monthly.get('expenses', 0)
    
    chart_data = monthly.rename(columns={'revenue': 'Revenue', 'expenses': 'Expenses'})
    chart_cols = ['Revenue', 'Expenses', 'NOI']
    available_cols = [c for c in chart_cols if c in chart_data.columns]
    
    selected_cols = st.multiselect(
        "Select metrics to display",
        options=available_cols,
        default=available_cols,
        key="metric_selector"
    )
    
    if not monthly.empty:
        if selected_cols:
            st.area_chart(chart_data.set_index('date')[selected_cols])
        else:
            st.info("Please select at least one metric to display the chart.")
    else:
        st.warning("No time-series data available for selection.")

    st.divider()

    t_col, l_col = st.columns(2)

    with t_col:
        st.write("### Top Tenants by Revenue")
        tenant_df = display_df[display_df['ledger_type'] == 'revenue'].groupby('tenant_name')['profit'].sum().sort_values(ascending=False).reset_index()
        tenant_df.columns = ['Tenant', 'Total Revenue']
        tenant_df = tenant_df[tenant_df['Tenant'].notna() & (tenant_df['Tenant'] != 'None')]
        if not tenant_df.empty:
            st.bar_chart(tenant_df.set_index('Tenant').head(10))
        else:
            st.info("No tenant-specific revenue records found.")

    with l_col:
        st.write("### Ledger Drill-down (Expenses)")
        drill_level = st.selectbox("Detail level", ["ledger_group", "ledger_category", "ledger_description"])
        exp_breakdown = display_df[display_df['ledger_type'] == 'expenses'].groupby(drill_level)['profit'].sum().abs().sort_values(ascending=False).head(10)
        if not exp_breakdown.empty:
            st.bar_chart(exp_breakdown)
        else:
            st.info("No expense records found.")

    st.divider()

    if is_all:
        st.write("### Portfolio-wide Comparisons")
        c1, c2 = st.columns(2)

        with c1:
            st.write("**NOI by Property**")
            prop_perf = df.groupby('property_name')['profit'].sum().sort_values(ascending=False).reset_index()
            prop_perf.columns = ['Property', 'NOI']
            st.bar_chart(prop_perf.set_index('Property').head(10))

        with c2:
            st.write("**Efficiency (OER) by Property**")
            rev_per_prop = df[df['ledger_type'] == 'revenue'].groupby('property_name')['profit'].sum()
            exp_per_prop = df[df['ledger_type'] == 'expenses'].groupby('property_name')['profit'].sum().abs()
            oer_per_prop = (exp_per_prop / rev_per_prop * 100).dropna().sort_values(ascending=False)
            if not oer_per_prop.empty:
                st.bar_chart(oer_per_prop.head(10))
            else:
                st.info("Insufficient data for OER comparison.")

        st.divider()
        st.write("### Expense Breakdown by Ledger Group")
        if 'ledger_group' not in display_df.columns:
            st.info("Ledger group data not available.")
        else:
            lg_expenses = (
                display_df[display_df['ledger_type'] == 'expenses']
                .groupby('ledger_group')['profit']
                .sum()
                .abs()
                .sort_values(ascending=False)
            )
            if not lg_expenses.empty:
                st.bar_chart(lg_expenses)
            else:
                st.info("No expense records found for ledger group breakdown.")

    else:
        st.write(f"### Expense Breakdown by Ledger Group — {selected_property}")
        if 'ledger_group' not in display_df.columns:
            st.info("Ledger group data not available.")
        else:
            lg_expenses = (
                display_df[display_df['ledger_type'] == 'expenses']
                .groupby('ledger_group')['profit']
                .sum()
                .abs()
                .sort_values(ascending=False)
            )
            if not lg_expenses.empty:
                st.bar_chart(lg_expenses)
            else:
                st.info("No expense records found for ledger group breakdown.")

        st.divider()
        st.write(f"### Tenant Revenue — {selected_property}")
        if 'tenant_name' in display_df.columns:
            tenant_rev = (
                display_df[
                    (display_df['ledger_type'] == 'revenue') &
                    display_df['tenant_name'].notna() &
                    (display_df['tenant_name'] != 'N/A')
                ]
                .groupby('tenant_name')['profit']
                .sum()
                .sort_values(ascending=False)
                .reset_index()
                .rename(columns={'tenant_name': 'Tenant', 'profit': 'Revenue'})
            )
            if not tenant_rev.empty:
                st.dataframe(tenant_rev.style.format({'Revenue': '{:,.2f}'}), use_container_width=True)
            else:
                st.info("No tenant revenue data for this property.")
        else:
            st.info("Tenant data not available in this dataset.")

        st.divider()
        st.write(f"### Top Expense Drivers — {selected_property}")
        cat_col = 'ledger_category' if 'ledger_category' in display_df.columns else None
        if cat_col:
            top_exp = (
                display_df[display_df['ledger_type'] == 'expenses']
                .groupby(cat_col)['profit']
                .sum()
                .sort_values()  # most negative first
                .head(5)
                .abs()
                .reset_index()
                .rename(columns={cat_col: 'Category', 'profit': 'Total Expense'})
            )
            if not top_exp.empty:
                st.dataframe(top_exp.style.format({'Total Expense': '{:,.2f}'}), use_container_width=True)
            else:
                st.info("No expense data recorded.")
        else:
            st.info("Ledger category data not available.")

    with st.expander(f"View {'Normalized' if is_all else 'Property'} Data Table"):
        st.dataframe(display_df, width="stretch")
