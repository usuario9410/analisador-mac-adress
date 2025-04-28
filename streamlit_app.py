import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from io import BytesIO

st.set_page_config(page_title="BLE/Wi-Fi Device Analytics", layout="wide")
st.title("📊 BLE / Wi-Fi Device Analytics")

# ── 1 · Uploads ────────────────────────────────────────────────────────────
up_xls = st.file_uploader("📄 Carregue a planilha (.xlsx)", type=["xlsx"])
up_oui = st.file_uploader("📑 (Opcional) tabela OUI (.csv)", type=["csv"])

@st.cache_data(show_spinner=False)
def load_excel(f): return pd.read_excel(f)

@st.cache_data(show_spinner=False)
def load_oui(f):
    df = pd.read_csv(f, names=["oui","org"])
    return {row.oui.upper(): row.org.split()[0] for _, row in df.iterrows()}

if up_xls is None:
    st.info("Envie pelo menos a planilha de resultados para iniciar.")
    st.stop()

df      = load_excel(up_xls)
oui_map = load_oui(up_oui) if up_oui else {}

# ── 2 · Mapas/heurísticas ─────────────────────────────────────────────────
COMPANY_ID_MAP = {
    "4C00": "Apple",    # 0x004C
    "7500": "Samsung",  # 0x0075
    "E000": "Google",   # 0x00E0
    "5701": "Sony",
    "3101": "LG",
    "2D01": "Huawei",
}

def classify_brand(row):
    name = str(row.get("Company Name", ""))
    if name:
        for k in ["Apple","Samsung","Huawei","Xiaomi","OPPO","Realme","Google",
                  "LG","Sony","Dell","HP","Garmin","Microsoft","Intel"]:
            if k.lower() in name.lower(): return k
        return name.split()[0]
    cid = str(row.get("Company ID", "")).upper()
    if cid in COMPANY_ID_MAP: return COMPANY_ID_MAP[cid]
    mac = str(row.get("mac", ""))
    oui = mac.replace(":","").upper()[:6]
    return oui_map.get(oui, "Unknown")

def parse_prod_id(mfg):
    if not isinstance(mfg, str): return (None, None)
    m = re.search(r"FF([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})", mfg)
    return (m.group(1).upper(), int(m.group(2),16)) if m else (None, None)

def classify_type(row):
    _, prod = parse_prod_id(row.get("others",""))
    brand   = row["brand"]
    blob    = " ".join(str(row.get(c,"")) for c in
              ["Name_Type2","Description2","Decoded Value2","UUID Member Name AD16"]).lower()
    if brand == "Apple":
        if prod in [0x12,0x18,0x1C,0x23,0x2E]: return "Watch"
        if prod in [0x19,0x26,0x27,0x37]:      return "Earbuds"
        if prod in [0x33,0x34]:                return "iPad"
        return "Smartphone"
    if brand == "Samsung":
        if "watch" in blob: return "Watch"
        if "buds"  in blob: return "Earbuds"
        return "Smartphone"
    if brand in ["Huawei","Xiaomi","OPPO","Realme","OnePlus","Google","LG","Sony"]:
        return "Smartphone"
    if row.get("rssi", -60) < -80: return "Earbuds/Tag"
    return "Unknown"

# ── 3 · Enriquecimento ────────────────────────────────────────────────────
df["brand"]       = df.apply(classify_brand, axis=1)
df["device_type"] = df.apply(classify_type, axis=1)
df["fingerprint"] = df[["mac","brand","device_type"]].astype(str).agg("-".join, axis=1)

# ── 4 · Visão geral ───────────────────────────────────────────────────────
unique = df.drop_duplicates("fingerprint")

st.subheader("Resumo")
c1, c2 = st.columns(2)
c1.metric("Dispositivos únicos", len(unique))
c2.metric("Marcas identificadas", unique["brand"].nunique())

type_counts  = unique["device_type"].value_counts()
brand_counts = unique["brand"].value_counts().head(15)

fig1, ax1 = plt.subplots(figsize=(6,3))
type_counts.plot(kind="bar", ax=ax1)
ax1.set_ylabel("Quantidade")
ax1.set_title("Distribuição por tipo")
st.pyplot(fig1)

fig2, ax2 = plt.subplots(figsize=(8,3))
brand_counts.plot(kind="bar", ax=ax2)
ax2.set_ylabel("Quantidade")
ax2.set_title("Top 15 marcas")
plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
st.pyplot(fig2)

# ── 5 · Rotações de MAC ───────────────────────────────────────────────────
st.subheader("Rotações de MAC (mesmo dispositivo, MACs diferentes)")
window_m = st.slider("Janela de agrupamento (min)", 1, 30, 15)
rssi_tol = st.slider("RSSI ± dB", 1, 20, 5)

rots = []
grp_cols = ["brand","device_type"]
for _, g in df.groupby(grp_cols):
    g = g.sort_values("timestamp") if "timestamp" in g.columns else g
    base, bucket = None, []
    for _, r in g.iterrows():
        if base is None:
            base, bucket = r, [r["mac"]]; continue
        t_ok = True
        if "timestamp" in g.columns:
            t_ok = abs((r["timestamp"]-base["timestamp"]).total_seconds()) <= window_m*60
        r_ok = abs(float(r.get("rssi",-99))-float(base.get("rssi",-99))) <= rssi_tol
        if t_ok and r_ok:
            bucket.append(r["mac"])
        else:
            if len(set(bucket))>1:
                rots.append({"brand":base["brand"],"type":base["device_type"],
                             "macs":" → ".join(bucket),"trocas":len(set(bucket))-1})
            base, bucket = r,[r["mac"]]
    if len(set(bucket))>1:
        rots.append({"brand":base["brand"],"type":base["device_type"],
                     "macs":" → ".join(bucket),"trocas":len(set(bucket))-1})

rot_df = pd.DataFrame(rots).sort_values("trocas",ascending=False)
st.dataframe(rot_df)

if not rot_df.empty:
    st.download_button("Baixar CSV", rot_df.to_csv(index=False).encode(),
                       "mac_rotations.csv", mime="text/csv")
