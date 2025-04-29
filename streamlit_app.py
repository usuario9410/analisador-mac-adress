#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisador de endereços MAC — Streamlit App
Autor: você 😉
"""

from pathlib import Path
import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────
#  Função de lookup de fabricante (OUI)
# ──────────────────────────────────────────────────────────────
try:
    # método principal – usa pacote pymanuf (precisa estar no requirements)
    from pymanuf.manuf import manuf
    _parser = manuf.MacParser()
    def get_vendor(mac: str) -> str:
        """Retorna o fabricante (ou 'Unknown') dado o MAC (string)."""
        return _parser.get_manuf(mac) or "Unknown"

except ModuleNotFoundError:
    # fallback caseiro: lê tabela OUI local (assets/oui.csv)
    import csv, importlib.resources as pkg

    OUI = {}
    path_csv = pkg.files("assets").joinpath("oui.csv")
    with path_csv.open() as f:
        for prefix, vendor in csv.reader(f):
            OUI[prefix.upper()] = vendor.strip()

    def get_vendor(mac: str) -> str:
        return OUI.get(mac[:8].upper(), "Unknown")

# inferência extra por palavra-chave no nome
VENDOR_KEYWORDS = {
    "esp": "Espressif (ESP-32)",
    "rasp": "Raspberry Pi",
}

# ──────────────────────────────────────────────────────────────
#  Configuração da página
# ──────────────────────────────────────────────────────────────
st.set_page_config("🔎 Analisador de MAC", layout="wide")
st.title("🔎 Analisador de Endereços MAC")
st.caption("Arraste um arquivo CSV ou Excel para identificar fabricantes 🎉")

# ──────────────────────────────────────────────────────────────
#  Upload & leitura
# ──────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Planilha de entrada", type=["csv", "xlsx", "xls"])
if not uploaded:
    st.stop()

suffix = Path(uploaded.name).suffix.lower()
if suffix in (".xlsx", ".xls"):
    df = pd.read_excel(uploaded)
else:
    df = pd.read_csv(uploaded)

# normaliza nomes de colunas esperadas
cols = {c.lower(): c for c in df.columns}
mac_col   = cols.get("mac") or cols.get("mac_address") or cols.get("address")
name_col  = cols.get("name") or cols.get("device_name") or cols.get("host")

df.rename(columns={mac_col: "mac", name_col: "device_name"}, inplace=True)

# ──────────────────────────────────────────────────────────────
#  Limpeza + enriquecimento
# ──────────────────────────────────────────────────────────────
df["mac"] = (
    df["mac"]
    .astype(str)
    .str.replace("[-:]", "", regex=True)   # remove separadores
    .str.upper()
    .str[:12]                              # garante 6 bytes = 12 hex
)

df["brand"] = df["mac"].apply(get_vendor)

# completa usando palavras-chave
mask_unknown = df["brand"].eq("Unknown")
device_str   = df["device_name"].astype("string")
for kw, vendor in VENDOR_KEYWORDS.items():
    cond = mask_unknown & device_str.str.contains(kw, case=False, na=False)
    df.loc[cond, "brand"] = vendor

# ──────────────────────────────────────────────────────────────
#  Exibição
# ──────────────────────────────────────────────────────────────
st.success(f"🔍 {len(df)} dispositivos analisados")
st.dataframe(df, use_container_width=True)

# download opcional
csv = df.to_csv(index=False).encode()
st.download_button("⬇️ Baixar resultado (.csv)", csv, "resultado_mac.csv", "text/csv")
