# -------------------------------------------------------------
# Streamlit app — Análise de Dispositivos BLE/Wi‑Fi (versão 4.3)
# -------------------------------------------------------------
# Requisitos:
#   streamlit pandas matplotlib openpyxl numpy
# -------------------------------------------------------------
# Como executar localmente
#   streamlit run app.py
# -------------------------------------------------------------

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────
# 🔧 Configuração da página
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Análise de Dispositivos (BLE/Wi‑Fi)",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────
# 🔧 Constantes e utilidades
# ──────────────────────────────────────────────────────────────

EXPECTED_COLS = {
    "timestamp": ["timestamp", "time", "date"],
    "mac": ["mac", "mac_address", "address"],
    "rssi": ["rssi", "signal", "power"],
    "device_name": ["name", "device", "device_name"],
}

DEVICE_TYPES = [
    "Smartphone",
    "Fones",
    "Relógio",
    "Computador",
    "Tablet",
    "Sensor",
    "Desconhecido",
]

VENDOR_KEYWORDS = {
    "apple": "Apple",
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "huawei": "Huawei",
    "lenovo": "Lenovo",
    "lg": "LG",
    "google": "Google",
    "motorola": "Motorola",
}

# ──────────────────────────────────────────────────────────────
# 🔍 OUI (pode ser vazio se não fornecido)
# ──────────────────────────────────────────────────────────────

def _load_oui(path: str | Path | None) -> dict[str, str]:
    if path is None or not Path(path).exists():
        return {}
    oui_df = pd.read_csv(path)
    oui_df.columns = oui_df.columns.str.lower()
    mapping: dict[str, str] = {}
    for _, row in oui_df.iterrows():
        mapping[row["prefix"].lower().replace(":", "").replace("-", "")] = row[
            "brand"
        ]
    return mapping


OUI_LOOKUP: dict[str, str] = _load_oui("oui.csv")


# ──────────────────────────────────────────────────────────────
# 🔧 Helpers
# ──────────────────────────────────────────────────────────────

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de colunas e garante existência das esperadas."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    rename_map: dict[str, str] = {}
    for std, variants in EXPECTED_COLS.items():
        for variant in variants:
            if variant in df.columns:
                rename_map[variant] = std
                break
    df = df.rename(columns=rename_map)
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _lookup_brand(mac: str, dev_name: str) -> str:
    """Retorna a marca (Apple, Samsung, etc.) ou Unknown."""
    prefix = mac[:6].lower()
    brand = OUI_LOOKUP.get(prefix)
    if brand:
        return brand
    lower_name = dev_name.lower()
    for kw, vendor in VENDOR_KEYWORDS.items():
        if kw in lower_name:
            return vendor
    return "Unknown"


def _infer_type(name: str, brand: str) -> str:
    n = name.lower()
    b = brand.lower()
    if any(k in n for k in ("bud", "pods", "ear", "head")):
        return "Fones"
    if any(k in n for k in ("watch", "gear", "fit", "band")):
        return "Relógio"
    if any(k in n for k in ("ipad", "tablet")) or "tablet" in b:
        return "Tablet"
    if any(k in n for k in ("macbook", "pc", "laptop", "notebook")) or "comput" in b:
        return "Computador"
    if any(k in n for k in ("tag", "tile", "sensor")):
        return "Sensor"
    if any(k in b for k in ("apple", "samsung", "xiaomi", "huawei", "motorola", "google")):
        return "Smartphone"
    return "Desconhecido"


def _stable_id(row):
    key = f"{row['brand']}|{row['device_type']}|{int(row.get('rssi', 0))}"
    return hashlib.md5(key.encode()).hexdigest()[:10]


# ──────────────────────────────────────────────────────────────
# 📂 Upload
# ──────────────────────────────────────────────────────────────

st.title("📊 Análise de Dispositivos BLE/Wi‑Fi (v4.3)")

uploaded = st.file_uploader(
    "Arraste ou selecione uma planilha (XLSX/CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=False,
)

if uploaded is None:
    st.info("→ Faça upload de uma planilha para começar.")
    st.stop()

try:
    if uploaded.name.lower().endswith("csv"):
        df_raw = pd.read_csv(uploaded)
    else:
        df_raw = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Erro ao ler a planilha: {e}")
    st.stop()

# ──────────────────────────────────────────────────────────────
# 🛠️ Pré‑processamento
# ──────────────────────────────────────────────────────────────

df = _normalise_columns(df_raw)

if df["mac"].isna().all():
    st.error("Nenhuma coluna de MAC foi localizada. Verifique o layout da planilha.")
    st.write("Colunas disponíveis:", list(df.columns))
    st.stop()

# Sanitiza MAC

df["mac_clean"] = (
    df["mac"].astype(str).str.upper().str.replace(r"[^0-9A-F]", "", regex=True)
)

# Marca e tipo

df["brand"] = df.apply(
    lambda r: _lookup_brand(str(r["mac_clean"]), str(r.get("device_name", ""))), axis=1
)

df["device_type"] = df.apply(
    lambda r: _infer_type(str(r.get("device_name", "")), str(r["brand"])), axis=1
)

# ──────────────────────────────────────────────────────────────
# 📈 Gráficos
# ──────────────────────────────────────────────────────────────

ORANGE = "#FFA500"
BLUE = "#1f77b4"

col_type, col_brand = st.columns(2)

with col_type:
    st.subheader("Dispositivos por Tipo (v3)")
    type_counts = (
        df["device_type"].value_counts().reindex(DEVICE_TYPES, fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(6, 4))
    type_counts.plot(kind="bar", ax=ax, color=ORANGE, edgecolor="black")
    ax.set_ylabel("Qtd Dispositivos")
    ax.set_xlabel("")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    st.pyplot(fig)

with col_brand:
    st.subheader("Dispositivos por Marca (Top 15)")
    brand_counts = df["brand"].value_counts().head(15)
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    brand_counts.plot(kind="bar", ax=ax2, color=ORANGE, edgecolor="black")
    ax2.set_ylabel("Qtd Dispositivos")
    ax2.set_xlabel("")
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha="right")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    fig2.tight_layout()
    st.pyplot(fig2)

# ──────────────────────────────────────────────────────────────
# 🔄 Mac switch
# ──────────────────────────────────────────────────────────────

st.subheader("Dispositivos que trocaram de MAC")

df["device_id"] = df.apply(_stable_id, axis=1)

mac_switch_df = (
    df.groupby("device_id")
    .agg(times_seen=("mac_clean", "count"), mac_list=("mac_clean", lambda x: sorted(set(x))))
    .reset_index()
)

mac_switch_df = mac_switch_df[mac_switch_df["mac_list"].str.len() > 1]

st.dataframe(mac_switch_df, use_container_width=True)

st.caption(
    "A heurística usa RSSI arredondado, marca e tipo para agrupar possíveis trocas de MAC. "
    "Ajuste conforme necessidade."
)

# ──────────────────────────────────────────────────────────────
# ⬇️ Download CSV processado
# ──────────────────────────────────────────────────────────────

out_csv = df.to_csv(index=False).encode()

st.download_button(
    "Baixar CSV processado",
    out_csv,
    file_name="analise_dispositivos.csv",
    mime="text/csv",
)
