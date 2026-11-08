"""Mock GSTIN / Udyam registry APIs + catalogue loader (backed by the hackathon CSVs)."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_ok(g: str) -> bool:
    """Official GSTIN check-digit algorithm (weighted base-36, Luhn mod-36 style)."""
    g = g.upper()
    if len(g) != 15 or any(c not in B36 for c in g):
        return False
    total = 0
    for i, c in enumerate(g[:14]):
        p = B36.index(c) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return B36[(36 - total % 36) % 36] == g[14]


def mask(identifier: str | None) -> str:
    """Show only the first 2 and last 3 characters - used in UI and logs (DPDP minimisation)."""
    if not identifier:
        return ""
    s = str(identifier)
    return s[:2] + "•" * max(0, len(s) - 5) + s[-3:] if len(s) > 6 else "•" * len(s)


class Registry:
    def __init__(self):
        self.g = pd.read_csv(DATA / "mock_gstin_registry.csv", dtype=str).set_index("gstin")
        self.u = pd.read_csv(DATA / "mock_udyam_registry.csv", dtype=str).set_index("udyam_number")
        self.cat = pd.read_csv(DATA / "product_catalogue.csv", dtype=str).fillna("")
        self._gst_state = {k[:2]: v for k, v in zip(self.g.index, self.g["state"])}
        self._ud_state = {k.split("-")[1]: v for k, v in zip(self.u.index, self.u["state"])}

    def gstin(self, g):
        g = (g or "").upper().strip()
        return None if g not in self.g.index else {"gstin": g, **self.g.loc[g].to_dict()}

    def udyam(self, u):
        u = (u or "").upper().replace(" ", "").strip()
        return None if u not in self.u.index else {"udyam_number": u, **self.u.loc[u].to_dict()}

    def nearest_gstin(self, g, max_dist=2):
        best, bd = None, 99
        for k in self.g.index:
            if k[:2] != g[:2] or len(k) != len(g):
                continue
            d = sum(a != b for a, b in zip(k, g))
            if d < bd:
                best, bd = k, d
        return self.gstin(best) if best and bd <= max_dist else None

    def find_by_name(self, trade_name, legal_name=None):
        t = (trade_name or "").strip().lower()
        m = self.g[self.g["trade_name"].str.lower() == t]
        if legal_name and len(m) > 1:
            m2 = m[m["legal_name"].str.lower() == legal_name.strip().lower()]
            m = m2 if len(m2) else m
        return None if len(m) != 1 else self.gstin(m.index[0])

    def state_of_gst_code(self, c):
        return self._gst_state.get(c)

    def state_of_udyam_code(self, c):
        return self._ud_state.get(c)


REG = Registry()
