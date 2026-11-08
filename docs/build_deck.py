"""Builds the 7-slide submission deck on the Airtel SYNC template."""
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

TPL, BG, SCR, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
RED, INK, MUT, WHITE, GREEN, LIGHT = (RGBColor(0xE4, 0, 0), RGBColor(0x1D, 0x1D, 0x1F), RGBColor(0x5F, 0x5F, 0x66),
                                      RGBColor(255, 255, 255), RGBColor(0x0A, 0x8A, 0x43), RGBColor(0xFF, 0xF1, 0xF1))
GREY = RGBColor(0xF3, 0xF3, 0xF6)
prs = Presentation(TPL)
cover = prs.slides[0]
# drop template's blank content slide; we re-create content slides with its background
sldIdLst = prs.slides._sldIdLst
rid = sldIdLst[1].rId
prs.part.drop_rel(rid)
sldIdLst.remove(sldIdLst[1])
FONT = "Arial"


def tb(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, margin=0.04):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(margin))
    for i, p in enumerate(paras):
        if isinstance(p, str):
            p = (p,)
        text, size, bold, color = (list(p) + [None] * 4)[:4]
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        runs = text if isinstance(text, list) else [(text, bold)]
        for rt, rb in runs:
            r = para.add_run()
            r.text = rt
            r.font.name = FONT
            r.font.size = Pt(size or 10)
            r.font.bold = bool(rb)
            r.font.color.rgb = color or INK
        para.space_after = Pt(2)
    return box


def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = fill
    if line:
        r.line.color.rgb = line
        r.line.width = Pt(1)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        r.adjustments[0] = radius
    return r


def card(s, x, y, w, h, title, body, fill=GREY, tcol=RED, tsize=10.5, bsize=8.5, line=None):
    rect(s, x, y, w, h, fill, line)
    paras = [(title, tsize, True, tcol)] + [(b, bsize, False, INK) if isinstance(b, str) else b for b in body]
    tb(s, x + 0.07, y + 0.05, w - 0.14, h - 0.08, paras)


def new_slide(title, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[10])
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    s.shapes.add_picture(BG, 0, 0, prs.slide_width, prs.slide_height)
    tb(s, 0.4, 0.5, 9.2, 0.4, [(title, 18, True, INK)])
    if kicker:
        tb(s, 0.4, 0.86, 9.2, 0.3, [(kicker, 10, False, MUT)])
    return s


# ---------------------------------------------------------------- 1 cover
tb(cover, 0.45, 2.55, 4.8, 0.55, [("Udyam Saathi", 30, True, WHITE)])
tb(cover, 0.45, 3.1, 4.5, 0.75, [("A phone-first, multilingual journey that takes a small business from “what do I need?” to “everything is live” in one sitting", 11.5, False, WHITE)])
rect(cover, 0.45, 3.95, 0.05, 0.85, RED, shape=MSO_SHAPE.RECTANGLE)
tb(cover, 0.6, 3.92, 4.6, 0.95, [
    ("Track A · Project Udyam Digital (Accel Business)", 10, True, WHITE),
    ("Team DevSquad_VITVellore", 10, True, RGBColor(0xFF, 0x8A, 0x8A)),
    ("Abhishek Anand · Utsav Chauhan", 10, False, WHITE),
    ("Vellore Institute of Technology, Vellore", 9.5, False, RGBColor(0xDD, 0xDD, 0xDD))])

# ---------------------------------------------------------------- 2 problem
s = new_slide("The problem isn’t demand. It’s four human hand-offs.",
              "What 5,000 SMB leads (Apr–Jun 2026) tell us - every number below is computed from smb_leads.csv")
funnel = [("Leads", 5000), ("Contacted", 3406), ("Needs assessed", 1974), ("Quote accepted", 861), ("KYC complete", 588), ("Activated", 368)]
y = 1.25
for i, (n, v) in enumerate(funnel):
    w = 3.1 * v / 5000 + 0.25
    rect(s, 0.4, y, w, 0.34, RED if i == 5 else RGBColor(0xF2, 0x8C, 0x8C) if i else RGBColor(0xE4, 0x5A, 0x5A), shape=MSO_SHAPE.RECTANGLE)
    tb(s, 0.45 + w, y + 0.02, 1.7, 0.32, [([(f"{v:,} ", True), (n, False)], 9.5, None, INK)])
    y += 0.42
tb(s, 0.4, y + 0.02, 3.9, 0.7, [("7.4% lead→activation · 17.6 days · 3 status-chase calls · ₹15,053 CAC per activated SMB", 9.5, True, RED)])
X, W, H = 4.55, 2.5, 1.0
tiles = [
    ("1,632 leads (33%) lost before any conversation", ["Unreachable after 3 attempts (805), owner had no time for a visit (531), visit never scheduled (296). The sales visit is the bottleneck."]),
    ("385 lost to the quote itself", ["“Quote too complex” (206) + “took too long” (179). A 3–5 day PDF with product codes loses the owner."]),
    ("Referrals convert 5× better", ["Referral 14.8% vs WhatsApp campaign 2.8% and web form 4.3%. Trust travels shop-to-shop, not through ads."]),
    ("Chasing status drives churn", [">3 follow-up calls → 23% churn in 6 months and NPS 6.4; ≤1 call → 5.9% churn, NPS 7.5. Silence after purchase is the real cost."]),
    ("GSTIN = 4.7× activation", ["9.6% with GSTIN vs 2.0% without. KYC & GST-gated products block the long tail."]),
    ("Micro is 54% of leads but loses money", ["4.1% conversion, ₹2,470 median bundle, 22.7% churn - at ₹15k CAC it never pays back."]),
]
for i, (t, b) in enumerate(tiles):
    cx, cy = X + (i % 2) * (W + 0.1), 1.2 + (i // 2) * (H + 0.08)
    card(s, cx, cy, W, H, t, b, fill=LIGHT if i % 3 == 0 else GREY, tsize=9.5, bsize=8.2)
rect(s, 0.4, 4.55, 9.2, 0.42, INK)
tb(s, 0.5, 4.57, 9.0, 0.38, [([("Our bet: ", True), ("remove the hand-offs (visit, PDF quote, paper KYC, status calls) with software - and turn the field force and partners into paid “Saathis” instead of competitors.", False)], 10, None, WHITE)], anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- 3 solution
s = new_slide("Udyam Saathi: discover → buy → verify → track, on a phone, in ~10 minutes",
              "One journey, in the owner’s language, with a human one tap away - never in the way")
steps = [("① Advisor", "6 tap-questions or one sentence in Hindi/Hinglish (“kirana hai, 3 log, UPI aur CCTV chahiye”). GSTIN lookup pre-fills the business. Rules engine builds an eligible bundle and explains every item in plain words."),
         ("② Quote & checkout", "One monthly price incl. GST. Toggle add-ons, live re-price. One-Bill discount (5–10%), 24-month option waives setup. Ineligible items shown with the reason and how to unlock."),
         ("③ Consent + Smart KYC", "DPDP consent screen first. Snap 4 documents (or DigiLocker). OCR + GSTIN checksum + registry cross-checks give a verdict in seconds; only flagged items go to a human."),
         ("④ Tracker", "A promised live-date from install days, site survey booked at checkout (parallel to KYC), milestone timeline, automatic bill credit for every late day, one-tap consent withdrawal.")]
for i, (t, b) in enumerate(steps):
    card(s, 0.4 + i * 2.32, 1.2, 2.2, 1.55, t, [b], fill=LIGHT, tsize=11, bsize=8.3)
tb(s, 0.4, 2.85, 9.2, 0.3, [("What makes it different (and hard to copy)", 12, True, RED)])
diffs = [("Bill-Swap mirror", "Shows the same services bought separately vs. one Accel bill - e.g. Dukaan bundle saves ₹1,759/month and collapses 3 vendors into 1."),
         ("Rules-first GenAI", "Deterministic engine enforces tier, size, GSTIN and requires_one_of; language layer only explains. No hallucinated SKUs - every judge scenario is reproducible."),
         ("Parallel activation + late-day credit", "Survey booked at checkout, not after KYC. Missed promise date = automatic credit, so the owner never needs to call."),
         ("Saathi partner co-pilot", "Field reps and local partners share advisor links with their code and earn 8% of year-1 MRR on digital closes."),
         ("Win-back propensity queue", "LightGBM on lead-time features ranks dropped leads with SHAP reasons, so reps call the right 20% first (1.74× lift)."),
         ("Shop-to-shop referral loop", "Every live customer gets a WhatsApp referral link - both get a free month. Leans into the 14.8% referral channel.")]
for i, (t, b) in enumerate(diffs):
    cx, cy = 0.4 + (i % 3) * 3.08, 3.2 + (i // 3) * 0.92
    card(s, cx, cy, 2.98, 0.84, t, [b], tsize=9.5, bsize=7.9)

# ---------------------------------------------------------------- 4 prototype
s = new_slide("Working prototype - built and tested on the hackathon dataset",
              "FastAPI + Tesseract OCR + LightGBM + mobile web app · repo: github.com/Abhishek5020/Udyam_Airtel_Digital")
shots = [("1_advisor_hi.png", "Hindi advisor: free text parsed, GSTIN pre-fills business"),
         ("2_quote_hi.png", "Transparent quote, toggles, One-Bill discount, Bill-Swap savings"),
         ("3b_kyc_K07_rejected.png", "Smart KYC catches tampered legal name (K07)"),
         ("4b_tracker_late_credit.png", "Tracker: promise date, milestones, auto-credit if late"),
         ("5_backoffice.png", "Saathi back office: win-back queue with SHAP reasons")]
from PIL import Image
x = 0.4
for i, (f, cap) in enumerate(shots):
    im = Image.open(f"{SCR}/{f}")
    w_px, h_px = im.size
    if i < 4:
        crop_h = int(w_px * 1.62)
        im.crop((0, 0, w_px, min(h_px, crop_h))).save(f"/tmp/_c{i}.png")
        pw = 1.45
    else:
        im.crop((0, 0, w_px, int(w_px * 0.62))).save(f"/tmp/_c{i}.png")
        pw = 2.95
    pic = s.shapes.add_picture(f"/tmp/_c{i}.png", Inches(x), Inches(1.2), width=Inches(pw))
    if pic.height > Inches(2.6):
        ratio = Inches(2.6) / pic.height
        pic.height, pic.width = Inches(2.6), int(pic.width * ratio)
    pic.line.color.rgb = RGBColor(0xDD, 0xDD, 0xE2)
    tb(s, x, 1.2 + pic.height / 914400 + 0.04, pic.width / 914400, 0.45, [(cap, 7.8, False, MUT)])
    x += pic.width / 914400 + 0.12
results = [("4 required modules + 2 stretch goals", "Advisor, Quote & checkout, Smart KYC, Tracker + Saathi back office and lead propensity score; WhatsApp share & deep-links"),
           ("Smart KYC on the 12 specimen applicants", "Flags cancelled GSTIN (K01), skewed photo (K02), blurred certificate (K04), missing Udyam (K05), altered legal name (K07), 257-day-old bill (K11); signatory authority checks"),
           ("Advisor eligibility, provably", "No-GSTIN micro shop: WhatsApp API, SMS, firewall withheld with reasons + free GST-help path; dependencies (CCTV needs broadband) auto-checked"),
           ("Propensity model, honestly evaluated", "Hold-out AUC 0.69; top-20% call list captures 35% of activations (1.74× lift). Lead-time features only - no leakage")]
for i, (t, b) in enumerate(results):
    card(s, 0.4 + i * 2.32, 4.2, 2.2, 0.85, t, [b], fill=LIGHT, tsize=8.5, bsize=7.2)

# ---------------------------------------------------------------- 5 architecture + privacy
s = new_slide("Architecture, Smart KYC and privacy-by-design",
              "Every component below runs in the prototype; mocked registries swap for GSTN / Udyam / DigiLocker / e-Sign APIs in production")
s.shapes.add_picture(f"{SCR}/../architecture.png", Inches(0.4), Inches(1.18), width=Inches(6.05))
card(s, 6.6, 1.18, 3.0, 1.75, "Smart KYC pipeline", [
    "1. Multi-pass OCR: watermark removal, deskew (±8°), blur score",
    "2. GSTIN grammar fix + official mod-36 check digit",
    "3. Mock GSTIN/Udyam lookup: status, legal & trade name, state",
    "4. Cross-document: ID & bill name, bill ≤90 days, PIN/city, ID expiry, signatory authority",
    "→ APPROVED / NEEDS REVIEW / REJECTED, each with a reason"], fill=GREY, tsize=10, bsize=7.6)
card(s, 6.6, 3.0, 3.0, 2.0, "DPDP Act 2023 choices", [
    "• Consent screen before any upload; purpose-tagged ledger; marketing opt-in OFF by default",
    "• Minimisation: only 4 legally required docs; images processed in memory",
    "• GSTIN / ID / Udyam masked in UI, API and logs (37••••••1ZU)",
    "• Retention: images deleted 30 days after activation; fields kept only as law requires",
    "• One-tap withdrawal + audit log of every lookup"], fill=RGBColor(0xE9, 0xF7, 0xEF), tcol=GREEN, tsize=10, bsize=7.6)
tb(s, 0.4, 4.4, 6.0, 0.6, [("Design rule: the catalogue rules decide WHAT is sold; GenAI decides only HOW it is explained. This keeps recommendations auditable, compliant and identical across all 15 live test scenarios.", 8.5, True, INK)])

# ---------------------------------------------------------------- 6 business case
s = new_slide("Who first, what bundle, at what price",
              "Bundles priced by the prototype’s engine from product_catalogue.csv (excl. 18% GST); segment economics from smb_leads.csv")
rows = [("Segment", "Data (conv · MRR · 6m churn · CAC)", "Priority & channel", "Hero bundle", "₹/month", "Contract"),
        ("Professional offices\nclinic, CA, coaching", "11.1% · ₹6,575 · 13.8% · ₹4.2k", "#1 - fully digital, highest volume × value", "Clinic & Office Pro: Fibre 300, 2 SIMs, email + antivirus ×10, 1 TB backup, failover, guest Wi-Fi", "5,917", "12–24m"),
        ("Small multi-site\nrestaurant / store chain", "11.0% · ₹28,080 · 10.8% · ₹9.1k", "#2 - digital quote, Saathi-assisted close", "Chain One-Bill (5 outlets): fibre, POS, 10 CCTV, guest Wi-Fi + failover per site, email ×10", "32,269", "24m"),
        ("Micro retail & services\nkirana, salon, pharmacy", "4.1% · ₹2,470 · 22.7% · ₹2.7k", "#3 - self-serve only (CAC must be <₹1.5k); referral loop", "Dukaan Digital: Fibre 100, 2 SIMs, UPI POS, WhatsApp API, 2 CCTV · Lite (no GSTIN): AirFiber, SIM, POS ₹1,707", "3,234", "12m (24m = setup free)"),
        ("Small manufacturers\nauto-parts, textile", "12.8% · ₹15,910 · 8.1% · ₹9.6k", "#4 - partner-led; advisor used as a sizing tool", "Factory Connect: Leased Line 100, 5 SIMs, 10 IoT sensors, firewall, email ×10", "33,861", "24m")]
cw = [1.45, 1.55, 1.6, 3.05, 0.65, 0.9]
y = 1.2
for ri, row in enumerate(rows):
    h = 0.28 if ri == 0 else 0.56
    x = 0.4
    for ci, val in enumerate(row):
        rect(s, x, y, cw[ci] - 0.03, h - 0.03, INK if ri == 0 else (LIGHT if ri % 2 else GREY), shape=MSO_SHAPE.RECTANGLE)
        tb(s, x + 0.02, y, cw[ci] - 0.07, h, [(val, 7.6 if ri else 8, ri == 0 or ci in (0, 4), WHITE if ri == 0 else (RED if ci == 4 else INK))], anchor=MSO_ANCHOR.MIDDLE)
        x += cw[ci]
    y += h
card(s, 0.4, 3.85, 3.0, 1.15, "Value to the owner", [
    "One bill, one helpline, one app instead of 3–6 vendors",
    "Bill-Swap: 18–35% cheaper than buying the same services separately",
    "Live in ~6 days (vs 17.6) with a dated promise"], fill=LIGHT, tsize=9.5, bsize=7.8)
card(s, 3.5, 3.85, 3.0, 1.15, "Value to Accel (assumptions labelled)", [
    "Self-serve CAC est. ₹1.5–3k vs ₹15k blended today",
    "At 40% contribution margin*, micro payback falls from ~15 months to ~2–3",
    "Suggested add-ons lift attach: target 5.5 products per bundle vs 4.5 today"], fill=GREY, tsize=9.5, bsize=7.8)
card(s, 6.6, 3.85, 3.0, 1.15, "Role of field force & partners", [
    "Saathis: share advisor links, earn 8% of yr-1 MRR on digital closes",
    "Field sales: multi-site & manufacturers + top-20% win-back queue",
    "Partners do installs and doorstep KYC help for the non-digital owner"], fill=GREY, tsize=9.5, bsize=7.8)
tb(s, 0.4, 5.0, 6, 0.2, [("*Assumed margin for illustration; not in the dataset.", 6.5, False, MUT)])

# ---------------------------------------------------------------- 7 metrics, rollout, risks
s = new_slide("How we’ll measure it, roll it out, and what could go wrong",
              "Targets set against the Apr–Jun 2026 baseline from smb_leads.csv")
mets = [("Metric", "Today", "6-month target"),
        ("Lead → activation", "7.4%", "15%"),
        ("Avg time to activate", "17.6 days", "≤ 6 days"),
        ("Blended CAC / activated SMB", "₹15,053", "≤ ₹6,000"),
        ("6-month churn", "15.2%", "≤ 9%"),
        ("Status-chase calls / customer", "3", "≤ 0.5")]
y = 1.2
for ri, (a, b, c) in enumerate(mets):
    for ci, (val, w, x) in enumerate(((a, 1.85, 0.4), (b, 0.8, 2.25), (c, 0.95, 3.05))):
        rect(s, x, y, w - 0.03, 0.33, INK if ri == 0 else (LIGHT if ci == 2 else GREY), shape=MSO_SHAPE.RECTANGLE)
        tb(s, x + 0.03, y, w - 0.08, 0.33, [(val, 8.6, ri == 0 or ci == 2, WHITE if ri == 0 else (RED if ci == 2 else INK))], anchor=MSO_ANCHOR.MIDDLE)
    y += 0.36
tb(s, 0.4, 3.4, 3.6, 0.5, [("North star: activated MRR per ₹ of acquisition spend. Guardrails: NPS ≥ 7.5, KYC false-approve rate < 0.5%.", 8.2, True, INK)])
card(s, 0.4, 3.95, 3.6, 1.05, "Rollout", [
    "Wk 0–8 · Pilot: Pune (T1) + Jaipur (T2), professional offices + micro, Hindi/Marathi, 20 partner Saathis",
    "Q2 · 10 cities, 6 languages, WhatsApp front end, DigiLocker + e-Sign live",
    "Q3–Q4 · National; voice advisor; partner app; propensity-led outbound"], fill=LIGHT, tsize=9.5, bsize=7.6)
risks = [("OCR misreads / forged documents", "Registry is the source of truth; checksum + name/state/date cross-checks; NEEDS REVIEW queue with 2-hour human SLA; DigiLocker pull removes uploads"),
         ("Partners see digital as a threat", "Partner code on every link, commission on digital closes, leaderboard; partners own installs & doorstep help"),
         ("GenAI recommends something ineligible", "LLM never selects SKUs; rules engine + dependency check is the only path to a quote; regression-tested scenarios"),
         ("Promise dates missed (install capacity)", "ETA from real install slots per city; auto-credit makes delays costly internally, so ops fixes capacity"),
         ("DPDP non-compliance / data breach", "Consent ledger, purpose limits, masking, 30-day image deletion, audit log, encryption at rest & in transit"),
         ("Micro churn stays high", "Proactive tracker + one helpline (≤1 chase call = 5.9% churn); usage nudges on WhatsApp after go-live")]
tb(s, 4.2, 1.15, 5.4, 0.3, [("Risks & mitigations", 12, True, RED)])
for i, (r, m) in enumerate(risks):
    cy = 1.48 + i * 0.59
    rect(s, 4.2, cy, 5.4, 0.53, GREY)
    tb(s, 4.27, cy + 0.02, 1.65, 0.5, [(r, 8.2, True, INK)], anchor=MSO_ANCHOR.MIDDLE)
    tb(s, 5.95, cy + 0.02, 3.6, 0.5, [(m, 7.6, False, INK)], anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
