# Analisador de MAC Address

Pequena aplicação em **Streamlit** que identifica o fabricante (OUI)
de cada endereço MAC presente num arquivo CSV.

## Como executar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Depois abra <http://localhost:8501> no navegador.
