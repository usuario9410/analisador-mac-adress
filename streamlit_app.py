import streamlit as st
import pandas as pd
from pymanuf import MacParser
import matplotlib.pyplot as plt

st.set_page_config(page_title="Analisador de MAC Address", layout="centered")
st.title("🔎 Analisador de Endereços MAC")

st.markdown(
    """
    Faça upload de um arquivo **CSV** contendo uma coluna chamada
    `mac` com os endereços MAC a serem analisados.
    A aplicação irá identificar o fabricante (OUI) de cada endereço
    automaticamente e exibir algumas estatísticas básicas.
    """
)

uploaded_file = st.file_uploader("📤 Enviar CSV…", type=["csv"])

if uploaded_file is None:
    st.info("⬆️ Envie um CSV para começar")
    st.stop()

# -------------------------------------------------------------------------
#  Leitura dos dados
# -------------------------------------------------------------------------
df = pd.read_csv(uploaded_file)

if "mac" not in df.columns:
    st.error("O CSV precisa conter uma coluna chamada 'mac'.")
    st.stop()

# -------------------------------------------------------------------------
#  Descoberta de fabricante via pymanuf
# -------------------------------------------------------------------------
parser = MacParser()
df["vendor"] = df["mac"].astype(str).apply(
    lambda m: parser.get_manuf(m) or "Unknown"
)

# -------------------------------------------------------------------------
#  Estatísticas
# -------------------------------------------------------------------------
st.subheader("📊 Tabela de resultados")
st.dataframe(df, hide_index=True)

vendor_counts = df["vendor"].value_counts().rename_axis("Fabricante")
st.subheader("🏭 Dispositivos por fabricante")
st.bar_chart(vendor_counts)

# -------------------------------------------------------------------------
#  Download do resultado anotado
# -------------------------------------------------------------------------
csv_bytes = df.to_csv(index=False).encode()
st.download_button(
    "⬇️ Baixar CSV com fabricantes",
    csv_bytes,
    file_name="mac_addresses_vendor.csv",
    mime="text/csv",
)
