# Home.py
import streamlit as st
import pandas as pd
import plotly.express as px

# Page config
st.set_page_config(
    page_title="Dashboard",
    page_icon="🏠",
    layout="wide"
)

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('../../Data/WARIS.CSV')
    df['Date'] = pd.to_datetime(df[['Year', 'Month']].assign(DAY=1))
    return df

df = load_data()

# Main page
st.title("Dashboard Overview")

# Key metrics in columns
col1, col2, col3 = st.columns(3)

# Calculate metrics
total_revenue = df['Total Operating Revenues'].sum()
total_expenditure = df['Total Operating Expenditures'].sum()
efficiency = df['Collection Efficiency'].mean()

# Display metrics
col1.metric("Total Revenue", f"${total_revenue:,.0f}")
col2.metric("Total Expenditure", f"${total_expenditure:,.0f}")
col3.metric("Average Collection Efficiency", f"{efficiency:.1f}%")

# Main chart
st.header("Revenue vs Expenditure Over Time")
fig = px.line(df, 
              x='Date', 
              y=['Total Operating Revenues', 'Total Operating Expenditures'],
              title='Revenue and Expenditure Trends')
st.plotly_chart(fig, width="stretch")
