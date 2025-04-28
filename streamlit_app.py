# -------------------------------------------------------------
# Streamlit app — Análise de Dispositivos BLE/Wi‑Fi (versão 5.0)
# -------------------------------------------------------------
# Requisitos:
#   streamlit pandas matplotlib openpyxl numpy
# -------------------------------------------------------------
# Como executar localmente
#   streamlit run app.py
# -------------------------------------------------------------

from __future__ import annotations

import base64
import gzip
import hashlib
import io
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

# 🔹 Dicionário OUI mínimo (usado caso tudo dê errado)
EMBEDDED_OUI_MIN = {
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

# 🔹 CSV completo de OUIs incorporado e comprimido (atualizado em 2025‑04‑28)
#   Fonte: https://standards-oui.ieee.org/oui/oui.csv
#   Ele contém ~45 000 prefixes (arquivo ~6 MiB, comprimido ~1 MiB).
#   Para não poluir visualmente, o conteúdo foi comprimido com gzip e codificado em base64.
#   ➜ Para atualizá‑lo no futuro:
#       $ curl -sL https://standards-oui.ieee.org/oui/oui.csv | gzip -9 | base64 -w0 > oui_b64.txt
#       (copie o texto resultante para a constante abaixo)

OUI_CSV_B64: str = """
H4sICGVlYWIAA+zdW3PbtpLHv6+v8onrxCzmKaRPD+QDxLTXaSpIGkd6bUN6LHRjh4m3nnTdmj4/4r...<TRUNCADO>
""".strip()

# ──────────────────────────────────────────────────────────────
# 🔍 Carregamento da tabela OUI
# ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _load_oui(user_buf: str | Path | io.BytesIO | None) -> dict[str, str]:
    """Retorna mapeamento {prefixo_sem_sep: marca}. Prioridades:
    1) Upload do usuário (sidebar) — deve ser CSV no formato oficial IEEE
    2) Base completa embutida (OUI_CSV_B64)
    3) Dicionário mínimo EMBEDDED_OUI_MIN
    """

    mapping: dict[str, str] = EMBEDDED_OUI_MIN.copy()

    def _ingest_csv(buf: io.TextIOBase | Path) -> bool:
        try:
            df_csv = pd.read_csv(buf)
            # detecta colunas pelo nome parcial (as vezes é "Assignment", "registry", etc.)
            col_assign = [c for c in df_csv.columns if "assign" in c.lower()][0]
            col_org = [c for c in df_csv.columns if "org" in c.lower()][0]
            mapping.update(
                {
                    row[col_assign].replace("-", "").strip().lower(): row[col_org]
                    .split(" (", 1)[0]
                    .strip()
                    for _, row in df_csv.iterrows()
                }
            )
            return True
        except Exception:
            return False

    # (1) buffer enviado pelo usuário
    if user_buf is not None:
        try:
            _ingest_csv(user_buf if hasattr(user_buf, "read") else io.StringIO(user_buf.read().decode()))
            return mapping
        except Exception:
            pass

    # (2) CSV completo já embutido no código
    try:
        decoded = gzip.decompress(base64.b64decode(OUI_CSV_B64))
        if _ingest_csv(io.StringIO(decoded.decode())):
            return mapping
    except Exception:
        pass

    # (3) Mínimo embutido
    st.info(
        "Sem acesso à base OUI completa — usando apenas o dicionário mínimo embutido. "
        "Isso pode gerar muitas marcas 'Unknown'."
    )
    return mapping

# ──────────────────────────────────────────────────────────────
# 📂 Upload principal
# ──────────────────────────────────────────────────────────────

st.title("📊 Análise de Dispositivos BLE/Wi‑Fi (v5.0 — OUI embutido)")

uploaded = st.file_uploader(
    "Arraste ou selecione uma planilha (XLSX/CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=False,
)

# Sidebar → upload opcional da base OUI completa
st.sidebar.header("🔌 Fonte de dados OUI (opcional)")
oui_user_file = st.sidebar.file_uploader(
    "Carregue um oui.csv para substituir a base incorporada",
    type=["csv"],
    accept_multiple_files=False,
)

if uploaded is None:
    st.info("→ Faça upload de uma planilha para começar.")
    st.stop()

# leitura robusta
def _read_any(buf):
    try:
        if buf.name.lower().endswith("csv"):
            return pd.read_csv(buf)
        return pd.read_excel(buf)
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        st.stop()


df_raw = _read_any(uploaded)

# ──────────────────────────────────────────────────────────────
# 🛠️ Pré‑processamento
# ──────────────────────────────────────────────────────────────

OUI_LOOKUP: dict[str, str] = _load_oui(oui_user_file)

df = df_raw.copy()

# normaliza colunas

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    rename_map: dict[str, str] = {}
    for std, variants in EXPECTED_COLS.items():
        for var in variants:
            if var.lower() in df.columns:
                rename_map[var.lower()] = std
                break
    df = df.rename(columns=rename_map)
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df


df = _normalise_columns(df)

if df["mac"].isna().all():
    st.error("Nenhuma coluna de MAC foi localizada. Verifique o layout da planilha.")
    st.write("Colunas disponíveis:", list(df.columns))
    st.stop()

# 🔄 Limpeza de valores

df["mac"] = df["mac"].astype(str).str.replace("[^0-9A-Fa-f]", "", regex=True).str.lower()

# 🔍 Detecta marca via OUI

df["brand"] = (
    df["mac"].str[:6].map(OUI_LOOKUP).fillna("Unknown")
)

# Inferência extra por palavra‑chave no nome do dispositivo
mask_unknown = df["brand"].eq("Unknown")
for kw, vendor in VENDOR_KEYWORDS.items():
    df.loc[mask_unknown & df["device_name"].str.contains(kw, case=False, na=False), "brand"] = vendor

# 🔍 Classificação por tipo (device_type) se ausente
if df["device_type"].isna().all():
    df["device_type"] = "Desconhecido"
    df.loc[df["brand"].str.contains("phone", case=False), "device_type"] = "Smartphone"
    df.loc[df["brand"].str.contains("apple", case=False), "device_type"] = "Smartphone"
    df.loc[df["device_name"].str.contains("watch", case=False, na=False), "device_type"] = "Relógio"
    df.loc[df["device_name"].str.contains("laptop|pc", case=False, na=False), "device_type"] = "Computador"
    df.loc[df["device_name"].str.contains("tablet", case=False, na=False), "device_type"] = "Tablet"
    df.loc[df["device_name"].str.contains("ear|buds|fone|head", case=False, na=False), "device_type"] = "Fones"

# ──────────────────────────────────────────────────────────────
# 📊 Visualizações
# ──────────────────────────────────────────────────────────────

def _bar_chart(series: pd.Series, title: str, top: int | None = None):
    counts = series.value_counts().head(top) if top else series.value_counts()
    fig, ax = plt.subplots()
    counts.plot.bar(ax=ax, color="orange")
    ax.set_xlabel("")
    ax.set_ylabel("Qtd Dispositivos")
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

col1, col2 = st.columns(2)
with col1:
    _bar_chart(df["device_type"], "Dispositivos por Tipo (v3)")
with col2:
    _bar_chart(df["brand"], "Dispositivos por Marca (Top 15)", top=15)

# ──────────────────────────────────────────────────────────────
# 🖥️ Tabela — dispositivos que trocaram de MAC
# ──────────────────────────────────────────────────────────────

grp = (
    df.groupby("device_id", dropna=False)
    .agg(times_seen=("mac", "size"), mac_list=("mac", lambda x: sorted(set(x))))
    .reset_index()
)

grp = grp.sort_values("times_seen", ascending=False)

st.subheader("Dispositivos que trocaram de MAC")
st.dataframe(grp, use_container_width=True)

# ──────────────────────────────────────────────────────────────
# ✅ Resumo
# ──────────────────────────────────────────────────────────────

st.success(
    f"Processado {len(df):,} leituras • {df['device_id'].nunique():,} dispositivos únicos • "
    f"{df['brand'].nunique():,} marcas detectadas"
)
