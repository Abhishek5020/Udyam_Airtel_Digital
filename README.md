# Udyam Saathi: Project Udyam Digital (YTL Hackathon 2026 · Airtel SYNC · Track A)

**Team DevSquad_VITVellore**: Abhishek Anand · Utsav Chauhan (Vellore Institute of Technology, Vellore)

A phone-first, multilingual (Hindi / English) journey that takes a small business from *"what do I need?"* to *"everything is live"* in one sitting:
**Advisor → Quote & checkout → Consent + Smart KYC → Order tracker**, plus a **Saathi back office** for field sales and channel partners.
All data is the synthetic hackathon pack (fictional Accel Telecom).

## Run it (about 2 minutes)
1. Install **Tesseract OCR**:
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki (add it to PATH)
   - macOS: `brew install tesseract`
   - Ubuntu: `sudo apt install tesseract-ocr`
2. Then run:
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend
uvicorn app:app --reload --port 8000
```
3. Open **http://localhost:8000** for the customer app (try `?lang=hi`) and **http://localhost:8000/backoffice.html** for the back office.
API docs are at **http://localhost:8000/docs**.

## What's inside
| Module | Where | Highlights |
|---|---|---|
| Advisor | `backend/engine.py`, `app.py /api/advisor/*` | Deterministic rules engine enforces city tier, min employees/sites, GSTIN requirement and `requires_one_of` dependencies; Hindi/English "why" for every item; Hinglish/Hindi free-text slot filling; skipped items come with a reason |
| Quote | `engine.quote`, `/api/quote` | Band pricing, toggles, One-Bill discount (5/10%), 24-month setup waiver, 18% GST, activation ETA, **Bill-Swap** comparison |
| Smart KYC | `backend/kyc.py`, `/api/kyc/*` | Multi-pass OCR (watermark removal, deskew, blur score) → GSTIN grammar fix + mod-36 checksum → mock GSTIN/Udyam registry → cross-document checks (names, state, PIN/city, bill ≤ 90 days vs 2026-07-15, ID expiry, signatory authority) → APPROVED / NEEDS_REVIEW / REJECTED |
| Mock registries | `backend/registry.py`, `/api/lookup/gstin/{id}`, `/api/lookup/udyam/{id}` | Backed by the CSVs; masked responses |
| Tracker | `/api/orders` | Survey booked at checkout (in parallel with KYC), promise date, milestones, auto-credit per late day, referral code |
| Back office | `frontend/backoffice.html`, `backend/ml.py` | LightGBM propensity on lead-time features (hold-out AUC 0.69, top-20% lift 1.74×), per-lead SHAP reasons, segment economics, partner commissions, advisor drop-offs, masked audit log |
| Privacy | consent ledger, masking, audit log | See `docs/Privacy_Security_Note.pdf` |

## KYC results on the 12 specimen applicants
| ID | Verdict | Main finding |
|---|---|---|
| K01 | REJECTED | GSTIN **Cancelled** in registry; Udyam number missing |
| K02 | NEEDS_REVIEW | Skewed photo: GSTIN unreadable, matched by name for the owner to confirm |
| K03 | APPROVED | - |
| K04 | REJECTED | GST certificate too blurred to read: ask for a retake |
| K05 | NEEDS_REVIEW | Udyam certificate not provided |
| K06 | NEEDS_REVIEW | OCR misread 2 GSTIN characters; auto-matched to the registry record |
| K07 | REJECTED | Legal name on certificate ("Shri Physio Clinic") ≠ registry ("Neelgiri Physio Clinic"): tampering |
| K08/K09 | NEEDS_REVIEW | Signatory is "Office admin": authorisation letter needed |
| K10 | NEEDS_REVIEW | GSTIN 1 character off from the registry record: verify |
| K11 | REJECTED | Address proof is 257 days old (> 90) |
| K12 | APPROVED | - |

## Submission documents (`docs/`)
- `DevSquad_VITVellore_Udyam_Saathi.pptx` / `.pdf`: 7-slide business case on the Airtel SYNC template
- `architecture.png`: solution architecture and data flows
- `Privacy_Security_Note.pdf`: 1-page DPDP privacy and security note
- `DEMO_SCRIPT.md`: 3-minute demo video script
- `screens/`: prototype screenshots

## Production swap-outs
Mock registries → GSTN / Udyam APIs; uploads → DigiLocker pull + Aadhaar e-Sign; the "why" text can be enhanced by an LLM (Hindi plus regional languages) through `engine.WHY`. The LLM never chooses products.
