# -------------------------------------------------------------
# Streamlit app — Análise de Dispositivos BLE/Wi‑Fi (versão 4.1)
# -------------------------------------------------------------
# Requisitos:
#   streamlit pandas matplotlib openpyxl numpy
#
# Como executar:
#   streamlit run app.py
# -------------------------------------------------------------

from __future__ import annotations

import hashlib
import io
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config("Analise de Dispositivos Grok", layout="centered")

# -------------------------------------------------------------
# 🔧 Utilidades
# -------------------------------------------------------------

EXPECTED_COLS = {
    "timestamp": ["timestamp", "time", "date"],
    "mac": ["mac", "mac_address", "address"],
    "rssi": ["rssi", "signal", "power"],
    "device_name": ["name", "device", "device_name"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de colunas para evitar KeyError."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    rename_map: dict[str, str] = {}
    for std, variants in EXPECTED_COLS.items():
        for variant in variants:
            if variant in df.columns:
                rename_map[variant] = std
                break
    df = df.rename(columns=rename_map)
    # garante existência
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _load_oui(path: Path | str | None) -> dict[str, str]:
    if path is None or not Path(path).exists():
        return {}
    oui_df = pd.read_csv(path)
    oui_df.columns = oui_df.columns.str.lower()
    return {
        row["prefix"].lower().replace(":", "").replace("-", ""): row["brand"]
        for _, row in oui_df.iterrows()
    }


OUI_LOOKUP: dict[str, str] = _load_oui("oui.csv")

# -------------------------------------------------------------
# 📂 Upload
# -------------------------------------------------------------

st.title("📊 Análise de Dispositivos BLE/Wi‑Fi (v4.1)")

uploaded = st.file_uploader(
    "Suba uma planilha (XLSX/CSV)", type=["xlsx", "csv"], accept_multiple_files=False
)

if uploaded is None:
    st.info("→ Faça upload de uma planilha para começar.")
    st.stop()

# Lê arquivo
if uploaded.name.endswith("csv"):
    df_raw = pd.read_csv(uploaded)
else:
    df_raw = pd.read_excel(uploaded)

# -------------------------------------------------------------
# 🛠️ Pré‑processamento
# -------------------------------------------------------------

df = _normalise_columns(df_raw)

# Remove MAC vazios
df = df.dropna(subset=["mac"])

# Sanitiza MAC (somente hexadecimais, sem separadores)
df["mac_clean"] = (
    df["mac"].astype(str).str.upper().str.replace(r"[^0-9A-F]", "", regex=True)
)

# Descobre marca pelo OUI

def _lookup_brand(mac: str) -> str:
    prefix = mac.replace(":", "").replace("-", "")[:6]
    return OUI_LOOKUP.get(prefix.lower(), "Unknown")


df["brand"] = df["mac_clean"].apply(_lookup_brand)

# Heurística básica de tipo de dispositivo pelos nomes + marca

def _infer_type(row) -> str:
    name = str(row.get("device_name", "")).lower()
    brand = row["brand"].lower()
    if any(k in name for k in ("bud", "pods", "ear", "head")):
        return "Fones"
    if any(k in name for k in ("watch", "gear", "fit", "band")):
        return "Relógio"
    if any(k in name for k in ("ipad", "tablet")) or "tablet" in brand:
        return "Tablet"
    if any(k in name for k in ("macbook", "pc", "laptop", "notebook")):
        return "Computador"
    if any(k in name for k in ("tag", "tile")):
        return "Sensor"
    return "Smartphone"


df["device_type"] = df.apply(_infer_type, axis=1)

# -------------------------------------------------------------
# 📈 Gráficos de distribuição
# -------------------------------------------------------------

stype, sbrand = st.columns(2)

with stype:
    st.subheader("Dispositivos por Tipo")
    type_counts = df["device_type"].value_counts().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6, 4))
    type_counts.plot(kind="bar", ax=ax)
    ax.set_ylabel("Qtd Dispositivos")
    st.pyplot(fig)

with sbrand:
    st.subheader("Dispositivos por Marca")
    brand_counts = df["brand"].value_counts().head(15)
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    brand_counts.plot(kind="bar", ax=ax2, color="orange")
    ax2.set_ylabel("Qtd Dispositivos")
    st.pyplot(fig2)

# -------------------------------------------------------------
# 🔄 Dispositivos que trocaram de MAC
# -------------------------------------------------------------

st.subheader("Dispositivos que trocaram de MAC")

# Agrupa por combinação aproximada de RSSI+marca+tipo para criar um id estável
# (hash para evitar identificação direta)

def _stable_id(row):
    key = f"{row['brand']}|{row['device_type']}|{int(row['rssi'])}"
    return hashlib.md5(key.encode()).hexdigest()[:10]


df["device_id"] = df.apply(_stable_id, axis=1)

mac_switch_df = (
    df.groupby("device_id")
    .agg(times_seen=("mac_clean", "count"), mac_list=("mac_clean", lambda x: sorted(set(x))))
    .reset_index()
)

# Filtra apenas quem tem >1 MAC
mac_switch_df = mac_switch_df[mac_switch_df["mac_list"].str.len() > 1]

st.dataframe(mac_switch_df, use_container_width=True)

st.caption(
    "A heurística usa RSSI arredondado, marca e tipo para agrupar o mesmo dispositivo. Ajuste conforme necessário."
)

# -------------------------------------------------------------
# ☑️ Download opcional (CSV analisado)
# -------------------------------------------------------------

out_csv = df.to_csv(index=False).encode()
st.download_button("Baixar CSV processado", out_csv, file_name="analise_dispositivos.csv", mime="text/csv")
