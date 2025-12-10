"""
AI Insights Engine - Automated Intelligence for Executive Dashboard
Calculates daily pulse, anomaly detection, smart alerts, and data queries.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import re


# =============================================================================
# THRESHOLD CONFIGURATION (Customizable Alert Thresholds)
# =============================================================================

ALERT_THRESHOLDS = {
    "nrw": {
        "critical": 40,  # NRW > 40% = critical
        "warning": 30,   # NRW > 30% = warning
        "good": 25,      # NRW < 25% = good
        "unit": "%",
        "direction": "lower_is_better"
    },
    "collection_efficiency": {
        "critical": 70,  # < 70% = critical
        "warning": 85,   # < 85% = warning
        "good": 95,      # > 95% = good
        "unit": "%",
        "direction": "higher_is_better"
    },
    "service_hours": {
        "critical": 8,   # < 8 hrs = critical
        "warning": 16,   # < 16 hrs = warning
        "good": 20,      # > 20 hrs = good
        "unit": "hrs/day",
        "direction": "higher_is_better"
    },
    "water_quality": {
        "critical": 85,  # < 85% = critical
        "warning": 95,   # < 95% = warning
        "good": 99,      # > 99% = good
        "unit": "%",
        "direction": "higher_is_better"
    },
    "cost_recovery": {
        "critical": 0.8, # < 80% = critical
        "warning": 1.0,  # < 100% = warning
        "good": 1.2,     # > 120% = good
        "unit": "ratio",
        "direction": "higher_is_better"
    }
}


# =============================================================================
# SMART DATA QUERY PATTERNS (No LLM Required)
# =============================================================================

QUERY_PATTERNS = [
    # Top N queries
    {
        "pattern": r"(?:top|best|highest|worst|lowest)\s*(\d+)\s*(?:zones?|areas?|regions?)?\s*(?:with|by|for)?\s*(nrw|non.?revenue|water.?loss)",
        "type": "ranking",
        "metric": "nrw",
        "direction": "desc"  # highest = worst
    },
    {
        "pattern": r"(?:top|best|highest)\s*(\d+)\s*(?:zones?|areas?|regions?)?\s*(?:with|by|for)?\s*(?:collection|payment|revenue)",
        "type": "ranking",
        "metric": "collection_efficiency",
        "direction": "desc"  # highest = best
    },
    {
        "pattern": r"(?:worst|lowest)\s*(\d+)\s*(?:zones?|areas?|regions?)?\s*(?:with|by|for)?\s*(?:collection|payment|revenue)",
        "type": "ranking",
        "metric": "collection_efficiency",
        "direction": "asc"  # lowest = worst
    },
    {
        "pattern": r"(?:top|best|highest)\s*(\d+)\s*(?:zones?|areas?|regions?)?\s*(?:with|by|for)?\s*(?:service|supply|hours)",
        "type": "ranking",
        "metric": "service_hours",
        "direction": "desc"
    },
    # Comparison queries
    {
        "pattern": r"compare\s*(?:all)?\s*(?:zones?|areas?|regions?)",
        "type": "comparison",
        "metric": "all"
    },
    # Summary queries
    {
        "pattern": r"(?:summary|overview|status)\s*(?:of|for)?\s*(?:all)?\s*(?:zones?|areas?)?",
        "type": "summary",
        "metric": "all"
    },
    # Specific zone query
    {
        "pattern": r"(?:how|what).+(?:performance|doing|status).+(?:zone|area)\s+([a-zA-Z0-9\s]+)",
        "type": "zone_detail",
        "metric": "all"
    },
    # Alert queries
    {
        "pattern": r"(?:alerts?|warnings?|problems?|issues?|critical)",
        "type": "alerts",
        "metric": "all"
    }
]


def parse_data_query(query: str) -> Optional[Dict[str, Any]]:
    """
    Parse a natural language query into a structured data request.
    Returns None if query doesn't match any known pattern.
    
    This function does NOT require LLM - uses regex pattern matching.
    """
    query_lower = query.lower().strip()
    
    for pattern_def in QUERY_PATTERNS:
        match = re.search(pattern_def["pattern"], query_lower, re.IGNORECASE)
        if match:
            result = {
                "type": pattern_def["type"],
                "metric": pattern_def["metric"],
                "direction": pattern_def.get("direction", "desc"),
                "raw_query": query
            }
            
            # Extract limit (N) if present
            groups = match.groups()
            if groups and groups[0] and groups[0].isdigit():
                result["limit"] = int(groups[0])
            elif pattern_def["type"] == "ranking":
                result["limit"] = 5  # Default to top 5
            
            # Extract zone name if zone_detail query
            if pattern_def["type"] == "zone_detail" and len(groups) > 0:
                result["zone_name"] = groups[-1].strip() if groups[-1] else None
            
            return result
    
    return None


def execute_data_query(
    query_parsed: Dict[str, Any],
    billing_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    fin_df: pd.DataFrame
) -> str:
    """
    Execute a parsed data query and return formatted results.
    Returns human-readable response string.
    """
    if billing_df.empty:
        return "No billing data available to answer this query."
    
    # Calculate zone metrics
    zone_metrics = {}
    
    if "zone" in billing_df.columns:
        for zone_name in billing_df["zone"].dropna().unique():
            zone_billing = billing_df[billing_df["zone"] == zone_name]
            zone_prod = prod_df[prod_df["zone"] == zone_name] if not prod_df.empty and "zone" in prod_df.columns else pd.DataFrame()
            
            total_billed = zone_billing["billed"].sum()
            total_paid = zone_billing["paid"].sum()
            coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0
            
            total_consumption = zone_billing["consumption_m3"].sum()
            total_production = zone_prod["production_m3"].sum() if not zone_prod.empty else 0
            nrw = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
            
            avg_svc_hours = zone_prod["service_hours"].mean() if not zone_prod.empty else 0
            
            zone_metrics[zone_name] = {
                "collection_efficiency": round(coll_eff, 1),
                "nrw": round(nrw, 1),
                "service_hours": round(avg_svc_hours, 1),
                "revenue": total_paid
            }
    
    query_type = query_parsed.get("type")
    metric = query_parsed.get("metric", "all")
    limit = query_parsed.get("limit", 5)
    direction = query_parsed.get("direction", "desc")
    
    # Handle ranking queries
    if query_type == "ranking" and zone_metrics:
        if metric == "nrw":
            sorted_zones = sorted(zone_metrics.items(), key=lambda x: x[1]["nrw"], reverse=(direction == "desc"))
            sorted_zones = sorted_zones[:limit]
            
            response = f"**Top {limit} zones by NRW (Non-Revenue Water):**\n\n"
            for i, (zone, metrics) in enumerate(sorted_zones, 1):
                status = "🔴" if metrics["nrw"] > 40 else "🟡" if metrics["nrw"] > 30 else "🟢"
                response += f"{i}. **{zone}**: {metrics['nrw']}% NRW {status}\n"
            
            return response
        
        elif metric == "collection_efficiency":
            sorted_zones = sorted(zone_metrics.items(), key=lambda x: x[1]["collection_efficiency"], reverse=(direction == "desc"))
            sorted_zones = sorted_zones[:limit]
            
            label = "best" if direction == "desc" else "worst"
            response = f"**{limit} {label} zones by Collection Efficiency:**\n\n"
            for i, (zone, metrics) in enumerate(sorted_zones, 1):
                status = "🟢" if metrics["collection_efficiency"] > 90 else "🟡" if metrics["collection_efficiency"] > 70 else "🔴"
                response += f"{i}. **{zone}**: {metrics['collection_efficiency']}% {status}\n"
            
            return response
        
        elif metric == "service_hours":
            sorted_zones = sorted(zone_metrics.items(), key=lambda x: x[1]["service_hours"], reverse=(direction == "desc"))
            sorted_zones = sorted_zones[:limit]
            
            response = f"**Top {limit} zones by Service Hours:**\n\n"
            for i, (zone, metrics) in enumerate(sorted_zones, 1):
                status = "🟢" if metrics["service_hours"] > 20 else "🟡" if metrics["service_hours"] > 12 else "🔴"
                response += f"{i}. **{zone}**: {metrics['service_hours']}h/day {status}\n"
            
            return response
    
    # Handle comparison query
    elif query_type == "comparison" and zone_metrics:
        response = "**Zone Performance Comparison:**\n\n"
        response += "| Zone | Collection Eff. | NRW | Service Hrs |\n"
        response += "|------|-----------------|-----|-------------|\n"
        
        for zone, metrics in sorted(zone_metrics.items()):
            ce_icon = "🟢" if metrics["collection_efficiency"] > 90 else "🟡" if metrics["collection_efficiency"] > 70 else "🔴"
            nrw_icon = "🟢" if metrics["nrw"] < 25 else "🟡" if metrics["nrw"] < 40 else "🔴"
            sh_icon = "🟢" if metrics["service_hours"] > 20 else "🟡" if metrics["service_hours"] > 12 else "🔴"
            
            response += f"| {zone} | {metrics['collection_efficiency']}% {ce_icon} | {metrics['nrw']}% {nrw_icon} | {metrics['service_hours']}h {sh_icon} |\n"
        
        return response
    
    # Handle summary query
    elif query_type == "summary":
        total_billed = billing_df["billed"].sum()
        total_paid = billing_df["paid"].sum()
        overall_coll = (total_paid / total_billed * 100) if total_billed > 0 else 0
        
        total_consumption = billing_df["consumption_m3"].sum()
        total_production = prod_df["production_m3"].sum() if not prod_df.empty else 0
        overall_nrw = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
        
        avg_service = prod_df["service_hours"].mean() if not prod_df.empty else 0
        
        response = "**📊 System Performance Summary:**\n\n"
        response += f"• **Collection Efficiency**: {overall_coll:.1f}%\n"
        response += f"• **Non-Revenue Water**: {overall_nrw:.1f}%\n"
        response += f"• **Average Service Hours**: {avg_service:.1f}h/day\n"
        response += f"• **Total Revenue**: ${total_paid/1e6:.2f}M\n"
        response += f"• **Zones Monitored**: {len(zone_metrics)}\n"
        
        # Add alerts
        alerts = []
        if overall_nrw > 35:
            alerts.append("⚠️ NRW exceeds 35% threshold")
        if overall_coll < 85:
            alerts.append("⚠️ Collection efficiency below 85%")
        if avg_service < 16:
            alerts.append("⚠️ Service hours below 16h target")
        
        if alerts:
            response += "\n**Active Alerts:**\n"
            for alert in alerts:
                response += f"• {alert}\n"
        
        return response
    
    # Handle alerts query
    elif query_type == "alerts":
        alerts = []
        
        # Check each zone against thresholds
        for zone, metrics in zone_metrics.items():
            if metrics["nrw"] > ALERT_THRESHOLDS["nrw"]["critical"]:
                alerts.append({"zone": zone, "severity": "critical", "issue": f"NRW at {metrics['nrw']}%"})
            elif metrics["nrw"] > ALERT_THRESHOLDS["nrw"]["warning"]:
                alerts.append({"zone": zone, "severity": "warning", "issue": f"NRW at {metrics['nrw']}%"})
            
            if metrics["collection_efficiency"] < ALERT_THRESHOLDS["collection_efficiency"]["critical"]:
                alerts.append({"zone": zone, "severity": "critical", "issue": f"Collection at {metrics['collection_efficiency']}%"})
            elif metrics["collection_efficiency"] < ALERT_THRESHOLDS["collection_efficiency"]["warning"]:
                alerts.append({"zone": zone, "severity": "warning", "issue": f"Collection at {metrics['collection_efficiency']}%"})
        
        if not alerts:
            return "✅ **No active alerts.** All zones are operating within acceptable thresholds."
        
        response = "**🚨 Active Alerts:**\n\n"
        
        critical_alerts = [a for a in alerts if a["severity"] == "critical"]
        warning_alerts = [a for a in alerts if a["severity"] == "warning"]
        
        if critical_alerts:
            response += "**Critical (Immediate Action Required):**\n"
            for alert in critical_alerts[:5]:
                response += f"🔴 **{alert['zone']}**: {alert['issue']}\n"
        
        if warning_alerts:
            response += "\n**Warnings (Monitor Closely):**\n"
            for alert in warning_alerts[:5]:
                response += f"🟡 **{alert['zone']}**: {alert['issue']}\n"
        
        return response
    
    # Zone detail query
    elif query_type == "zone_detail":
        zone_name = query_parsed.get("zone_name", "").lower()
        
        # Find matching zone
        matching_zone = None
        for zone in zone_metrics.keys():
            if zone_name in zone.lower():
                matching_zone = zone
                break
        
        if matching_zone and matching_zone in zone_metrics:
            m = zone_metrics[matching_zone]
            response = f"**📍 {matching_zone} Performance:**\n\n"
            response += f"• **Collection Efficiency**: {m['collection_efficiency']}%\n"
            response += f"• **Non-Revenue Water**: {m['nrw']}%\n"
            response += f"• **Service Hours**: {m['service_hours']}h/day\n"
            response += f"• **Revenue**: ${m['revenue']/1e6:.2f}M\n"
            return response
        else:
            return f"Zone '{zone_name}' not found. Available zones: {', '.join(list(zone_metrics.keys())[:5])}..."
    
    return "I couldn't understand that query. Try asking things like:\n• 'Top 5 zones with highest NRW'\n• 'Compare all zones'\n• 'Show me alerts'"


def generate_quick_insight(
    billing_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    fin_df: pd.DataFrame,
    selected_country: str = "All"
) -> str:
    """
    Generate a quick 2-3 sentence insight for the executive dashboard.
    No LLM required - rule-based narrative generation.
    """
    if billing_df.empty:
        return "Data is loading... Check back shortly for insights."
    
    # Calculate key metrics
    total_billed = billing_df["billed"].sum()
    total_paid = billing_df["paid"].sum()
    coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0
    
    total_production = prod_df["production_m3"].sum() if not prod_df.empty else 0
    total_consumption = billing_df["consumption_m3"].sum()
    nrw = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
    
    # Identify the most critical issue
    insights = []
    
    if nrw > 40:
        insights.append(f"⚠️ NRW is critically high at {nrw:.1f}%. Immediate leak detection recommended.")
    elif nrw > 30:
        insights.append(f"📈 NRW at {nrw:.1f}% exceeds the 30% target. Focus on meter accuracy and leakage control.")
    
    if coll_eff < 70:
        insights.append(f"🔴 Collection efficiency at {coll_eff:.1f}% requires urgent attention.")
    elif coll_eff < 85:
        insights.append(f"💰 Collection efficiency ({coll_eff:.1f}%) can be improved with targeted follow-ups.")
    
    # Find worst zone if available
    if "zone" in billing_df.columns:
        zone_coll = billing_df.groupby("zone").agg({"billed": "sum", "paid": "sum"})
        zone_coll["eff"] = (zone_coll["paid"] / zone_coll["billed"]) * 100
        zone_coll = zone_coll[zone_coll["billed"] > 0].sort_values("eff")
        
        if not zone_coll.empty:
            worst_zone = zone_coll.index[0]
            worst_eff = zone_coll.iloc[0]["eff"]
            if worst_eff < 70:
                insights.append(f"📍 Zone {worst_zone} needs priority attention ({worst_eff:.0f}% collection).")
    
    if not insights:
        insights.append(f"✅ Operations running smoothly. Collection at {coll_eff:.1f}%, NRW at {nrw:.1f}%.")
    
    return " ".join(insights[:2])  # Return top 2 insights


# =============================================================================
# INDICATOR SEARCH INDEX (No LLM required)
# Based on AUDC Data Dictionary - Maps indicators to pages and tabs
# =============================================================================

INDICATOR_SEARCH_INDEX = [
    # Access & Coverage - Water Supply
    {"indicator": "surface water access", "keywords": ["surface water", "river", "dam", "lake", "pond"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "unimproved water sources", "keywords": ["unimproved", "unprotected well", "spring"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "limited water access", "keywords": ["limited", "collection time", "30 minutes"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "basic water access", "keywords": ["basic", "improved source"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "safely managed water", "keywords": ["safely managed", "drinking water", "safe water", "water quality"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "water supply coverage", "keywords": ["coverage", "municipal water", "piped water", "households"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Water Supply", "frequency": "Quarterly"},
    {"indicator": "water supply growth", "keywords": ["increase", "growth", "expansion", "coverage growth"], 
     "page": "Access & Coverage", "tab": "Growth Metrics", "domain": "Water Supply", "frequency": "Quarterly"},
    {"indicator": "metered connections", "keywords": ["metered", "meter", "metering"], 
     "page": "Access & Coverage", "tab": "Infrastructure Status", "domain": "Water Supply", "frequency": "Monthly"},
    
    # Access & Coverage - Sanitation
    {"indicator": "open defecation", "keywords": ["open defecation", "OD", "defecation"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "unimproved sanitation", "keywords": ["unimproved sanitation", "pit latrine", "bucket latrine"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "limited sanitation", "keywords": ["limited sanitation", "shared toilet", "shared sanitation"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "basic sanitation", "keywords": ["basic sanitation", "improved sanitation"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "safely managed sanitation", "keywords": ["safely managed sanitation", "safe sanitation"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "sewer connections", "keywords": ["sewer", "sewerage", "sewered", "sewer connections"], 
     "page": "Access & Coverage", "tab": "Coverage Overview", "domain": "Sanitation", "frequency": "Quarterly"},
    {"indicator": "public toilets", "keywords": ["public toilet", "public sanitation"], 
     "page": "Access & Coverage", "tab": "Infrastructure Status", "domain": "Sanitation", "frequency": "Monthly"},
    
    # Production
    {"indicator": "non-revenue water", "keywords": ["NRW", "non-revenue water", "water loss", "losses", "leakage"], 
     "page": "Production", "tab": "Water Balance", "domain": "Water Supply", "frequency": "Monthly"},
    {"indicator": "consumption per capita", "keywords": ["consumption", "per capita", "demand", "water demand"], 
     "page": "Production", "tab": "Production Metrics", "domain": "Water Supply", "frequency": "Monthly"},
    {"indicator": "wastewater treatment", "keywords": ["wastewater", "sewage treatment", "treated wastewater", "ww treated"], 
     "page": "Production", "tab": "Treatment", "domain": "Sanitation", "frequency": "Monthly"},
    {"indicator": "water recycling", "keywords": ["recycled", "reused", "water reuse", "recycling"], 
     "page": "Production", "tab": "Circular Economy", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "faecal sludge", "keywords": ["faecal sludge", "FS", "sludge", "emptying", "desludging"], 
     "page": "Production", "tab": "Sludge Management", "domain": "Sanitation", "frequency": "Monthly"},
    {"indicator": "treatment capacity", "keywords": ["capacity", "utilization", "WTP", "STP", "FSTP"], 
     "page": "Production", "tab": "Capacity", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "water stress", "keywords": ["water stress", "water scarcity", "resources"], 
     "page": "Production", "tab": "Resource Analysis", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "production volume", "keywords": ["production", "volume", "produced", "m3"], 
     "page": "Production", "tab": "Production Metrics", "domain": "Water Supply", "frequency": "Daily"},
    {"indicator": "service hours", "keywords": ["service hours", "hours per day", "supply hours", "availability"], 
     "page": "Production", "tab": "Service Continuity", "domain": "Water Supply", "frequency": "Daily"},
    
    # Service & Quality
    {"indicator": "water quality", "keywords": ["water quality", "chlorine", "e.coli", "ecoli", "contamination", "testing"], 
     "page": "Service Quality", "tab": "Water Quality", "domain": "Water Supply", "frequency": "Monthly"},
    {"indicator": "women in decision-making", "keywords": ["women", "gender", "female", "decision-making", "workforce"], 
     "page": "Service Quality", "tab": "Governance", "domain": "Sanitation", "frequency": "Quarterly"},
    {"indicator": "continuity of supply", "keywords": ["continuity", "supply hours", "24x7", "reliability"], 
     "page": "Service Quality", "tab": "Service Reliability", "domain": "Water Supply", "frequency": "Monthly"},
    {"indicator": "complaints resolution", "keywords": ["complaints", "resolved", "resolution", "customer service"], 
     "page": "Service Quality", "tab": "Customer Service", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "sewer blockages", "keywords": ["blockage", "blocked", "sewer blockage", "maintenance"], 
     "page": "Service Quality", "tab": "Network Performance", "domain": "Sanitation", "frequency": "Monthly"},
    {"indicator": "staff efficiency", "keywords": ["staff", "employees", "efficiency", "per 1000 connections"], 
     "page": "Service Quality", "tab": "Operational Efficiency", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "asset health", "keywords": ["asset", "infrastructure", "condition", "health index"], 
     "page": "Service Quality", "tab": "Asset Management", "domain": "Both", "frequency": "Annual"},
    {"indicator": "staff training", "keywords": ["training", "capacity building", "trained staff"], 
     "page": "Service Quality", "tab": "Human Resources", "domain": "Both", "frequency": "Annual"},
    
    # Financial Health
    {"indicator": "collection efficiency", "keywords": ["collection", "revenue collection", "billing", "payment", "collection rate"], 
     "page": "Financial Health", "tab": "Revenue Performance", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "operating cost coverage", "keywords": ["cost coverage", "cost recovery", "opex", "operating cost"], 
     "page": "Financial Health", "tab": "Cost Analysis", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "pro-poor financing", "keywords": ["pro-poor", "subsidy", "poor", "equity", "tariff"], 
     "page": "Financial Health", "tab": "Equity Analysis", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "budget variance", "keywords": ["budget", "variance", "allocated", "actual expenditure"], 
     "page": "Financial Health", "tab": "Budget Analysis", "domain": "Both", "frequency": "Annual"},
    {"indicator": "budget allocation water", "keywords": ["national budget", "water allocation", "government funding"], 
     "page": "Financial Health", "tab": "Government Funding", "domain": "Water Supply", "frequency": "Annual"},
    {"indicator": "budget allocation sanitation", "keywords": ["national budget", "sanitation allocation", "government funding"], 
     "page": "Financial Health", "tab": "Government Funding", "domain": "Sanitation", "frequency": "Annual"},
    {"indicator": "staff cost", "keywords": ["staff cost", "HR cost", "salary", "personnel"], 
     "page": "Financial Health", "tab": "Cost Breakdown", "domain": "Both", "frequency": "Annual"},
    {"indicator": "debt", "keywords": ["debt", "outstanding", "arrears", "unpaid"], 
     "page": "Financial Health", "tab": "Revenue Performance", "domain": "Both", "frequency": "Monthly"},
    {"indicator": "revenue", "keywords": ["revenue", "income", "billed", "total revenue"], 
     "page": "Financial Health", "tab": "Revenue Performance", "domain": "Both", "frequency": "Monthly"},
]


def search_indicators(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search for indicators/metrics based on user query.
    Returns list of matching indicators with navigation guidance.
    
    This function does NOT require LLM - it's a simple keyword-based search.
    
    Args:
        query: User's search query
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with indicator info and navigation guidance
    """
    if not query or len(query.strip()) < 2:
        return []
    
    query_lower = query.lower().strip()
    query_words = query_lower.split()
    
    results = []
    
    for item in INDICATOR_SEARCH_INDEX:
        score = 0
        
        # Check indicator name
        if query_lower in item["indicator"].lower():
            score += 10
        
        # Check keywords
        for keyword in item["keywords"]:
            keyword_lower = keyword.lower()
            if query_lower in keyword_lower:
                score += 5
            elif keyword_lower in query_lower:
                score += 5
            else:
                # Check individual words
                for word in query_words:
                    if len(word) >= 3 and word in keyword_lower:
                        score += 2
        
        # Check page name
        if query_lower in item["page"].lower():
            score += 3
        
        # Check domain
        if query_lower in item["domain"].lower():
            score += 2
        
        if score > 0:
            results.append({
                "indicator": item["indicator"],
                "page": item["page"],
                "tab": item["tab"],
                "domain": item["domain"],
                "frequency": item["frequency"],
                "score": score,
                "guidance": f"Go to **{item['page']}** page → **{item['tab']}** tab"
            })
    
    # Sort by score and return top results
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def get_search_suggestions() -> List[str]:
    """Get popular/common search terms for autocomplete."""
    return [
        "NRW", "collection efficiency", "water quality", "service hours",
        "coverage", "sewer", "complaints", "revenue", "budget", "staff",
        "treatment", "wastewater", "consumption", "metering", "blockages"
    ]


class InsightsEngine:
    """
    Generates intelligent insights from utility data.
    """
    
    def __init__(self, billing_df: pd.DataFrame, prod_df: pd.DataFrame, fin_df: pd.DataFrame):
        """Initialize with dataframes from the dashboard."""
        self.billing_df = billing_df
        self.prod_df = prod_df
        self.fin_df = fin_df
    
    def calculate_overall_score(self) -> float:
        """
        Calculate a 0-100 performance score based on key metrics.
        Weighted average of normalized KPIs.
        """
        scores = []
        
        # 1. Collection Efficiency (weight: 0.3)
        total_billed = self.billing_df["billed"].sum()
        total_paid = self.billing_df["paid"].sum()
        coll_eff = (total_paid / total_billed) if total_billed > 0 else 0
        coll_score = min(100, (coll_eff / 0.95) * 100)  # Target 95%
        scores.append(("collection", coll_score, 0.3))
        
        # 2. NRW (weight: 0.25)
        total_production = self.prod_df["production_m3"].sum()
        total_consumption = self.billing_df["consumption_m3"].sum()
        nrw_pct = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
        nrw_score = max(0, 100 - (nrw_pct / 0.5))  # Penalty for exceeding 50%
        scores.append(("nrw", nrw_score, 0.25))
        
        # 3. Service Hours (weight: 0.2)
        avg_service_hours = self.prod_df["service_hours"].mean() if not self.prod_df.empty else 0
        svc_score = min(100, (avg_service_hours / 20) * 100)  # Target 20h
        scores.append(("service", svc_score, 0.2))
        
        # 4. Operating Efficiency (weight: 0.15)
        total_opex = self.fin_df["opex"].sum()
        total_revenue = total_paid + self.fin_df["sewer_revenue"].sum()
        op_ratio = (total_revenue / total_opex) if total_opex > 0 else 0
        op_score = min(100, op_ratio * 100)
        scores.append(("operating", op_score, 0.15))
        
        # 5. Complaint Resolution (weight: 0.1)
        total_complaints = self.fin_df["complaints"].sum()
        total_resolved = self.fin_df["resolved"].sum()
        res_rate = (total_resolved / total_complaints) if total_complaints > 0 else 1
        res_score = res_rate * 100
        scores.append(("complaints", res_score, 0.1))
        
        # Weighted average
        weighted_sum = sum(score * weight for _, score, weight in scores)
        return round(weighted_sum, 1)
    
    def detect_anomalies(self, lookback_days: int = 7) -> List[Dict]:
        """
        Detect anomalies by comparing recent performance to historical baseline.
        Returns list of {metric, change_pct, severity, message}
        """
        anomalies = []
        
        # Get recent data (last 1 day) vs baseline (previous lookback_days)
        if self.billing_df.empty:
            return anomalies
            
        max_date = self.billing_df["date"].max()
        yesterday = max_date - timedelta(days=1)
        baseline_start = yesterday - timedelta(days=lookback_days)
        
        # Recent data
        recent_billing = self.billing_df[self.billing_df["date"] >= yesterday]
        recent_prod = self.prod_df[self.prod_df["date"] >= yesterday] if not self.prod_df.empty else pd.DataFrame()
        
        # Baseline data
        baseline_billing = self.billing_df[
            (self.billing_df["date"] >= baseline_start) & (self.billing_df["date"] < yesterday)
        ]
        baseline_prod = self.prod_df[
            (self.prod_df["date"] >= baseline_start) & (self.prod_df["date"] < yesterday)
        ] if not self.prod_df.empty else pd.DataFrame()
        
        # 1. Collection Efficiency Anomaly
        recent_coll = (recent_billing["paid"].sum() / recent_billing["billed"].sum()) if recent_billing["billed"].sum() > 0 else 0
        baseline_coll = (baseline_billing["paid"].sum() / baseline_billing["billed"].sum()) if baseline_billing["billed"].sum() > 0 else 0
        
        if baseline_coll > 0:
            coll_change = ((recent_coll - baseline_coll) / baseline_coll) * 100
            if abs(coll_change) > 5:  # Threshold: 5% change
                severity = "critical" if abs(coll_change) > 10 else "warning"
                direction = "dropped" if coll_change < 0 else "increased"
                anomalies.append({
                    "metric": "Collection Efficiency",
                    "change_pct": coll_change,
                    "severity": severity,
                    "message": f"Collection Efficiency {direction} by {abs(coll_change):.1f}% compared to {lookback_days}-day average"
                })
        
        # 2. Service Hours Anomaly
        if not recent_prod.empty and not baseline_prod.empty:
            recent_svc = recent_prod["service_hours"].mean()
            baseline_svc = baseline_prod["service_hours"].mean()
            
            if baseline_svc > 0:
                svc_change = ((recent_svc - baseline_svc) / baseline_svc) * 100
                if abs(svc_change) > 10:  # Threshold: 10% change
                    severity = "critical" if recent_svc < 12 else "warning"
                    anomalies.append({
                        "metric": "Service Hours",
                        "change_pct": svc_change,
                        "severity": severity,
                        "message": f"Service hours changed by {svc_change:.1f}% (now {recent_svc:.1f}h/day)"
                    })
        
        # 3. NRW Spike
        recent_nrw_prod = recent_prod["production_m3"].sum() if not recent_prod.empty else 0
        recent_nrw_cons = recent_billing["consumption_m3"].sum()
        recent_nrw = ((recent_nrw_prod - recent_nrw_cons) / recent_nrw_prod * 100) if recent_nrw_prod > 0 else 0
        
        baseline_nrw_prod = baseline_prod["production_m3"].sum() if not baseline_prod.empty else 0
        baseline_nrw_cons = baseline_billing["consumption_m3"].sum()
        baseline_nrw = ((baseline_nrw_prod - baseline_nrw_cons) / baseline_nrw_prod * 100) if baseline_nrw_prod > 0 else 0
        
        if baseline_nrw > 0:
            nrw_change = recent_nrw - baseline_nrw
            if abs(nrw_change) > 5:  # Threshold: 5 percentage points
                severity = "critical" if recent_nrw > 40 else "warning"
                anomalies.append({
                    "metric": "Non-Revenue Water",
                    "change_pct": nrw_change,
                    "severity": severity,
                    "message": f"NRW is now {recent_nrw:.1f}% (changed by {nrw_change:+.1f} pts)"
                })
        
        return anomalies
    
    def generate_daily_pulse(self, user_name: str = "Managing Director") -> str:
        """
        Generate a concise 3-sentence morning briefing.
        Format: Greeting + Overall Status + Key Alert + Specific Issue
        """
        score = self.calculate_overall_score()
        anomalies = self.detect_anomalies()
        
        # Greeting with score
        if score >= 85:
            status = "excellent shape"
        elif score >= 70:
            status = "stable"
        elif score >= 50:
            status = "showing some concerns"
        else:
            status = "requiring immediate attention"
        
        greeting = f"Good morning. Overall performance is in {status} (Score: {score:.0f}/100)."
        
        # Key alert (most severe anomaly)
        alert = ""
        critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
        if critical_anomalies:
            top_anomaly = critical_anomalies[0]
            alert = f" {top_anomaly['message']}."
        elif anomalies:
            top_anomaly = anomalies[0]
            alert = f" {top_anomaly['message']}."
        else:
            alert = " All key metrics are within acceptable ranges."
        
        # Specific zone issue (if available)
        zone_issue = ""
        if not self.billing_df.empty and "zone" in self.billing_df.columns:
            # Find worst performing zone by collection efficiency
            zone_coll = self.billing_df.groupby("zone").agg({
                "billed": "sum",
                "paid": "sum"
            })
            zone_coll["coll_eff"] = (zone_coll["paid"] / zone_coll["billed"]) * 100
            zone_coll = zone_coll[zone_coll["billed"] > 0].sort_values("coll_eff")
            
            if not zone_coll.empty:
                worst_zone = zone_coll.index[0]
                worst_coll = zone_coll.iloc[0]["coll_eff"]
                
                if worst_coll < 70:
                    zone_issue = f" Zone {worst_zone} shows critical collection efficiency at {worst_coll:.0f}%."
        
        return greeting + alert + zone_issue
    
    def get_suggested_questions(self) -> List[str]:
        """
        Generate context-aware suggested questions based on current data state.
        """
        suggestions = []
        
        # Always include basic questions
        suggestions.append("Why is NRW trending upward?")
        suggestions.append("Compare performance across all zones")
        
        # Add anomaly-based questions
        anomalies = self.detect_anomalies()
        for anom in anomalies[:2]:  # Top 2
            if "Collection" in anom["metric"]:
                suggestions.append("What's causing the collection efficiency drop?")
            elif "Service" in anom["metric"]:
                suggestions.append("How do service interruptions affect revenue?")
            elif "NRW" in anom["metric"]:
                suggestions.append("Which zone has the highest water losses?")
        
        # Add performance-based questions
        score = self.calculate_overall_score()
        if score < 70:
            suggestions.append("What actions can improve our overall score?")
        
        # Financial questions if opex is high
        if not self.fin_df.empty:
            total_opex = self.fin_df["opex"].sum()
            total_revenue = self.billing_df["paid"].sum() + self.fin_df["sewer_revenue"].sum()
            if total_opex > 0 and (total_revenue / total_opex) < 1.1:
                suggestions.append("How can we reduce operating costs?")
        
        return suggestions[:5]  # Return top 5
    
    def correlate_service_quality(self) -> Optional[str]:
        """
        Find correlation between service hours and other metrics.
        Returns insight string if correlation found.
        """
        if self.prod_df.empty or self.billing_df.empty:
            return None
        
        # Merge prod and billing by date
        prod_daily = self.prod_df.groupby("date").agg({"service_hours": "mean", "production_m3": "sum"}).reset_index()
        billing_daily = self.billing_df.groupby("date").agg({"consumption_m3": "sum", "billed": "sum", "paid": "sum"}).reset_index()
        
        merged = pd.merge(prod_daily, billing_daily, on="date", how="inner")
        
        if len(merged) < 10:  # Need sufficient data
            return None
        
        # Calculate correlation between service hours and collection
        merged["coll_eff"] = (merged["paid"] / merged["billed"]) * 100
        
        # Filter valid data
        valid = merged[(merged["service_hours"] > 0) & (merged["billed"] > 0)]
        
        if len(valid) > 5:
            corr = valid["service_hours"].corr(valid["coll_eff"])
            
            if abs(corr) > 0.5:  # Significant correlation
                direction = "positive" if corr > 0 else "negative"
                strength = "strong" if abs(corr) > 0.7 else "moderate"
                
                # Find threshold effect
                low_svc = valid[valid["service_hours"] < 12]
                high_svc = valid[valid["service_hours"] >= 12]
                
                if not low_svc.empty and not high_svc.empty:
                    low_coll = low_svc["coll_eff"].mean()
                    high_coll = high_svc["coll_eff"].mean()
                    diff = high_coll - low_coll
                    
                    return (f"Analysis reveals a {strength} {direction} correlation ({corr:.2f}) between service hours and collection efficiency. "
                            f"When service drops below 12 hours/day, collection efficiency is {diff:.1f}% lower on average.")
        
        return None
    
    def zone_performance_summary(self) -> Dict[str, Dict]:
        """
        Calculate performance metrics by zone for comparison.
        Returns dict of {zone: {metrics}}
        """
        if self.billing_df.empty or "zone" not in self.billing_df.columns:
            return {}
        
        zones = {}
        
        for zone_name in self.billing_df["zone"].dropna().unique():
            zone_billing = self.billing_df[self.billing_df["zone"] == zone_name]
            zone_prod = self.prod_df[self.prod_df["zone"] == zone_name] if not self.prod_df.empty and "zone" in self.prod_df.columns else pd.DataFrame()
            
            # Calculate metrics
            total_billed = zone_billing["billed"].sum()
            total_paid = zone_billing["paid"].sum()
            coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0
            
            total_consumption = zone_billing["consumption_m3"].sum()
            total_production = zone_prod["production_m3"].sum() if not zone_prod.empty else 0
            nrw = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
            
            avg_svc_hours = zone_prod["service_hours"].mean() if not zone_prod.empty else 0
            
            zones[zone_name] = {
                "collection_efficiency": coll_eff,
                "nrw_percent": nrw,
                "service_hours": avg_svc_hours,
                "revenue": total_paid
            }
        
        return zones


def generate_board_brief_text(
    billing_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    fin_df: pd.DataFrame,
    selected_period: str = "This month"
) -> str:
    """
    Generate a narrative board brief text (for export/display).
    """
    engine = InsightsEngine(billing_df, prod_df, fin_df)
    
    # Calculate key metrics
    total_billed = billing_df["billed"].sum()
    total_paid = billing_df["paid"].sum()
    coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0
    
    total_production = prod_df["production_m3"].sum() if not prod_df.empty else 0
    total_consumption = billing_df["consumption_m3"].sum()
    nrw_pct = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
    
    total_opex = fin_df["opex"].sum() if not fin_df.empty else 0
    total_revenue = total_paid + (fin_df["sewer_revenue"].sum() if not fin_df.empty else 0)
    op_ratio = (total_revenue / total_opex) if total_opex > 0 else 0
    
    score = engine.calculate_overall_score()
    
    # Build narrative
    brief = f"""
# Executive Board Brief - {selected_period}

## Overall Performance
Overall utility performance score: **{score:.0f}/100**.

## Financial Summary
{selected_period}, we achieved **${total_revenue/1e6:.2f}M** in total revenue against **${total_opex/1e6:.2f}M** in operating expenditure, 
resulting in an operating cost coverage ratio of **{op_ratio:.2f}**. Collection efficiency stands at **{coll_eff:.1f}%**, 
{"meeting" if coll_eff >= 90 else "below"} our target of 95%.

## Operational Efficiency
Non-Revenue Water (NRW) remains a critical concern at **{nrw_pct:.1f}%**, {"which exceeds" if nrw_pct > 30 else "below"} the target of 25%. 
This represents **{(total_production - total_consumption)/1e3:.1f}k m³** of unbilled water. 
{"Priority interventions are required to reduce system losses." if nrw_pct > 35 else "Continued monitoring is recommended."}

## Service Delivery
"""
    
    if not prod_df.empty:
        avg_svc_hours = prod_df["service_hours"].mean()
        brief += f"Average service hours: **{avg_svc_hours:.1f} hours/day** (Target: 20h).\n\n"
    
    # Zone analysis
    zones = engine.zone_performance_summary()
    if zones:
        brief += "## Zone Performance\n"
        sorted_zones = sorted(zones.items(), key=lambda x: x[1]["collection_efficiency"])
        
        if sorted_zones:
            worst_zone, worst_metrics = sorted_zones[0]
            best_zone, best_metrics = sorted_zones[-1]
            
            brief += f"**Best performing**: {best_zone} ({best_metrics['collection_efficiency']:.1f}% collection). "
            brief += f"**Needs attention**: {worst_zone} ({worst_metrics['collection_efficiency']:.1f}% collection).\n\n"
    
    # Recommendations
    brief += "## Strategic Recommendations\n"
    if nrw_pct > 35:
        brief += "1. **Immediate**: Launch NRW reduction program targeting leak detection and meter accuracy.\n"
    if coll_eff < 85:
        brief += "2. **High Priority**: Strengthen revenue collection processes and customer engagement.\n"
    if op_ratio < 1.0:
        brief += "3. **Financial**: Review cost structure and identify efficiency gains to achieve cost recovery.\n"
    
    return brief
