"""Advisor rules engine: needs -> eligible, dependency-complete bundle with a transparent quote.

Design rule: the catalogue rules decide WHAT is sold (deterministic, auditable, judge-testable);
the language layer only decides HOW it is explained. An LLM can be plugged into `explain()`
but is never allowed to add or remove products.
"""
import math
from registry import REG

SEG_CODE = {"micro": "Micro retail & services", "prof": "Professional offices",
            "multi": "Small multi-site businesses", "mfg": "Small manufacturers"}

# need -> (product id, quantity rule)
NEED_MAP = {
    "upi_pos": ("P19", "counters"),
    "whatsapp": ("P15", "one"),
    "sms": ("P14", "one"),
    "cctv": ("P23", "cameras"),
    "cloud_email": ("P16", "users"),
    "backup": ("P17", "one"),
    "security": ("P20", "devices"),
    "firewall": ("P21", "sites"),
    "guest_wifi": ("P22", "sites"),
    "failover": ("P09", "sites"),
    "website": ("P18", "one"),
    "telephony": ("P12", "channels"),
    "tollfree": ("P13", "one"),
    "iot": ("P24", "machines"),
    "fleet": ("P25", "vehicles"),
    "static_ip": ("P11", "one"),
    "sdwan": ("P10", "sites"),
}

WHY = {
    "en": {
        "P01": "100 Mbps fibre is plenty for UPI, billing and a few devices",
        "P02": "300 Mbps fibre keeps video calls and cloud apps smooth for your team",
        "P03": "1 Gbps fibre with priority support for a busy office",
        "P04": "5G AirFiber works where fibre is not laid - installed in about 2 days",
        "P05": "a dedicated 20 Mbps line with 99.5% uptime SLA for operations that cannot stop",
        "P06": "a dedicated 100 Mbps line with 99.9% SLA for your plant",
        "P07": "business SIMs for staff with unlimited calls, all on one bill",
        "P08": "premium business SIMs with roaming for people who travel",
        "P09": "automatic 4G/5G backup so UPI and billing never stop if the wire is cut",
        "P10": "one dashboard to manage the network at all your sites",
        "P11": "a fixed IP so your CCTV / server can be reached from outside",
        "P12": "a business phone line that rings on any staff phone",
        "P13": "a toll-free number customers can call for free",
        "P14": "bulk SMS for offers and reminders (DLT registration done for you)",
        "P15": "official WhatsApp Business for your catalogue, orders and reminders",
        "P16": "professional email @yourbusiness with video meetings",
        "P17": "1 TB cloud backup so records are safe even if a laptop is lost",
        "P18": "a ready website with your own domain",
        "P19": "billing tablet that accepts UPI and cards and prints GST bills",
        "P20": "antivirus for each work device",
        "P21": "a managed firewall that blocks attacks before they reach you",
        "P22": "separate guest Wi-Fi so customers never touch your billing network",
        "P23": "cloud CCTV you can watch live on your phone",
        "P24": "sensors that alert you when a machine stops or overheats",
        "P25": "GPS trackers for your delivery vehicles",
    },
    "hi": {
        "P01": "100 Mbps फाइबर - UPI, बिलिंग और कुछ डिवाइस के लिए काफी",
        "P02": "300 Mbps फाइबर - टीम की वीडियो कॉल और क्लाउड ऐप बिना रुकावट",
        "P03": "1 Gbps फाइबर, प्राथमिकता सपोर्ट के साथ",
        "P04": "5G AirFiber - जहाँ फाइबर नहीं है वहाँ भी, लगभग 2 दिन में चालू",
        "P05": "20 Mbps डेडिकेटेड लाइन, 99.5% अपटाइम गारंटी",
        "P06": "100 Mbps डेडिकेटेड लाइन, 99.9% अपटाइम गारंटी",
        "P07": "स्टाफ के लिए बिज़नेस सिम, अनलिमिटेड कॉल, एक ही बिल",
        "P08": "रोमिंग वाले प्रीमियम बिज़नेस सिम",
        "P09": "ऑटो 4G/5G बैकअप - तार कटे तो भी UPI और बिलिंग चालू",
        "P10": "सभी ब्रांच का नेटवर्क एक डैशबोर्ड से",
        "P11": "फिक्स्ड IP - CCTV/सर्वर बाहर से देखने के लिए",
        "P12": "बिज़नेस फोन लाइन जो किसी भी स्टाफ के फोन पर बजे",
        "P13": "टोल-फ्री नंबर - ग्राहक मुफ्त में कॉल करें",
        "P14": "ऑफर और रिमाइंडर के लिए बल्क SMS",
        "P15": "ऑफिशियल WhatsApp Business - कैटलॉग, ऑर्डर और रिमाइंडर",
        "P16": "@आपकाबिज़नेस वाला प्रोफेशनल ईमेल और वीडियो मीटिंग",
        "P17": "1 TB क्लाउड बैकअप - लैपटॉप खोए तो भी रिकॉर्ड सुरक्षित",
        "P18": "आपके डोमेन के साथ तैयार वेबसाइट",
        "P19": "UPI और कार्ड लेने वाला बिलिंग टैबलेट, GST बिल के साथ",
        "P20": "हर डिवाइस के लिए एंटीवायरस",
        "P21": "मैनेज्ड फ़ायरवॉल - हमले पहले ही रुकें",
        "P22": "ग्राहकों के लिए अलग गेस्ट Wi-Fi",
        "P23": "क्लाउड CCTV - फोन पर लाइव देखें",
        "P24": "मशीन रुके या गरम हो तो अलर्ट",
        "P25": "डिलीवरी गाड़ियों के लिए GPS ट्रैकर",
    },
}


def catalogue():
    return {r["product_id"]: r for r in REG.cat.to_dict("records")}


def _eligible(p, prof):
    reasons = []
    if str(prof["city_tier"]) not in p["available_city_tiers"].split(";"):
        reasons.append(f"not sold in tier-{prof['city_tier']} cities")
    if int(prof["employees"]) < int(p["min_employees"]):
        reasons.append(f"needs ≥{p['min_employees']} employees")
    if int(prof["sites"]) < int(p["min_sites"]):
        reasons.append(f"needs ≥{p['min_sites']} sites")
    if p["requires_gstin"] == "Y" and not prof.get("has_gstin"):
        reasons.append("needs an active GSTIN")
    return reasons


def _price(p, seg):
    lo, hi = int(p["price_min_inr_per_month"]), int(p["price_max_inr_per_month"])
    # price-sensitive micro segment gets the floor; others the midpoint of the band
    return lo if seg == "micro" else int(round((lo + hi) / 2 / 10) * 10 - 1 if hi > lo else lo)


def _qty(rule, prof):
    e, s = int(prof["employees"]), int(prof["sites"])
    return {
        "one": 1, "sites": s, "counters": max(1, int(prof.get("counters") or s)),
        "cameras": int(prof.get("cameras") or 4 * s), "users": max(1, int(prof.get("email_users") or min(e, 50))),
        "devices": max(1, int(prof.get("devices") or min(e, 50))), "channels": max(2, math.ceil(e / 10)),
        "machines": int(prof.get("machines") or 5), "vehicles": int(prof.get("vehicles") or 3),
        "lines": int(prof.get("sim_lines") or 0),
    }[rule]


def pick_connectivity(prof):
    seg, e, fibre = prof["segment"], int(prof["employees"]), prof.get("fibre_available", True)
    g, t1 = prof.get("has_gstin"), str(prof["city_tier"]) == "1"
    if seg == "mfg" and e >= 25 and g:
        return "P06"
    if seg in ("mfg", "multi") and e >= 10 and g and prof.get("needs_sla"):
        return "P05"
    if not fibre:
        return "P04"
    if t1 and e >= 15 and g and seg in ("prof", "multi"):
        return "P03"
    if seg in ("prof", "multi", "mfg") or e > 8:
        return "P02"
    return "P01"


def recommend(prof: dict, lang: str = "en") -> dict:
    """prof: segment, city_tier, employees, sites, has_gstin, fibre_available, needs[], sim_lines,
    current_spend, current_vendors"""
    cat = catalogue()
    lines, skipped = [], []
    seg = prof["segment"]

    def add(pid, qty, need=None, optional=False):
        p = cat[pid]
        why_not = _eligible(p, prof)
        if why_not:
            skipped.append({"product_id": pid, "name": p["product_name"], "reason": "; ".join(why_not), "need": need})
            return False
        if any(l["product_id"] == pid for l in lines):
            return True
        unit = _price(p, seg)
        lines.append({
            "product_id": pid, "name": p["product_name"], "category": p["category"], "unit": p["unit"],
            "qty": qty, "unit_price": unit, "list_max": int(p["price_max_inr_per_month"]) * qty, "monthly": unit * qty,
            "setup": int(p["one_time_setup_inr"]) * (qty if p["unit"] in ("per site", "per camera", "per counter", "per device", "per vehicle") else 1),
            "contract_months": int(p["min_contract_months"]), "install_days": int(p["typical_install_days"]),
            "why": WHY.get(lang, WHY["en"])[pid], "optional": optional, "need": need,
        })
        return True

    core = pick_connectivity(prof)
    if not add(core, int(prof["sites"]), "internet"):
        add("P04" if not prof.get("fibre_available", True) else "P01", int(prof["sites"]), "internet")
    if int(prof.get("sim_lines") or 0) > 0:
        add("P08" if prof.get("travel") else "P07", int(prof["sim_lines"]), "mobile")
    for need in prof.get("needs", []):
        if need in NEED_MAP:
            pid, rule = NEED_MAP[need]
            add(pid, _qty(rule, prof), need)
    # data-driven add-on suggestions (toggle off by default)
    if seg in ("multi", "prof") and "failover" not in prof.get("needs", []) and core in ("P01", "P02", "P03"):
        add("P09", int(prof["sites"]), "suggested", optional=True)
    if "upi_pos" in prof.get("needs", []) and "guest_wifi" not in prof.get("needs", []) and core != "P04":
        add("P22", int(prof["sites"]), "suggested", optional=True)

    # dependency check: every requires_one_of must be satisfied by something in the bundle
    ids = {l["product_id"] for l in lines}
    for l in list(lines):
        req = cat[l["product_id"]]["requires_one_of"]
        if req and not ids.intersection(req.split("|")):
            lines.remove(l)
            skipped.append({"product_id": l["product_id"], "name": l["name"], "reason": f"needs one of {req.replace('|', '/')} in the bundle"})
    return {"lines": lines, "skipped": skipped, "segment": SEG_CODE[seg], **quote(lines, prof)}


def quote(lines, prof, toggled_off=()):
    active = [l for l in lines if not (l["optional"] and l["product_id"] not in prof.get("accept_optional", []))
              and l["product_id"] not in toggled_off]
    gross = sum(l["monthly"] for l in active)
    cats = {l["category"] for l in active}
    disc_pct = 10 if len(cats) >= 3 else (5 if len(cats) == 2 else 0)
    disc = round(gross * disc_pct / 100)
    setup = sum(l["setup"] for l in active)
    setup_waived = setup if prof.get("contract_choice", 12) >= 24 else 0
    net = gross - disc
    gst = round(net * 0.18)
    eta = max([l["install_days"] for l in active] or [0])
    separate = sum(l["list_max"] for l in active)
    cur = int(prof.get("current_spend") or 0)
    vendors = int(prof.get("current_vendors") or 0)
    return {
        "active_ids": [l["product_id"] for l in active],
        "monthly_gross": gross, "one_bill_discount_pct": disc_pct, "one_bill_discount": disc,
        "monthly_net": net, "gst_18": gst, "monthly_total_incl_gst": net + gst,
        "setup_total": setup, "setup_waived": setup_waived, "setup_payable": setup - setup_waived,
        "contract_months": max([l["contract_months"] for l in active] + [prof.get("contract_choice", 12)]),
        "activation_eta_days": eta + 1,  # +1 for e-KYC & e-sign, in parallel with site survey
        "bill_swap": {"current_monthly_spend": cur, "current_vendors": vendors,
                      "vendors_after": 1, "monthly_delta": cur - net if cur else None,
                      "same_services_separately": separate, "saving_vs_separate": separate - net},
    }
