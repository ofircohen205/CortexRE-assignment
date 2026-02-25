"""
frontend/eda_ui.py
==================
EDA interface components for the Streamlit frontend.
"""

from __future__ import annotations

import streamlit as st

def render_eda_tab(df):
    st.subheader("Exploratory Data Analysis")
    
    # Property Selector
    properties = sorted(df['property_name'].unique())
    selected_property = st.selectbox("Focus on specific property", ["All Properties (Portfolio View)"] + properties)
    
    if selected_property == "All Properties (Portfolio View)":
        display_df = df
        is_all = True
    else:
        display_df = df[df['property_name'] == selected_property]
        is_all = False

    # Portfolio/Property KPIs
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

    # Monthly Trend
    st.write(f"### {'Portfolio' if is_all else selected_property} Performance Over Time")
    monthly = display_df.groupby(['date', 'ledger_type'])['profit'].sum().unstack(fill_value=0).reset_index()
    monthly['NOI'] = monthly.get('revenue', 0) + monthly.get('expenses', 0)
    
    # Rename for chart clarity
    chart_data = monthly.rename(columns={'revenue': 'Revenue', 'expenses': 'Expenses'})
    chart_cols = ['Revenue', 'Expenses', 'NOI']
    available_cols = [c for c in chart_cols if c in chart_data.columns]
    
    # Column selection
    selected_cols = st.multiselect(
        "Select metrics to display",
        options=available_cols,
        default=available_cols
    )
    
    if not monthly.empty:
        if selected_cols:
            st.area_chart(chart_data.set_index('date')[selected_cols])
        else:
            st.info("Please select at least one metric to display the chart.")
    else:
        st.warning("No time-series data available for selection.")

    st.divider()

    if is_all:
        # Portfolio specific: Property Performance
        st.write("### Top Properties by Net Operating Income")
        prop_perf = df.groupby('property_name')['profit'].sum().sort_values(ascending=False).reset_index()
        prop_perf.columns = ['Property', 'NOI']
        st.bar_chart(prop_perf.set_index('Property').head(10))
    else:
        # Property specific: Category Breakdown
        st.write(f"### Revenue & Expense Breakdown for {selected_property}")
        
        # Check which category column to use
        cat_col = 'ledger_category' if 'ledger_category' in display_df.columns else 'category'
        
        if cat_col not in display_df.columns:
            st.error(f"Column '{cat_col}' not found in dataset. Please check data normalization.")
            return

        c1, c2 = st.columns(2)
        
        with c1:
            rev_breakdown = display_df[display_df['ledger_type'] == 'revenue'].groupby(cat_col)['profit'].sum().sort_values(ascending=False)
            if not rev_breakdown.empty:
                st.write("**Revenue by Category**")
                st.bar_chart(rev_breakdown)
            else:
                st.info("No revenue data recorded.")
                
        with c2:
            exp_breakdown = display_df[display_df['ledger_type'] == 'expenses'].groupby(cat_col)['profit'].sum().abs().sort_values(ascending=False)
            if not exp_breakdown.empty:
                st.write("**Expenses by Category (Absolute)**")
                st.bar_chart(exp_breakdown)
            else:
                st.info("No expense data recorded.")

    # Raw Data filter
    with st.expander(f"View {'Normalized' if is_all else 'Property'} Data"):
        st.dataframe(display_df, width="stretch")
