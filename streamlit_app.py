# -------------------------------------------------------------
# Streamlit app — Análise de Dispositivos BLE/Wi‑Fi (versão 4.6)
# -------------------------------------------------------------
# Requisitos:
#   streamlit pandas matplotlib openpyxl numpy requests
# -------------------------------------------------------------
# Como executar localmente
#   streamlit run app.py
# -------------------------------------------------------------

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
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
    # → coluna com nome/amigável do dispositivo
    "device_name": [
        "name",
        "device",
        "device_name",
        "model",
        "manufacturer",
        "company",
        "vendor",
    ],
    # se o arquivo já trouxer a coluna do tipo não vamos sobrescrever
    "device_type": ["device_type", "type", "category"],
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

# Palavras‑chave para inferir marca se OUI falhar
VENDOR_KEYWORDS = {
    "apple": "Apple",
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "huawei": "Huawei",
    "lenovo": "Lenovo",
    "lg": "LG",
    "google": "Google",
    "motorola": "Motorola",
    "sony": "Sony",
}

# Pequeno dicionário OUI embutido (pode ser expandido)
EMBEDDED_OUI = {
    # Apple
    "dc44d6": "Apple",
    "f0d1a9": "Apple",
    "bc92b6": "Apple",
    "68b6fc": "Apple",
    # Samsung
    "cc07ab": "Samsung",
    "10d1dc": "Samsung",
    "2c4d54": "Samsung",
    "04e8b0": "Samsung",
    # Xiaomi
    "c894d2": "Xiaomi",
    "54ef44": "Xiaomi",
    # Huawei
    "50e59c": "Huawei",
    "84a8e4": "Huawei",
    # Motorola / Lenovo
    "00486a": "Motorola",
    "5cd998": "Lenovo",
    # Amazon
    "a4ee57": "Amazon",
    # Realme / Oppo / OnePlus (BBK)
    "28e02c": "Realme",
    "7c4986": "OnePlus",
}

OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"  # atualizado regularmente (~16 MB)

# ──────────────────────────────────────────────────────────────
# 🔍 OUI — carrega local → remoto → usa EMBEDDED
# ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _load_oui(path: str | Path | None) -> dict[str, str]:
    """Retorna dicionário {prefixo_sem_separador: marca}."""

    mapping: dict[str, str] = EMBEDDED_OUI.copy()

    # 1) arquivo local (ideal para uso offline)
    if path and Path(path).exists():
        try:
            oui_df = pd.read_csv(path)
            mapping.update({
                row["assignment"].replace("-", "").lower(): row["organization_name"].split(" (", 1)[0]
                for _, row in oui_df.iterrows()
            })
            return mapping
        except Exception as exc:
            st.warning(f"Falha ao ler oui.csv local: {exc}")

    # 2) remoto (pode não funcionar em ambientes restritos)
    try:
        r = requests.get(OUI_URL, timeout=10)
        r.raise_for_status()
        df_remote = pd.read_csv(io.StringIO(r.text))
        mapping.update({
            row["Assignment"].replace("-", "").lower(): row["Organization Name"].split(" (", 1)[0]
            for _, row in df_remote.iterrows()
        })
    except Exception:
        st.info("Sem acesso à lista OUI remota — usando somente os prefixos embutidos")

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
            if variant.lower() in df.columns:
                rename_map[variant.lower()] = std
                break
    df = df.rename(columns=rename_map)
    # adiciona colunas faltantes (mas *não* sobrescreve device_type se já existir)
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _lookup_brand(mac: str, dev_name: str) -> str:
    """Retorna a marca ou Unknown."""
    prefix = mac[:6].lower()
    brand = OUI_LOOKUP.get(prefix)
    if brand:
        return brand
    lower_name = str(dev_name).lower()
    for kw, vendor in VENDOR_KEYWORDS.items():
        if kw in lower_name:
            return vendor
    return "Unknown"


def _infer_type(name: str, brand: str) -> str:
    n = str(name).lower()
    b = str(brand).lower()
    # earphones
    if any(k in n for k in ("bud", "pods", "ear", "head", "fone")):
        return "Fones"
    # watches
    if any(k in n for k in ("watch", "gear", "fit", "band", "relog")):
        return "Relógio"
    # tablets
    if any(k in n for k in ("ipad", "tablet")) or "tablet" in b:
        return "Tablet"
    # computers
    if any(k in n for k in ("macbook", "pc", "laptop", "notebook", "desktop")) or "comput" in b:
        return "Computador"
    # sensors / tags
    if any(k in n for k in ("tag", "tile", "sensor", "beacon")):
        return "Sensor"
    # smartphones
    if b in (v.lower() for v in VENDOR_KEYWORDS.values()):
        return "Smartphone"
    return "Desconhecido"


def _stable_id(row):
    key = f"{row['brand']}|{row['device_type']}|{int(row.get('rssi', 0))}"
    return hashlib.md5(key.encode()).hexdigest()[:10]


# ──────────────────────────────────────────────────────────────
# 📂 Upload
# ──────────────────────────────────────────────────────────────

st.title("📊 Análise de Dispositivos BLE/Wi‑Fi (v4.6 — OUI embutido)")

uploaded = st.file_uploader(
    "Arraste ou selecione uma planilha (XLSX/CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=False,
)

if uploaded is None:
    st.info("→ Faça upload de uma planilha para começar.")
    st.stop()

# leitura robusta
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

# ── Marca ────────────────────────────────────────────────────

if "brand" not in df.columns:
    df["brand"] = np.nan

mask_brand_na = df["brand"].isna() | (df["brand"].str.strip() == "")

df.loc[mask_brand_na, "brand"] = df.loc[mask_brand_na].apply(
    lambda r: _lookup_brand(str(r["mac_clean"]), str(r.get("device_name", ""))),
    axis=1,
)

# ── Tipo ─────────────────────────────────────────────────────

if "device_type" not in df.columns:
    df["device_type"] = np.nan

mask_type_na = df["device_type"].isna() | (df["device_type"].str.strip() == "")

df.loc[mask_type_na, "device_type"] = df.loc[mask_type_na].apply(
    lambda r: _infer_type(str(r.get("device_name", "")), str(r["brand"])), axis=1
)

# força categoria conhecida
if not set(df["device_type"].unique()) <= set(DEVICE_TYPES):
    unk_mask = ~df["device_type"].isin(DEVICE_TYPES)
    df.loc[unk_mask, "device_type"] = "Desconhecido"

# ──────────────────────────────────────────────────────────────
# 📈 Gráficos
# ──────────────────────────────────────────────────────────────

ORANGE = "#FFA500"

col_type, col_brand = st.columns(2)

with col_type:
    st.subheader("Dispositivos por Tipo (v3)")
    type_counts = df["device_type"].value_counts().reindex(DEVICE_TYPES, fill_value=0)
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
    "A heurística usa RSSI, marca e tipo para agrupar possíveis trocas de MAC. "
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
