"""
AI Insights Engine - Automated Intelligence for Executive Dashboard
Calculates daily pulse, anomaly detection, and smart alerts.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


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
