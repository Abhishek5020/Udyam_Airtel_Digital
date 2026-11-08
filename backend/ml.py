"""Lead propensity model (LightGBM) trained on smb_leads.csv, with per-lead SHAP-style reasons.

Only lead-time features are used (no funnel dates/outcomes) so there is no target leakage.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from registry import DATA, mask

CAT = ["lead_source", "segment", "preferred_language", "annual_turnover_band", "current_internet",
       "current_provider", "contact_role", "state"]
NUM = ["city_tier", "employee_count", "num_sites", "monthly_telecom_spend_inr", "n_interest", "gstin_ok", "has_udyam_b"]

NICE = {"lead_source": "Lead source", "segment": "Segment", "preferred_language": "Language",
        "annual_turnover_band": "Turnover", "current_internet": "Current internet", "current_provider": "Current provider",
        "contact_role": "Contact role", "state": "State", "city_tier": "City tier", "employee_count": "Employees",
        "num_sites": "Sites", "monthly_telecom_spend_inr": "Telecom spend", "n_interest": "# products asked",
        "gstin_ok": "Has GSTIN", "has_udyam_b": "Has Udyam"}


def features(d: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=d.index)
    for c in CAT:
        X[c] = d[c].fillna("NA").astype("category")
    X["city_tier"] = d["city_tier"]
    X["employee_count"] = d["employee_count"]
    X["num_sites"] = d["num_sites"]
    X["monthly_telecom_spend_inr"] = d["monthly_telecom_spend_inr"]
    X["n_interest"] = d["products_of_interest"].fillna("").str.count(";") + d["products_of_interest"].notna().astype(int)
    X["gstin_ok"] = (d["has_gstin"] == "Y").astype(int)
    X["has_udyam_b"] = (d["has_udyam"] == "Y").astype(int)
    return X


class Propensity:
    def __init__(self):
        d = pd.read_csv(DATA / "smb_leads.csv")
        self.d = d
        X, y = features(d), (d["outcome"] == "Activated").astype(int)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y)
        params = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                      subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=7)
        self.model = lgb.LGBMClassifier(**params).fit(Xtr, ytr)
        p = self.model.predict_proba(Xte)[:, 1]
        self.auc = float(roc_auc_score(yte, p))
        order = np.argsort(-p)
        top = order[: len(order) // 5]
        self.lift_top20 = float(yte.iloc[top].mean() / yte.mean())
        self.capture_top20 = float(yte.iloc[top].sum() / yte.sum())
        self.model = lgb.LGBMClassifier(**params).fit(X, y)  # refit on all data for serving
        self.X = X
        self.scores = self.model.predict_proba(X)[:, 1]
        self.contrib = self.model.predict(X, pred_contrib=True)

    def reasons(self, i, k=3):
        c = self.contrib[i][:-1]
        cols = list(self.X.columns)
        idx = np.argsort(-np.abs(c))[:k]
        return [{"feature": NICE[cols[j]], "value": str(self.X.iloc[i, j]), "impact": round(float(c[j]), 3)} for j in idx]

    def queue(self, n=50):
        """Back-office call list: dropped leads with the highest win-back propensity."""
        d = self.d.assign(score=self.scores)
        dropped = d[d["outcome"] == "Dropped"].sort_values("score", ascending=False).head(n)
        out = []
        for i, r in dropped.iterrows():
            out.append({"lead_id": r.lead_id, "business": r.business_name, "segment": r.segment, "city": r.city,
                        "language": r.preferred_language, "stage": r.stage_reached, "drop_reason": r.drop_reason,
                        "source": r.lead_source, "gstin": mask(r.gstin) if isinstance(r.gstin, str) else "-",
                        "score": round(float(r.score), 3), "why": self.reasons(i)})
        return out

    def summary(self):
        return {"auc": round(self.auc, 3), "lift_top20": round(self.lift_top20, 2),
                "capture_top20": round(self.capture_top20, 3), "base_rate": round(float(self.d.outcome.eq('Activated').mean()), 4)}
