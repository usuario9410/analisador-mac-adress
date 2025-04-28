"""Streamlit app — BLE/Wi‑Fi device analysis (v4.7)
-------------------------------------------------
✓ Lê planilha XLSX/CSV gerada pelo analisador Wi‑Fi/BLE
✓ Preenche coluna **brand** automaticamente usando a base IEEE OUI (pacote `ieee-oui`)
✓ Mostra dois gráficos de barras:
    • Dispositivos por **Tipo** (smartphone, fone, etc.)
    • Dispositivos por **Marca** (TOP 15)
✓ Lista de dispositivos que trocaram de MAC (mesmo *device_id*, ≥ 2 MACs)
"""

from __future__ import annotations

import io
from typing import Final

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from ieee_oui import oui_lookup  # ⇢ pip install ieee-oui

# --------------------------------------------------------------------------------------
#  Config Streamlit
# --------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Análise de Dispositivos BLE/Wi‑Fi",
    layout="wide",
    page_icon="📊",
)

st.title("Análise de Dispositivos BLE/Wi‑Fi (v4.7 — OUI embutido)")

uploaded_file = st.file_uploader(
    "Arraste ou selecione uma planilha (XLSX/CSV)", type=["xlsx", "csv"], accept_multiple_files=False
)

# --------------------------------------------------------------------------------------
#  Helper — fabricante a partir do MAC (OUI)
# --------------------------------------------------------------------------------------
def vendor_from_mac(mac: str) -> str:
    """Converte MAC ➜ fabricante usando a base IEEE OUI.
    Retorna "Unknown" caso não encontre ou MAC inválido."""

    if not isinstance(mac, str) or len(mac) < 6:
        return "Unknown"

    try:
        info = oui_lookup(mac)
        name = info.org.strip() if info and info.org else ""
        return name or "Unknown"
    except Exception:
        return "Unknown"


# --------------------------------------------------------------------------------------
#  Funções de visualização
# --------------------------------------------------------------------------------------
def bar_plot(series: pd.Series, title: str, *, top_n: int | None = None):
    """Desenha um gráfico de barras vertical a partir de uma Series index‑>count."""

    if top_n is not None:
        series = series.nlargest(top_n)

    fig, ax = plt.subplots(figsize=(5, 4))
    series.plot.bar(ax=ax, color="#f8a31b")
    ax.set_xlabel("")
    ax.set_ylabel("Qtd Dispositivos")
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", linewidth=0.5)
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)


# --------------------------------------------------------------------------------------
#  Processamento principal
# --------------------------------------------------------------------------------------
if uploaded_file:
    # ---------- leitura ----------
    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=str)
    else:
        df = pd.read_excel(uploaded_file, dtype=str)

    # assegura colunas mínimas
    expected_cols: Final = {"mac", "device_id", "device_type", "brand", "device_name"}
    if not expected_cols.issubset(df.columns):
        st.error(
            f"Planilha não contém todas as colunas esperadas: {sorted(expected_cols)} — "
            f"encontrado: {df.columns.tolist()}"
        )
        st.stop()

    # converte tudo para string e normaliza
    df = df.fillna("")
    for col in ["mac", "device_id", "device_type", "brand", "device_name"]:
        df[col] = df[col].astype(str).str.strip()

    # ---------- completa marca pelo OUI ----------
    mask_unknown = df["brand"].isin(["", "Unknown", "Desconhecido"])
    df.loc[mask_unknown, "brand"] = df.loc[mask_unknown, "mac"].map(vendor_from_mac)

    # ---------- gráficos ----------
    col_tipo, col_marca = st.columns(2)

    with col_tipo:
        tipo_counts = df["device_type"].value_counts().sort_values(ascending=False)
        bar_plot(tipo_counts, "Dispositivos por Tipo (v3)")

    with col_marca:
        marca_counts = df["brand"].value_counts().sort_values(ascending=False)
        bar_plot(marca_counts, "Dispositivos por Marca (Top 15)", top_n=15)

    # ---------- dispositivos com MAC alternado ----------
    mac_list_df = (
        df.groupby("device_id")
        .agg(mac_list=("mac", lambda x: sorted(set(x))), times_seen=("mac", "count"))
        .query("times_seen > 1")
        .sort_values("times_seen", ascending=False)
        .reset_index()
    )

    st.subheader("Dispositivos que trocaram de MAC")
    st.dataframe(mac_list_df, hide_index=True, use_container_width=True)

else:
    st.info("⬆️ Faça upload de um arquivo para iniciar a análise.")
