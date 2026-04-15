from app.services.database_service import db

def get_revenue_summary():
    """
    Calculates total network revenue across all sources:
    1. Ad Impressions (CPM based)
    2. Wi-Fi Package Purchases
    """
    try:
        # Calculate Ad Revenue (CPM = R50.00 default)
        ads = list(db.ads.find({"active": True}))
        total_ad_revenue = sum((ad.get('impressions', 0) / 1000) * ad.get('cpm_rate', 50.00) for ad in ads)

        # Calculate Bundle Sales Revenue (from session history)
        # Assuming you store price in the session record when purchased
        sessions = list(db.hotspot_sessions.find({}))
        total_bundle_revenue = sum(float(s.get('price', 0)) for s in sessions)

        return {
            "total_revenue": round(total_ad_revenue + total_bundle_revenue, 2),
            "ad_revenue": round(total_ad_revenue, 2),
            "bundle_revenue": round(total_bundle_revenue, 2),
            "total_impressions": sum(ad.get('impressions', 0) for ad in ads)
        }
    except Exception as e:
        return {"error": str(e)}

def get_performance_distribution():
    """
    Prepares data for the Doughnut/Pie charts in the dashboard.
    Shows which ads are generating the most value.
    """
    try:
        ads = list(db.ads.find({"active": True}).sort("impressions", -1).limit(5))
        labels = [ad['ad_id'] for ad in ads]
        data = [ad['impressions'] for ad in ads]
        
        return {
            "labels": labels,
            "datasets": [{
                "label": "Impressions by Campaign",
                "data": data,
                "backgroundColor": ['#0061ff', '#60a5fa', '#10b981', '#f59e0b', '#ef4444']
            }]
        }
    except Exception as e:
        return {"error": str(e)}

def get_network_load_stats():
    """
    Calculates hourly traffic peaks based on session starts.
    Used for the Line Chart to see when the network is busiest.
    """
    # logic to aggregate sessions by hour...
    pass