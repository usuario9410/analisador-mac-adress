
# -*- coding: utf-8 -*-
"""
Analisador de Dispositivos BLE/Wi‑Fi
------------------------------------
• Faz upload de planilha (XLSX ou CSV) contendo, no mínimo, a coluna **mac**
• Usa a base IEEE OUI (via pymanuf) embutida no pacote para deduzir fabricante
• Classifica tipo de dispositivo quando possível
• Gera gráficos simples de distribuição por tipo e por marca
Autor: ChatGPT – 2025‑04
"""
from __future__ import annotations

import io
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from pymanuf import manuf   # ieee‑oui embutido

# --------------------------------------------------------
# Configuração Streamlit
st.set_page_config(page_title="Análise de Dispositivos BLE/Wi‑Fi",
                   page_icon="📶",
                   layout="centered")
st.title("📊 Análise de Dispositivos BLE/Wi‑Fi (OUI embutido)")

# --------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_parser() -> manuf.MacParser:
    """Instancia única do parser de OUIs."""
    return manuf.MacParser()

PARSER = get_parser()

# Vendor extras (inferência por palavra‑chave no nome do device)
VENDOR_KEYWORDS = {
    "esp32": "Espressif",
    "xiaomi": "Xiaomi",
    "samsung": "Samsung",
    "apple": "Apple",
    "huawei": "Huawei",
}

# Classificação de tipo por palavra‑chave
TYPE_KEYWORDS = {
    "phone": "Smartphone",
    "watch": "Relógio",
    "laptop": "Computador",
    "tablet": "Tablet",
    "sensor": "Sensor",
    "camera": "Câmera",
}

def infer_vendor(mac: str) -> str:
    vendor = PARSER.get_manuf(mac) or "Unknown"
    return vendor

def infer_from_keywords(text: str, mapping: dict[str, str]) -> str | None:
    text_low = text.lower()
    for kw, label in mapping.items():
        if kw in text_low:
            return label
    return None

def load_dataframe(buf: io.BytesIO, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(buf)
    else:
        df = pd.read_excel(buf)
    return df

def main() -> None:
    uploaded = st.file_uploader("Arraste ou selecione uma planilha (XLSX/CSV)",
                                type=["xlsx", "csv"])
    if not uploaded:
        st.info("⬆️ Carregue um arquivo para começar")
        return

    df = load_dataframe(uploaded, uploaded.name)
    if "mac" not in df.columns:
        st.error("A planilha deve conter uma coluna chamada **mac**.")
        return

    # Normaliza colunas opcionais
    for col in ["device_name", "device_type", "brand"]:
        if col not in df.columns:
            df[col] = ""

    # ---------- Inferência de fabricante (brand) ----------
    df["brand"] = df["mac"].astype(str).str.upper().str.strip().apply(infer_vendor)

    # Complementa com palavra‑chave se Unknown
    mask_unk = df["brand"].eq("Unknown")
    df.loc[mask_unk, "brand"] = (
        df.loc[mask_unk, "device_name"].astype(str)
          .apply(lambda x: infer_from_keywords(x, VENDOR_KEYWORDS) or "Unknown")
    )

    # ---------- Inferência de tipo ----------
    if df["device_type"].replace("", pd.NA).isna().all():
        df["device_type"] = (
            df["device_name"].astype(str)
              .apply(lambda x: infer_from_keywords(x, TYPE_KEYWORDS) or "Desconhecido")
        )

    # ---------- Métricas ----------
    type_counts = (df["device_type"]
                     .fillna("Desconhecido")
                     .value_counts()
                     .sort_values(ascending=False))

    brand_counts = (df["brand"]
                      .fillna("Unknown")
                      .value_counts()
                      .head(15)
                      .sort_values(ascending=False))

    # ---------- Plot ----------
    col1, col2 = st.columns(2)
    with col1:
        fig1, ax1 = plt.subplots(figsize=(4,3))
        type_counts.plot.bar(ax=ax1)
        ax1.set_xlabel("")
        ax1.set_ylabel("Qtd dispositivos")
        ax1.set_title("Dispositivos por Tipo")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig1)

    with col2:
        fig2, ax2 = plt.subplots(figsize=(4,3))
        brand_counts.plot.bar(ax=ax2)
        ax2.set_xlabel("")
        ax2.set_ylabel("Qtd dispositivos")
        ax2.set_title("Dispositivos por Marca (Top 15)")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig2)

    # ---------- Pré‑visualização ----------
    with st.expander("🔍 Pré‑visualizar Tabela"):
        st.dataframe(df.head(200))

    # ---------- Download ----------
    out = io.BytesIO()
    df.to_excel(out, index=False, engine="openpyxl")
    st.download_button("⬇️ Baixar resultado (XLSX)", data=out.getvalue(),
                       file_name="resultado_analise.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    main()
