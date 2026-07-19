"""Config-driven data for the AI Insights hub.

Consolidates every "here's money you could recover / an action to take"
signal the app already computes — smart recommendations plus the
uncollected estimates from Publishing, Neighboring Rights, Mechanicals,
and Territories — into a single list ranked by estimated impact, each
linking to the page where you act on it.
"""

from publishing_config import get_publishing_data
from neighboring_rights_config import get_neighboring_rights_data
from mechanicals_config import get_mechanicals_data
from territories_config import get_territories_data

CATEGORY_TONE = {
    "Recovery": "border-amber-500/20 bg-amber-500/10 text-amber-400",
    "Publishing": "border-blue-500/20 bg-blue-500/10 text-blue-400",
    "Neighboring": "border-purple-500/20 bg-purple-500/10 text-purple-400",
    "Mechanicals": "border-green-500/20 bg-green-500/10 text-green-400",
    "Territories": "border-cyan-500/20 bg-cyan-500/10 text-cyan-400",
}


def get_insights_data(smart_recommendations):
    insights = []

    for rec in smart_recommendations:
        insights.append({
            "title": rec.reason,
            "category": "Recovery",
            "impact": round(rec.estimated_value, 2),
            "cta": rec.cta_label,
            "route": "/recovery",
        })

    pub = get_publishing_data()["summary"]
    if pub["uncollected_total"] > 0:
        insights.append({
            "title": "Register unregistered works to collect performance + mechanical royalties",
            "category": "Publishing", "impact": pub["uncollected_total"],
            "cta": "Open Publishing", "route": "/publishing",
        })

    nbr = get_neighboring_rights_data()["summary"]
    if nbr["uncollected_total"] > 0:
        insights.append({
            "title": "Set up international neighboring-rights collection",
            "category": "Neighboring", "impact": nbr["uncollected_total"],
            "cta": "Open Neighboring Rights", "route": "/neighboring-rights",
        })

    mech = get_mechanicals_data()["summary"]
    if mech["blackbox_total"] > 0:
        insights.append({
            "title": "Claim mechanicals held in the MLC black box",
            "category": "Mechanicals", "impact": mech["blackbox_total"],
            "cta": "Open Mechanicals", "route": "/mechanicals",
        })

    terr = get_territories_data()["summary"]
    if terr["uncollected_total"] > 0:
        insights.append({
            "title": "Close collection gaps in %d territories" % terr["gap_countries"],
            "category": "Territories", "impact": terr["uncollected_total"],
            "cta": "Open Territories", "route": "/territories",
        })

    insights.sort(key=lambda x: x["impact"], reverse=True)
    for i in insights:
        i["tone"] = CATEGORY_TONE.get(i["category"], CATEGORY_TONE["Recovery"])

    total_impact = round(sum(i["impact"] for i in insights), 2)
    categories = sorted({i["category"] for i in insights})
    return {
        "summary": {
            "total_impact": total_impact,
            "count": len(insights),
            "categories": len(categories),
            "top_impact": insights[0]["impact"] if insights else 0,
        },
        "insights": insights,
    }
