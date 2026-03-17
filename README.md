# Eleccions ICGSB – Generador de paperetes

Eina per generar paperetes en PDF a partir de l’exportació Excel de vots electrònics de l’ICGSB.

## Requisits

- Python 3.9+
- `pandas`, `openpyxl`, `reportlab`

```bash
pip install -r requirements.txt
```

## Ús

```bash
python3 generar_papeletes.py "/ruta/al/export.xlsx"
```

Si no passes cap fitxer, s’utilitza per defecte `~/Downloads/ExportGraduadosBarcelona.xlsx`.

El PDF es genera a la mateixa carpeta que l’Excel, amb el nom `paperetes_icgsb.pdf`.

## Excel

- L’Excel pot tenir més d’un full. Es fa servir el primer full que tingui les columnes: **id agenda**, **nombre agenda**, **id** (votant), **votos**.
- Si el nom de l’agenda conté `//`, es mostra en diverses línies a la papereta.
- En canviar d’**id agenda** (elecció), es comença una nova pàgina al PDF.

## Opció web (Streamlit)

```bash
streamlit run app.py
```

Permet pujar l’Excel des del navegador i escollir les columnes abans de generar el PDF.
