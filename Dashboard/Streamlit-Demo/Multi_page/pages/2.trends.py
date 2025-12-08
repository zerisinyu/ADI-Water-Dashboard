# pages/2_📈_trends.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Trends", page_icon="📈")

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('../../Data/WARIS.CSV')
    df['Date'] = pd.to_datetime(df[['Year', 'Month']].assign(DAY=1))
    return df

df = load_data()

st.title("Trends Analysis")

# Date range selector
date_range = st.date_input(
    "Select Date Range",
    value=(df['Date'].min(), df['Date'].max())
)

# Filter data by date
mask = (df['Date'] >= pd.to_datetime(date_range[0])) & (df['Date'] <= pd.to_datetime(date_range[1]))
filtered_df = df[mask]

# Trend chart
st.header("Revenue Trends")
fig = px.line(filtered_df, 
              x='Date', 
              y='Total Operating Revenues',
              color='Zone',
              title='Revenue by Zone Over Time')
st.plotly_chart(fig, width="stretch")

# Summary statistics
st.header("Summary Statistics")
st.dataframe(filtered_df.groupby('Zone')['Total Operating Revenues'].agg(['mean', 'min', 'max']))
