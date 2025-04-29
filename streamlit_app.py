
"""
Streamlit MAC Address Analyzer
------------------------------

Uploads a CSV or TXT containing MAC addresses and enriches each row
with vendor / OUI information fetched from the official IEEE registry.

Heavy‑weight OUI data (approx. 30 MB) is cached locally in *assets/oui.csv*
after the first run so subsequent launches are fast even on cold restarts.
"""

from __future__ import annotations
from pathlib import Path
import io, re, requests, pandas as pd, streamlit as st

OUI_CSV_URL = "https://standards-oui.ieee.org/oui/oui.csv"
CACHE_PATH = Path(__file__).with_name("assets") / "oui.csv"

@st.cache_data(show_spinner="🔄  baixando a tabela oficial de OUIs…")
def load_oui_dataframe() -> pd.DataFrame:
    """Return a DataFrame with columns ['Assignment', 'Organization Name']."""
    if CACHE_PATH.exists():
        return pd.read_csv(CACHE_PATH, dtype=str)

    r = requests.get(OUI_CSV_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), dtype=str)
    # Keep only clean columns and normalise assignment (first 6 hex chars)
    df = df.rename(columns={"Assignment": "OUI", "Organization Name": "vendor"})[["OUI", "vendor"]]
    df["OUI"] = df["OUI"].str.upper().str.replace("-", "", regex=False)
    CACHE_PATH.parent.mkdir(exist_ok=True)
    df.to_csv(CACHE_PATH, index=False)
    return df

def normalise_mac(mac: str) -> str | None:
    """Return MAC as 12 upper‑case hex chars or None if invalid."""
    m = re.sub(r"[^0-9A-Fa-f]", "", mac)
    return m.upper() if len(m) == 12 else None

def enrich(df: pd.DataFrame, mac_col: str) -> pd.DataFrame:
    """Add vendor column by joining first 6 hex chars against OUI DB."""
    oui_df = load_oui_dataframe()
    df = df.copy()
    df["mac_norm"] = df[mac_col].astype(str).map(normalise_mac)
    df["OUI"] = df["mac_norm"].str.slice(0,6)
    df = df.merge(oui_df, on="OUI", how="left")
    df = df.rename(columns={"vendor": "Vendor"})
    return df.drop(columns=["mac_norm"])

st.title("🔍 MAC Address Analyzer")

uploaded = st.file_uploader("📄  Faça upload do arquivo com MACs (CSV, TXT)", type=["csv","txt"])
if uploaded:
    try:
        raw = uploaded.read().decode("utf‑8", errors="ignore")
        data = pd.read_csv(io.StringIO(raw)) if uploaded.name.endswith(".csv") else pd.DataFrame({"MAC": raw.strip().splitlines()})
    except Exception as e:
        st.error(f"Falha ao ler arquivo: {e}")
        st.stop()

    mac_col = st.selectbox("Selecione a coluna que contém os MACs", data.columns.tolist(), index=0)
    result = enrich(data, mac_col)

    st.success(f"{len(result)} linhas processadas.")
    st.dataframe(result, use_container_width=True)

    csv = result.to_csv(index=False).encode("utf‑8")
    st.download_button("⬇️  Baixar resultado CSV", csv, file_name="mac_enriched.csv", mime="text/csv")
else:
    st.info("Nenhum arquivo enviado ainda.")
