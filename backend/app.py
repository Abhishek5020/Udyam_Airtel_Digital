"""Udyam Digital - FastAPI backend.  Run:  uvicorn app:app --reload  (from backend/)"""
import hashlib
import json
import re
import uuid
from datetime import date, timedelta, datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from registry import REG, DATA, mask, gstin_checksum_ok
from engine import recommend, quote as make_quote, catalogue
from kyc import ocr_image, extract, validate, TODAY
from ml import Propensity

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "backend" / "store.json"
app = FastAPI(title="Udyam Digital API", version="1.0")
MODEL = Propensity()

DB = {"orders": {}, "consents": {}, "sessions": {}, "audit": []}
if STORE.exists():
    DB.update(json.loads(STORE.read_text()))


def save():
    STORE.write_text(json.dumps(DB, indent=1, default=str))


def audit(event, **kw):
    """Audit log never stores raw identifiers - only masked values / hashes (DPDP data minimisation)."""
    DB["audit"].append({"ts": datetime.now().isoformat(timespec="seconds"), "event": event, **kw})
    DB["audit"] = DB["audit"][-500:]


# ---------------------------------------------------------------- advisor
class AdviseIn(BaseModel):
    profile: dict
    lang: str = "en"
    session_id: str | None = None
    partner_code: str | None = None


@app.post("/api/advisor/recommend")
def advise(body: AdviseIn):
    r = recommend(body.profile, body.lang)
    sid = body.session_id or uuid.uuid4().hex[:10]
    DB["sessions"][sid] = {"ts": datetime.now().isoformat(timespec="seconds"), "segment": body.profile.get("segment"),
                           "city_tier": body.profile.get("city_tier"), "employees": body.profile.get("employees"),
                           "lang": body.lang, "quote": r["monthly_net"], "status": "quoted",
                           "partner_code": body.partner_code, "skipped": [s["name"] for s in r["skipped"]]}
    save()
    return {"session_id": sid, **r}


NEED_WORDS = {
    "upi_pos": ["upi", "pos", "billing", "bill", "बिल", "card", "payment", "पेमेंट"],
    "whatsapp": ["whatsapp", "व्हाट्सएप", "catalogue", "catalog", "कैटलॉग"],
    "cctv": ["cctv", "camera", "कैमरा", "सीसीटीवी", "security camera"],
    "cloud_email": ["email", "mail", "ईमेल", "gmail", "office"],
    "security": ["virus", "antivirus", "security", "hack", "सुरक्षा"],
    "failover": ["backup internet", "failover", "down", "बंद", "outage"],
    "guest_wifi": ["guest", "wifi for customers", "customer wifi", "wi-fi", "wifi"],
    "website": ["website", "वेबसाइट", "online"],
    "telephony": ["phone line", "ivr", "call centre", "landline"],
    "sms": ["sms", "message"],
    "iot": ["machine", "मशीन", "iot", "sensor"],
    "fleet": ["vehicle", "gaadi", "गाड़ी", "delivery", "truck", "fleet"],
    "backup": ["data backup", "records", "files", "backup"],
}
SEG_WORDS = {
    "micro": ["kirana", "किराना", "salon", "सैलून", "pharmacy", "medical store", "shop", "दुकान", "dukaan", "bakery", "store"],
    "prof": ["clinic", "क्लिनिक", "doctor", "ca ", "chartered", "coaching", "office", "lawyer", "dental", "diagnostic", "consult"],
    "multi": ["chain", "branches", "outlets", "restaurant", "रेस्टोरेंट", "stores", "branch"],
    "mfg": ["factory", "फैक्ट्री", "manufactur", "unit", "plant", "workshop", "textile", "auto parts"],
}
NUM_WORDS = {"ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "four": 4, "paanch": 5, "five": 5,
             "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5}


class ParseIn(BaseModel):
    text: str


@app.post("/api/advisor/parse")
def parse(body: ParseIn):
    """Lightweight multilingual (English / Hindi / Hinglish) slot filler for the advisor's free-text box."""
    t = " " + body.text.lower() + " "
    out = {"needs": []}
    for seg, ws in SEG_WORDS.items():
        if any(w in t for w in ws):
            out["segment"] = seg
            break
    for need, ws in NEED_WORDS.items():
        if any(w in t for w in ws):
            out["needs"].append(need)
    for w, n in NUM_WORDS.items():
        t = re.sub(rf"(?<![a-zऀ-ॿ]){w}(?![a-zऀ-ॿ])", str(n), t)
    m = re.search(r"(\d+)\s*(people|staff|employees|log|लोग|कर्मचारी|workers|log kaam)", t)
    if m:
        out["employees"] = int(m.group(1))
    m = re.search(r"(\d+)\s*(branches|branch|outlets|stores|sites|shops|दुकानें|ब्रांच|locations)", t)
    if m:
        out["sites"] = int(m.group(1))
    if re.search(r"no gst|gst nahi|gst नहीं|without gst", t):
        out["has_gstin"] = False
    elif "gst" in t or "जीएसटी" in t:
        out["has_gstin"] = True
    if re.search(r"no fib|fibre nahi|fiber nahi|फाइबर नहीं", t):
        out["fibre_available"] = False
    return out


class QuoteIn(BaseModel):
    lines: list
    profile: dict
    toggled_off: list = []


@app.post("/api/quote")
def quote(body: QuoteIn):
    return make_quote(body.lines, body.profile, tuple(body.toggled_off))


@app.get("/api/catalogue")
def get_catalogue():
    return list(catalogue().values())


# ---------------------------------------------------------------- mock registry APIs
@app.get("/api/lookup/gstin/{gstin}")
def lookup_gstin(gstin: str):
    g = gstin.upper().strip()
    fmt = bool(re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g))
    rec = REG.gstin(g)
    audit("gstin_lookup", gstin=mask(g), found=bool(rec))
    return {"gstin": mask(g), "format_ok": fmt, "checksum_ok": fmt and gstin_checksum_ok(g),
            "found": bool(rec), "record": ({**rec, "gstin": mask(g)} if rec else None)}


@app.get("/api/lookup/udyam/{udyam}")
def lookup_udyam(udyam: str):
    rec = REG.udyam(udyam)
    audit("udyam_lookup", udyam=mask(udyam), found=bool(rec))
    return {"found": bool(rec), "record": ({**rec, "udyam_number": mask(rec["udyam_number"])} if rec else None)}


# ---------------------------------------------------------------- KYC
class ConsentIn(BaseModel):
    session_id: str
    purposes: list
    lang: str = "en"


@app.post("/api/kyc/consent")
def consent(body: ConsentIn):
    cid = "CNS-" + uuid.uuid4().hex[:8].upper()
    DB["consents"][cid] = {"session_id": body.session_id, "purposes": body.purposes, "lang": body.lang,
                           "ts": datetime.now().isoformat(timespec="seconds"),
                           "retention": "KYC images deleted 30 days after activation; extracted fields kept for contract term + 8 yrs (statutory)",
                           "withdrawn": False}
    audit("consent_given", consent_id=cid, purposes=body.purposes)
    save()
    return {"consent_id": cid, **DB["consents"][cid]}


@app.post("/api/kyc/consent/{cid}/withdraw")
def withdraw(cid: str):
    if cid not in DB["consents"]:
        raise HTTPException(404)
    DB["consents"][cid]["withdrawn"] = True
    audit("consent_withdrawn", consent_id=cid)
    save()
    return {"ok": True}


DOC_TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]


def _run(files: dict):
    docs, quality = {}, {}
    for t, f in files.items():
        o = ocr_image(f)
        docs[t] = extract(t, o["combined"])
        quality[t] = o["quality"]
    res = validate(docs)
    masked = {t: {k: (mask(v) if k in ("gstin", "udyam_number", "id_no") else v) for k, v in d.items() if not k.startswith("_")}
              for t, d in docs.items()}
    return {"extracted": masked, "quality": quality, **res}


@app.post("/api/kyc/verify")
async def kyc_verify(consent_id: str = Form(...), gst_certificate: UploadFile | None = File(None),
                     udyam_certificate: UploadFile | None = File(None), signatory_id: UploadFile | None = File(None),
                     address_proof: UploadFile | None = File(None)):
    if consent_id not in DB["consents"] or DB["consents"][consent_id]["withdrawn"]:
        raise HTTPException(403, "Consent required before KYC")
    files = {k: v.file for k, v in dict(gst_certificate=gst_certificate, udyam_certificate=udyam_certificate,
                                        signatory_id=signatory_id, address_proof=address_proof).items() if v}
    r = _run(files)  # images processed in memory only - never written to disk
    audit("kyc_verified", consent_id=consent_id, verdict=r["verdict"])
    save()
    return r


@app.get("/api/kyc/sample/{applicant}")
def kyc_sample(applicant: str):
    """Demo helper: run Smart KYC on the specimen documents K01..K12 from the dataset."""
    a = applicant.upper()
    files = {t: str(DATA / "kyc_documents" / f"{a}_{t}.png") for t in DOC_TYPES
             if (DATA / "kyc_documents" / f"{a}_{t}.png").exists()}
    if not files:
        raise HTTPException(404)
    return {"applicant": a, **_run(files)}


@app.get("/api/kyc/sample-image/{name}")
def kyc_image(name: str):
    p = DATA / "kyc_documents" / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- orders / tracker
class OrderIn(BaseModel):
    session_id: str
    business_name: str
    lines: list
    quote: dict
    consent_id: str | None = None
    kyc_verdict: str | None = None
    partner_code: str | None = None
    preferred_slot: str | None = None
    lang: str = "en"


def milestones(start: date, lines: list, kyc_ok: bool):
    """Parallel activation: site survey is booked at checkout, alongside e-KYC, not after it."""
    install = max([l["install_days"] for l in lines] or [1])
    ms = [("Order placed", 0), ("e-KYC verified & e-signed", 0 if kyc_ok else 1),
          ("Site survey (booked at checkout)", 1), ("SIMs dispatched / eSIM live", 1)]
    ms += [(f"{l['name']} installed", l["install_days"]) for l in sorted(lines, key=lambda x: x["install_days"])
           if l["category"] != "Connectivity" or "Postpaid" not in l["name"]]
    ms += [("All services live - one bill, one helpline", install + 1)]
    seen, out = set(), []
    for n, d in ms:
        if n not in seen:
            seen.add(n)
            out.append({"step": n, "promised": str(start + timedelta(days=d)), "done": d == 0})
    return out


@app.post("/api/orders")
def create_order(body: OrderIn):
    oid = "UD" + datetime.now().strftime("%y%m%d") + uuid.uuid4().hex[:4].upper()
    start = TODAY
    active = [l for l in body.lines if l["product_id"] in body.quote.get("active_ids", [])] or body.lines
    o = {"order_id": oid, "business_name": body.business_name, "created": str(start), "lang": body.lang,
         "lines": [{k: l[k] for k in ("product_id", "name", "qty", "monthly", "install_days", "category")} for l in active],
         "monthly_net": body.quote.get("monthly_net"), "milestones": milestones(start, active, body.kyc_verdict == "APPROVED"),
         "promise_date": str(start + timedelta(days=body.quote.get("activation_eta_days", 7))),
         "delay_credit_per_day": round((body.quote.get("monthly_net") or 0) / 30),
         "partner_code": body.partner_code, "referral_code": "REF-" + oid[-4:],
         "session_id": body.session_id, "consent_id": body.consent_id}
    DB["orders"][oid] = o
    if body.session_id in DB["sessions"]:
        DB["sessions"][body.session_id]["status"] = "ordered"
    audit("order_created", order_id=oid, partner=body.partner_code)
    save()
    return o


@app.get("/api/orders/{oid}")
def get_order(oid: str, simulate_day: int = 0):
    o = DB["orders"].get(oid.upper())
    if not o:
        raise HTTPException(404, "Order not found")
    today = TODAY + timedelta(days=simulate_day)
    ms = [{**m, "done": date.fromisoformat(m["promised"]) <= today} for m in o["milestones"]]
    nxt = next((m for m in ms if not m["done"]), None)
    late = max(0, (today - date.fromisoformat(o["promise_date"])).days) if nxt else 0
    return {**o, "milestones": ms, "today": str(today), "next_step": nxt, "days_late": late,
            "auto_credit_inr": late * o["delay_credit_per_day"]}


# ---------------------------------------------------------------- back office
@app.get("/api/backoffice/queue")
def bo_queue(n: int = 40):
    return {"model": MODEL.summary(), "leads": MODEL.queue(n)}


@app.get("/api/backoffice/advisor-dropoffs")
def bo_dropoffs():
    """Advisor sessions that got a quote but no order -> routed to the nearest partner/field rep."""
    return [{"session_id": k, **v} for k, v in DB["sessions"].items() if v.get("status") != "ordered"][-50:]


@app.get("/api/backoffice/partners")
def bo_partners():
    agg = {}
    for o in DB["orders"].values():
        p = o.get("partner_code") or "DIRECT"
        a = agg.setdefault(p, {"partner": p, "orders": 0, "mrr": 0})
        a["orders"] += 1
        a["mrr"] += o.get("monthly_net") or 0
    for a in agg.values():
        a["commission_inr"] = round(a["mrr"] * 0.08 * 12) if a["partner"] != "DIRECT" else 0
    return list(agg.values())


@app.get("/api/backoffice/insights")
def bo_insights():
    d = MODEL.d
    act = d[d.outcome == "Activated"]
    seg = d.groupby("segment").agg(leads=("lead_id", "size"), conv=("outcome", lambda s: round((s == "Activated").mean(), 3))).reset_index()
    val = act.groupby("segment").agg(median_mrr=("monthly_bundle_value_inr", "median"),
                                     churn6m=("churned_within_6_months", lambda s: round((s == "Y").mean(), 3)),
                                     cac=("acquisition_cost_inr", "mean")).reset_index()
    src = d.groupby("lead_source").outcome.apply(lambda s: round((s == "Activated").mean(), 3)).to_dict()
    drops = d.drop_reason.value_counts().head(10).to_dict()
    return {"segments": seg.merge(val, on="segment").round({"median_mrr": 0, "cac": 0, "churn6m": 3}).to_dict("records"), "source_conversion": src,
            "top_drop_reasons": drops, "audit_tail": DB["audit"][-15:]}


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
