import io
from pathlib import Path
import requests
import pandas as pd
import streamlit as st

# -----------------------------------------------------------
# Configuração da página
st.set_page_config(page_title="Enriquecedor de MACs", page_icon="🔍", layout="wide")

# -----------------------------------------------------------
# Utilidades
OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"
CACHE_PATH = Path(__file__).parent / "assets" / "oui.csv"

@st.cache_data(show_spinner=False, ttl=24*3600)
def load_oui_dataframe() -> pd.DataFrame:
    """Baixa a tabela oficial de OUIs da IEEE ou usa cache/local."""
    if CACHE_PATH.exists():
        try:
            return pd.read_csv(CACHE_PATH)
        except Exception as e:
            st.warning(f"Falha ao ler cache local: {e}")

    try:
        st.info("Baixando base oficial de fabricantes da IEEE… pode demorar uns segundos.")
        resp = requests.get(OUI_URL, timeout=30)
        resp.raise_for_status()
        CACHE_PATH.write_bytes(resp.content)
        df = pd.read_csv(io.BytesIO(resp.content))
        return df
    except Exception as err:
        st.error(f"Não foi possível baixar a lista oficial ({err}). "
                 "Usando base reduzida embutida – fabricantes pouco comuns podem ficar como 'Unknown'.")
        # Fallback mínimo
        fallback = Path(__file__).parent / "assets" / "oui_fallback.csv"
        if fallback.exists():
            return pd.read_csv(fallback)
        else:
            return pd.DataFrame(columns=["Assignment", "Organization Name", "Organization Address"])

def enrich(df: pd.DataFrame, mac_col: str) -> pd.DataFrame:
    """Adiciona colunas de fabricante (brand) a partir da coluna de MAC informada."""
    oui_df = load_oui_dataframe()
    # normaliza MAC -> OUI (primeiros 6 hex sem separador)
    def mac_to_oui(mac: str) -> str:
        return mac.upper().replace("-","").replace(":","").replace(".","")[:6]

    df = df.copy()
    df["OUI"] = df[mac_col].astype(str).map(mac_to_oui)
    oui_map = dict(zip(oui_df["Assignment"].str.replace("-",""), oui_df["Organization Name"]))
    df["brand"] = df["OUI"].map(oui_map).fillna("Unknown")
    return df

# -----------------------------------------------------------
# Interface
st.title("🔍 Enriquecedor de MAC Addresses")

uploaded = st.file_uploader("📤 Envie um arquivo CSV ou Excel com os MACs", type=["csv","xls","xlsx"])
if uploaded:
    # ler arquivo
    if uploaded.name.lower().endswith("csv"):
        data = pd.read_csv(uploaded)
    else:
        data = pd.read_excel(uploaded)

    st.write("### Pré‑visualização", data.head())

    mac_col = st.selectbox("Selecione a coluna que contém os MACs", data.columns.tolist())
    if st.button("Enriquecer!"):
        result = enrich(data, mac_col)
        st.success("Dados enriquecidos ✅")
        st.dataframe(result.head(1000))
        csv_bytes = result.to_csv(index=False).encode()
        st.download_button("⬇️ Baixar resultado (CSV)", csv_bytes,
                           file_name=f"resultado_mac_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                           mime="text/csv")