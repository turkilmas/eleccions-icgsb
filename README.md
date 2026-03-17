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

## Pàgina web (Examinar + Generar PDF)

```bash
pip install flask
python web.py
```

Obre al navegador **http://127.0.0.1:5000**. Hi ha un botó **Examinar** per triar l’Excel i **Generar PDF** per descarregar el fitxer.

## Opció web amb Streamlit

```bash
streamlit run app.py
```

Permet pujar l’Excel des del navegador i escollir les columnes abans de generar el PDF.

## Cloudflare Pages (tot al navegador)

La pàgina **no necessita servidor**: l’Excel es llegeix i el PDF es genera al navegador (SheetJS + jsPDF).

Per desplegar a [Cloudflare Pages](https://pages.cloudflare.com/):

| Camp | Valor |
|------|--------|
| **Comanda de compilació** | *(deixar buit)* |
| **Directori de sortida** | `.` *(punt = arrel del repositori)* |

La pàgina que es desplega és `index.html` a l’arrel del projecte. Un cop desplegat, el botó «Generar PDF» funciona directament (tot s’executa al navegador).
