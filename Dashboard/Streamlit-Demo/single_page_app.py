# pip install -r requirements.txt
# to install the required packages

import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.api as sm


# Load and prepare data
@st.cache_data
def load_data():
    df = pd.read_csv('../../Data/WARIS.CSV')
    df['Date'] = pd.to_datetime(df[['Year', 'Month']].assign(DAY=1))
    df['Year'] = df['Date'].dt.year
    return df

df = load_data()

# Sidebar navigation
with st.sidebar:
    selected = option_menu("Waris Dashboard", 
                           ["Dashboard", "Revenue & Expen Trends", "Operational Metrics", "Efficiency Analysis", "Operational Details", "Predictive Analytics"],
                           icons=['house-fill', 'bar-chart-line', 'sliders', 'activity', 'table', 'graph-up'],
                           default_index=0)

# Dashboard Sections
if selected == "Dashboard":
    st.title("Key Metrics Overview")
    metrics_layout = st.columns(4)

    # Calculate metrics
    total_revenue = df.groupby('Year')['Total Operating Revenues'].sum().iloc[-1]
    total_expenditures = df.groupby('Year')['Total Operating Expenditures'].sum().iloc[-1]
    collection_efficiency = df['Collection Efficiency'].mean()
    average_personnel_expense = df['Personnel Expenditure as Percentage of O&M Costs'].mean()

    # Use markdown to enhance visual presentation with HTML and inline CSS
    metrics_layout[0].markdown(f"<div style='text-align: center; color: #4CAF50;'><span style='font-size: 2em;'>${total_revenue:,.0f}</span><br>Total Revenue", unsafe_allow_html=True)
    metrics_layout[1].markdown(f"<div style='text-align: center; color: #FF9800;'><span style='font-size: 2em;'>${total_expenditures:,.0f}</span><br>Total Expenditures</div>", unsafe_allow_html=True)
    metrics_layout[2].markdown(f"<div style='text-align: center; color: #2196F3;'><span style='font-size: 2em;'>{collection_efficiency:.2f}%</span><br>Collection Efficiency</div>", unsafe_allow_html=True)
    metrics_layout[3].markdown(f"<div style='text-align: center; color: #F44336;'><span style='font-size: 2em;'>{average_personnel_expense:.2f}%</span><br>Avg Personnel Exp %</div>", unsafe_allow_html=True)
   
    st.divider()


    # Revenue vs Expenditure Scatter Plot
    st.header("Revenue vs. Expenditure Over Time")
    fig = px.scatter(df, x='Total Operating Revenues', y='Total Operating Expenditures', color='Year', 
                     trendline="ols", labels={"x": "Operating Revenues", "y": "Operating Expenditures"})
    st.plotly_chart(fig, width="stretch")

    st.header("Zone-Wise Revenue Comparison")
    revenue_comparison = df.groupby(['Year', 'Zone'])['Total Operating Revenues'].sum().reset_index()
    fig2 = px.bar(revenue_comparison, x='Zone', y='Total Operating Revenues', color='Year', barmode='group',
                  labels={"Total Operating Revenues": "Revenue"})
    st.plotly_chart(fig2, width="stretch")

    st.header("Efficiency Distribution")
    fig3 = px.histogram(df, x='Collection Efficiency', nbins=30, title="Distribution of Collection Efficiency")
    st.plotly_chart(fig3, width="stretch")

if selected == "Revenue & Expen Trends":
    st.title("Monthly Revenue and Expenditure Chart")
    fig = px.line(df, x='Date', y=['Total Operating Revenues', 'Total Operating Expenditures'],
                  labels={'value': 'USD', 'variable': 'Type'})
    st.plotly_chart(fig, width="stretch")

    st.title("Year-on-Year Comparison Chart")
        # Group by year and sum only the necessary columns
    yearly_data = df.groupby(df['Date'].dt.year).agg({
            'Total Operating Revenues': 'sum',
            'Total Operating Expenditures': 'sum'
        }).reset_index()
    fig = px.bar(yearly_data, x='Date', y=['Total Operating Revenues', 'Total Operating Expenditures'],
                    labels={'Date': 'Year', 'value': 'USD', 'variable': 'Type'})
    st.plotly_chart(fig, width="stretch")

if selected == "Operational Metrics":
    st.title("Zone-Wise Billing and Collection")
    fig = px.bar(df, x='Zone', y=['Total Water & Sewerage Billing', 'Total Collection'], barmode='group')
    st.plotly_chart(fig, width="stretch")

    st.title("Expense Distribution by Zone")
    fig = px.pie(df, names='Zone', values='Total Operating Expenditures', title='Expenditure Breakdown by Zone')
    st.plotly_chart(fig, width="stretch")

if selected == "Efficiency Analysis":
    st.title("Collection Efficiency by Zone")
    fig = px.line(df, x='Date', y='Collection Efficiency', color='Zone')
    st.plotly_chart(fig, width="stretch")

    st.title("Maintenance Cost Coverage")
    fig = px.bar(df, x='Zone', y='Operation & Maintenance Cost Coverage')
    st.plotly_chart(fig, width="stretch")

if selected == "Operational Details":
    st.title("Monthly Details Table")
    st.dataframe(df)

    st.title("Heatmap of Collection Efficiency")
    efficiency_heatmap = df.pivot_table(index='Month', columns='Year', values='Collection Efficiency', aggfunc='mean')
    fig = px.imshow(efficiency_heatmap, text_auto=True, aspect="auto", labels=dict(x="Year", y="Month", color="Efficiency"))
    st.plotly_chart(fig, width="stretch")

if selected == "Predictive Analytics":
    st.write("Predictive analytics sections would go here with future projections based on historical data.")
