"""Smart KYC: OCR extraction + rule-based validation against mock registries.

Every check returns a reason a human can read, so an agent can override with context.
"""
import re
from datetime import date, datetime
from difflib import SequenceMatcher

from PIL import Image, ImageOps
import pytesseract

from registry import REG, gstin_checksum_ok, mask

TODAY = date(2026, 7, 15)  # per dataset README
ADDRESS_PROOF_MAX_AGE_DAYS = 90

GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
UDYAM_RE = re.compile(r"UDYAM-\s?[A-Z]{2}-\s?\d{2}-\s?\d{7}")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

FIELD_LABELS = {
    "gst_certificate": ["GSTIN", "Legal name", "Trade name", "Constitution",
                        "Address of principal", "Date of liability", "Type of registration"],
    "udyam_certificate": ["Udyam reg. number", "Enterprise name", "Enterprise type",
                          "Major activity", "City", "State", "Date of registration"],
    "signatory_id": ["Name", "Designation", "For business", "ID no.", "Valid till"],
    "address_proof": ["Consumer no.", "Billed to", "Supply address", "Bill date", "Amount due"],
}


def _clean(img: Image.Image) -> Image.Image:
    """Drop the pink 'SPECIMEN' watermark: keep only dark, non-reddish pixels (text is near-black)."""
    import numpy as np
    a = np.asarray(img.convert("RGB")).astype(int)
    gray = a.mean(axis=2)
    reddish = (a[..., 0] - a[..., 1]) > 40
    keep = (gray < 110) & ~reddish
    return Image.fromarray(np.where(keep, 0, 255).astype("uint8"))


def blur_score(img: Image.Image) -> float:
    """Variance of a Laplacian - low values mean a blurry photo (ask the owner to retake)."""
    import numpy as np
    g = np.asarray(ImageOps.grayscale(img)).astype(float)
    lap = g[1:-1, 1:-1] * -4 + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


ALL_LABELS = [l.lower() for ls in FIELD_LABELS.values() for l in ls]


def _label_hits(txt: str) -> int:
    t = txt.lower()
    return sum(1 for l in ALL_LABELS if l in t)


def ocr_image(path_or_file) -> dict:
    """Multi-pass OCR: raw, watermark-removed, and deskew attempts; keep the richest read."""
    img = Image.open(path_or_file).convert("RGB")
    quality = {"blur_score": round(blur_score(img), 1), "rotated": 0}
    best = pytesseract.image_to_string(img)
    alt = pytesseract.image_to_string(_clean(img), config="--psm 6")
    combined = best + "\n" + alt
    if _label_hits(best) < 4:  # probably skewed - try small rotations
        for ang in (-8, -5, -3, 3, 5, 8):
            t = pytesseract.image_to_string(img.rotate(ang, expand=True, fillcolor="white"))
            if _label_hits(t) > _label_hits(best):
                best, quality["rotated"] = t, ang
        combined = best + "\n" + alt
    quality["label_hits"] = _label_hits(best)
    return {"text": best, "combined": combined, "quality": quality}


DIGIT_FIX = str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})
ALPHA_FIX = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"})


def normalise_gstin(raw: str) -> str:
    """Fix common OCR confusions using GSTIN positional grammar (2 digits, 5 letters, 4 digits, letter...)."""
    r = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if len(r) != 15:
        return r
    return (r[:2].translate(DIGIT_FIX) + r[2:7].translate(ALPHA_FIX) + r[7:11].translate(DIGIT_FIX)
            + r[11].translate(ALPHA_FIX) + r[12] + "Z" + r[14])


def find_gstin(text: str) -> str | None:
    cands = []
    for line in text.splitlines():
        if "gstin" in line.lower():
            tok = re.sub(r"(?i)gstin", "", line).strip(" :|")
            tok = re.sub(r"[^A-Za-z0-9]", "", tok)
            if len(tok) >= 15:
                cands.append(normalise_gstin(tok[:15]))
    for m in re.finditer(r"\b[0-9OISZ]{2}[A-Z0-9]{5}[0-9OIS]{4}[A-Z0-9]{3}[A-Z0-9]\b", text):
        cands.append(normalise_gstin(m.group(0)))
    for c in cands:  # prefer one that the registry knows
        if REG.gstin(c):
            return c
    return cands[0] if cands else None


def _after(label: str, text: str) -> str | None:
    for line in text.splitlines():
        if line.strip().lower().startswith(label.lower()):
            v = line.strip()[len(label):].strip(" :|")
            if v:
                return v
    # label on its own line, value on the next
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if l.lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1]
    return None


def extract(doc_type: str, text: str) -> dict:
    t = text.replace("|", " ")
    f: dict = {}
    if doc_type == "gst_certificate":
        f["gstin"] = find_gstin(t)
        f["legal_name"] = _after("Legal name", t)
        f["trade_name"] = _after("Trade name", t)
        f["constitution"] = _after("Constitution", t)
        f["date_of_liability"] = (DATE_RE.search(_after("Date of liability", t) or "") or [None])[0] if _after("Date of liability", t) else None
    elif doc_type == "udyam_certificate":
        m = UDYAM_RE.search(t)
        f["udyam_number"] = re.sub(r"\s", "", m.group(0)) if m else None
        f["enterprise_name"] = _after("Enterprise name", t)
        f["city"] = _after("City", t)
        f["state"] = _after("State", t)
        f["major_activity"] = _after("Major activity", t)
        d = DATE_RE.search(_after("Date of registration", t) or "")
        f["date_of_registration"] = d.group(1) if d else None
    elif doc_type == "signatory_id":
        f["name"] = _after("Name", t)
        f["designation"] = _after("Designation", t)
        f["for_business"] = _after("For business", t)
        f["id_no"] = _after("ID no.", t)
        vt = _after("Valid till", t) or ""
        d = DATE_RE.search(vt) or DATE_RE.search(t.split("Valid till")[-1] if "Valid till" in t else "")
        f["valid_till"] = d.group(1) if d else None
    elif doc_type == "address_proof":
        f["billed_to"] = _after("Billed to", t)
        sa = _after("Supply address", t) or ""
        f["supply_address"] = sa
        bd = _after("Bill date", t) or ""
        d = DATE_RE.search(bd)
        f["bill_date"] = d.group(1) if d else None
    return f


def sim(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    na = re.sub(r"[^a-z0-9 ]", "", a.lower()).strip()
    nb = re.sub(r"[^a-z0-9 ]", "", b.lower()).strip()
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _d(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def validate(docs: dict[str, dict], gst_required: bool = True) -> dict:
    """docs: {doc_type: extracted_fields}. Returns checks list + verdict."""
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    for need in ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]:
        if need not in docs:
            sev = "fail" if (need != "udyam_certificate") else "warn"
            if need == "gst_certificate" and not gst_required:
                sev = "warn"
            add(f"{need.replace('_', ' ').title()} present", sev, "Document not uploaded")

    business = None
    gst = docs.get("gst_certificate")
    if gst:
        g = (gst.get("gstin") or "").strip()
        if not g and gst.get("trade_name"):
            hit = REG.find_by_name(gst.get("trade_name"), gst.get("legal_name"))
            if hit:
                g = hit["gstin"]
                add("GSTIN readable", "warn", f"GSTIN unreadable (photo skewed/blurred); matched registry by name -> {mask(g)}. Owner to confirm.")
        if not g:
            add("GSTIN readable", "fail", "Could not read GSTIN or business name - ask for a clearer photo (blur/skew detected)")
        else:
            fmt = bool(re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g))
            add("GSTIN format", "pass" if fmt else "fail", mask(g))
            ok = fmt and gstin_checksum_ok(g)
            rec = REG.gstin(g)
            if not ok and rec is None:
                near = REG.nearest_gstin(g, max_dist=2)
                if near and sim(near.get("trade_name"), gst.get("trade_name")) > 0.85:
                    add("GSTIN checksum", "warn", f"OCR misread {sum(a != b for a, b in zip(g, near['gstin']))} char(s); auto-corrected to registry record {mask(near['gstin'])}")
                    g, rec, ok = near["gstin"], near, True
            if fmt and not (rec and ok) and not gstin_checksum_ok(g):
                add("GSTIN checksum", "fail", "Check digit does not match - GSTIN is invalid or altered")
            elif ok and not any(c["check"] == "GSTIN checksum" for c in checks):
                add("GSTIN checksum", "pass", "Check digit valid")
            if rec is None:
                add("GSTIN registry lookup", "fail", "Not found in GST registry")
            else:
                business = rec.get("trade_name")
                st = rec["status"]
                add("GSTIN status", "pass" if st == "Active" else "fail", f"Registry status: {st}")
                st_ok = sim(gst.get("trade_name"), rec["trade_name"]) > 0.85
                add("Trade name vs registry", "pass" if st_ok else "fail",
                    f"Certificate '{gst.get('trade_name')}' vs registry '{rec['trade_name']}'")
                if gst.get("legal_name"):
                    ln_ok = sim(gst.get("legal_name"), rec["legal_name"]) > 0.9
                    add("Legal name vs registry", "pass" if ln_ok else "fail",
                        f"Certificate '{gst.get('legal_name')}' vs registry '{rec['legal_name']}'" + ("" if ln_ok else " - possible tampering"))
                gst["_resolved_gstin"] = g

    ud = docs.get("udyam_certificate")
    if ud:
        u = ud.get("udyam_number")
        rec = REG.udyam(u) if u else None
        if not u:
            add("Udyam number readable", "fail", "Could not read Udyam number")
        elif rec is None:
            add("Udyam registry lookup", "fail", f"{mask(u)} not found in Udyam registry")
        else:
            add("Udyam registry lookup", "pass", f"{rec['enterprise_name']} · {rec['enterprise_type']} · {rec['nic_description']}")
            for fld, lab in (("major_activity", "Major activity"), ("date_of_registration", "Registration date")):
                if ud.get(fld):
                    okf = (ud[fld] or "").strip().lower() == (rec[fld] or "").strip().lower()
                    add(f"Udyam {lab} vs registry", "pass" if okf else "info",
                        f"Certificate '{ud[fld]}' vs registry '{rec[fld]}'" + ("" if okf else " (informational)"))
            business = business or rec["enterprise_name"]
            if business and sim(rec["enterprise_name"], business) < 0.85:
                add("Udyam name vs GST name", "fail", f"Udyam '{rec['enterprise_name']}' ≠ GST '{business}'")
        if gst and gst.get("_resolved_gstin") and u and u[6:8]:
            st_g = REG.state_of_gst_code(gst["_resolved_gstin"][:2])
            st_u = REG.state_of_udyam_code(u[6:8])
            if st_g and st_u and st_g != st_u:
                add("State consistency (GST vs Udyam)", "fail", f"GST state {st_g} vs Udyam state {st_u}")

    sig = docs.get("signatory_id")
    if sig:
        vt = _d(sig.get("valid_till"))
        if vt is None:
            add("Signatory ID validity", "warn", "Expiry date not readable")
        else:
            add("Signatory ID validity", "pass" if vt >= TODAY else "fail",
                f"Valid till {vt}" + ("" if vt >= TODAY else " - EXPIRED"))
        des = (sig.get("designation") or "").lower()
        if des and not any(k in des for k in ("owner", "partner", "director", "proprietor")):
            add("Signatory authority", "warn", f"Designation '{sig.get('designation')}' - authorisation letter / board resolution needed (e-sign by owner)")
        ref = business or (gst or {}).get("trade_name")
        if ref:
            s = sim(sig.get("for_business"), ref)
            add("Signatory ID business match", "pass" if s > 0.85 else "fail",
                f"ID issued for '{sig.get('for_business')}'")
        if gst and gst.get("legal_name") and "Prop." in (gst.get("legal_name") or ""):
            owner = gst["legal_name"].split("(")[0].strip()
            s = sim(sig.get("name"), owner)
            add("Signatory = proprietor", "pass" if s > 0.8 else "warn",
                f"ID name '{sig.get('name')}' vs proprietor '{owner}'")

    ap = docs.get("address_proof")
    if ap:
        bd = _d(ap.get("bill_date"))
        if bd is None:
            add("Address proof date", "warn", "Bill date not readable")
        else:
            age = (TODAY - bd).days
            add("Address proof recency (≤90 days)", "pass" if age <= ADDRESS_PROOF_MAX_AGE_DAYS else "fail",
                f"Bill dated {bd} - {age} days old")
        ref = business or (gst or {}).get("trade_name")
        if ref:
            s = sim(ap.get("billed_to"), ref)
            add("Address proof name match", "pass" if s > 0.85 else "fail", f"Billed to '{ap.get('billed_to')}'")
        if gst and gst.get("_resolved_gstin"):
            rec = REG.gstin(gst["_resolved_gstin"])
            if rec and ap.get("supply_address"):
                pin_a = re.findall(r"\d{6}", re.sub(r"\s", "", ap["supply_address"]))
                pin_r = re.findall(r"\d{6}", rec["principal_place_of_business"])
                city_ok = any(w.lower() in ap["supply_address"].lower() for w in rec["principal_place_of_business"].split(",")[-2:-1][0].split()) if "," in rec["principal_place_of_business"] else True
                if pin_a and pin_r:
                    add("Address matches GST place of business", "pass" if pin_a[0] == pin_r[0] else "fail",
                        f"PIN on bill {pin_a[0]} vs GST {pin_r[0]}")
                else:
                    city = rec["principal_place_of_business"].split(",")[-2].strip() if rec["principal_place_of_business"].count(",") >= 2 else ""
                    okc = city[:5].lower() in ap["supply_address"].lower()
                    add("Address city matches GST place of business", "pass" if okc else "fail", f"Registry city: {city}")

    checks = [c for c in checks if c["status"] != "info"] + [c for c in checks if c["status"] == "info"]
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    verdict = "APPROVED" if not fails and not warns else ("NEEDS_REVIEW" if not fails else "REJECTED")
    return {"verdict": verdict, "checks": checks, "fail_count": len(fails), "warn_count": len(warns)}
