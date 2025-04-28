# -------------------------------------------------------------
# Streamlit app — Análise de Dispositivos BLE/Wi‑Fi (versão 4)
# -------------------------------------------------------------
# Requisitos (pip install …):
#   streamlit pandas numpy matplotlib scikit-learn (opcional)
# Arquivos esperados no mesmo diretório:
#   • oui.csv   → tabela OUI→Marca (3 colunas: prefix,brand,vendor)
# -------------------------------------------------------------

import hashlib
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ---------- Config. Streamlit ----------
st.set_page_config(page_title="Análise de Dispositivos Grok", layout="wide")

# ---------- Utilidades ----------
@st.cache_data
def load_oui(path: Path) -> dict:
    """Carrega CSV (prefixo OUI → marca)."""
    if not path.exists():
        st.warning("Arquivo oui.csv não encontrado — marcas ficarão vazias.")
        return {}
    df_oui = pd.read_csv(path)
    df_oui["prefix"] = df_oui["prefix"].str.upper()
    return dict(zip(df_oui["prefix"], df_oui["brand"]))


OUI_MAP = load_oui(Path("oui.csv"))

# Padrões → tipo de dispositivo
DEVICE_PATTERNS = [
    (r"airpod|air[- ]?pods?|pods?$", "Fones"),
    (r"buds?|galaxy\s?buds?", "Fones"),
    (r"watch|galaxy\s?watch|i ?watch|(sm-r\d+)", "Relógio"),
    (r"(mac(book)?|thinkpad|dell|hp|asus|surface)", "Computador"),
    (r"ipad|tablet", "Tablet"),
    (r"(tile|tag|smart\s?tag|nut|airtag)", "Tag"),
    (r"(sensor|ruuvi|switch|door|motion|thermo)", "Sensor"),
]


def classify_device(row: pd.Series) -> str:
    """Retorna o tipo de dispositivo usando heurísticas combinadas."""
    ln = str(row.get("local_name", "")).lower()
    mfg = str(row.get("manufacturer_str", "")).lower()
    uuids = str(row.get("uuids", "")).lower()
    rssi = row.get("rssi", -127)
    interval = row.get("interval_ms", 0)

    # 1) padrões dedicados
    for pat, dtype in DEVICE_PATTERNS:
        if re.search(pat, ln) or re.search(pat, mfg) or re.search(pat, uuids):
            return dtype

    # 2) heurísticas por RSSI / intervalo
    if rssi < -90 and interval < 400:
        return "Tag/Sensor"

    # 3) fallback pelo OUI
    prefix = row.get("mac", "")[:8].upper()  # AA:BB:CC
    brand = OUI_MAP.get(prefix.replace(":", ""), "")
    if brand in {"Apple", "Samsung", "Xiaomi", "Huawei"}:
        return "Smartphone"

    return "Desconhecido"


def brand_from_mac(mac: str) -> str:
    prefix = mac.upper().replace(":", "")[:6]
    return OUI_MAP.get(prefix, "Unknown")


# ---------- MAC‑rotation ----------

def derive_device_id(row: pd.Series) -> str:
    """Gera hash estável para agrupar MACs que rotacionam.
    Usa manufacturer data, local name e prefixo OUI.
    """
    base = (
        row.get("manufacturer_str", "")
        + "|"
        + row.get("local_name", "")
        + "|"
        + row.get("mac", "")[:8]  # mesmo OUI
    )
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def analyse_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    df["mac"] = df["mac"].str.upper()
    df["brand"] = df["mac"].apply(brand_from_mac)
    df["device_type"] = df.apply(classify_device, axis=1)
    df["device_id"] = df.apply(derive_device_id, axis=1)
    return df


# ---------- Gráficos ----------

def bar_chart(counts: pd.Series, title: str, xlabel: str):
    fig, ax = plt.subplots(figsize=(6, 4))
    counts.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Quantidade")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)


# ---------- Interface ----------
st.title("📊 Análise de Dispositivos Grok — v4")

uploaded = st.file_uploader("Suba a planilha .xlsx ou .csv com os pacotes capturados", type=["xlsx", "csv"])

if uploaded:
    if uploaded.name.endswith(".xlsx"):
        raw_df = pd.read_excel(uploaded)
    else:
        raw_df = pd.read_csv(uploaded)

    st.success(f"Arquivo carregado: {uploaded.name} — {len(raw_df)} linhas")

    df = analyse_dataframe(raw_df)

    # --- Gráficos: tipo & marca ---
    col1, col2 = st.columns(2)
    with col1:
        bar_chart(df["device_type"].value_counts().sort_values(ascending=False),
                  "Distribuição por Tipo", "device_type")
    with col2:
        bar_chart(df["brand"].value_counts().head(15),
                  "Top 15 Marcas", "brand")

    # --- Tabela de MAC‑rotation ---
    st.subheader("📑 Dispositivos que trocaram de MAC")
    mac_hist = (
        df.groupby(["device_id", "brand", "device_type"])
          .agg(mac_list=("mac", lambda x: sorted(set(x))),
                mac_changes=("mac", lambda x: len(set(x))-1),
                first_seen=("timestamp", "min"),
                last_seen=("timestamp", "max"))
          .reset_index()
    )
    mac_hist = mac_hist[mac_hist["mac_changes"] > 0]

    st.dataframe(mac_hist, use_container_width=True)

    # --- Download CSV resultante ---
    buff = io.BytesIO()
    mac_hist.to_csv(buff, index=False)
    st.download_button("📥 Baixar tabela (CSV)", buff.getvalue(),
                       file_name="mac_changes.csv", mime="text/csv")
else:
    st.info("⚠️ Nenhum arquivo enviado ainda.")
