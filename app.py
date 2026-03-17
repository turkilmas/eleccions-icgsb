import io
from typing import List, Tuple

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import streamlit as st


def calcular_orden_votants(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    """
    Afegeix al dataframe:
      - 'ordinal_votant': posició (1..N) de cada ID segons ordre d'aparició
      - 'total_votants': total d'identificadors diferents
    """
    vistos = {}
    ordre = []
    for idx, valor in df[id_col].items():
        if pd.isna(valor):
            ordre.append(None)
            continue
        if valor not in vistos:
            vistos[valor] = len(vistos) + 1
        ordre.append(vistos[valor])

    df = df.copy()
    df["ordinal_votant"] = ordre
    df["total_votants"] = len(vistos)
    return df


def agrupar_per_papeletes(
    df: pd.DataFrame,
    col_id_agenda: str,
    col_nom_agenda: str,
    col_id_votant: str,
) -> List[Tuple[str, str, str, int, int, List[int]]]:
    """
    Retorna una llista de tuples amb:
      (id_agenda, nom_agenda, id_votant, ordinal_votant, total_votants, linies_excel)
    agrupades per (id_agenda, id_votant).
    """
    resultats = []

    # La primera fila de dades és la línia 2 d'Excel (suposant 1 línia de capçalera)
    linia_offset = 2

    grouped = df.groupby([col_id_agenda, col_id_votant], dropna=True)
    for (id_agenda, id_votant), grup in grouped:
        if pd.isna(id_votant):
            continue

        nom_agenda = str(grup[col_nom_agenda].iloc[0])

        # ordinal i total són els mateixos per tot el grup
        ordinal = int(grup["ordinal_votant"].iloc[0])
        total = int(grup["total_votants"].iloc[0])

        # línies d'Excel (1-based), assumint una sola fila de capçalera
        linies_excel = [int(i) + linia_offset for i in grup.index.tolist()]

        resultats.append(
            (str(id_agenda), nom_agenda, str(id_votant), ordinal, total, linies_excel)
        )

    # Ordenem per id_agenda i després per ordinal de votant (simulació ordre de vot)
    resultats.sort(key=lambda x: (x[0], x[3]))
    return resultats


def crear_pdf_papeletes(
    df: pd.DataFrame,
    col_id_agenda: str,
    col_nom_agenda: str,
    col_id_votant: str,
    col_vots: str,
) -> bytes:
    """
    Genera un PDF amb una pàgina per cada papereta.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ample, alt = A4

    marge_x = 20 * mm
    marge_y = 20 * mm

    papeletes = agrupar_per_papeletes(df, col_id_agenda, col_nom_agenda, col_id_votant)

    for id_agenda, nom_agenda, id_votant, ordinal, total, linies in papeletes:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(marge_x, alt - marge_y, "ICGSB - Eleccions")

        c.setFont("Helvetica", 12)
        c.drawString(marge_x, alt - marge_y - 25, f"Agenda: {id_agenda} - {nom_agenda}")
        c.drawString(marge_x, alt - marge_y - 45, f"Identificador votant: {id_votant}")

        # Determinem a qui ha votat aquest votant en aquesta agenda
        mask = (df[col_id_agenda] == id_agenda) & (df[col_id_votant] == id_votant)
        vots_unics = sorted(set(df.loc[mask, col_vots].dropna().astype(str)))

        y = alt - marge_y - 80
        c.setFont("Helvetica-Bold", 13)
        c.drawString(marge_x, y, "Vot emès:")
        y -= 20

        c.setFont("Helvetica", 12)
        if not vots_unics:
            c.drawString(marge_x, y, "— Sense vot registrat —")
            y -= 20
        else:
            for vot in vots_unics:
                c.drawString(marge_x + 15, y, f"- {vot}")
                y -= 18

        # Peu de pàgina amb informació de traçabilitat
        c.setFont("Helvetica-Oblique", 10)
        text_peu = f"Papeleta: {ordinal}/{total}   Línies Excel: {','.join(map(str, linies))}"
        c.drawString(marge_x, marge_y, text_peu)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


def main() -> None:
    st.set_page_config(page_title="Generador de paperetes ICGSB", page_icon="🗳️")
    st.title("Generador de paperetes a partir d'Excel de vots (ICGSB)")

    st.markdown(
        """
Aquesta eina llegeix l'Excel d'exportació de vots i genera un PDF amb
una papereta per a cada combinació **(elecció, votant)**, simulant unes eleccions presencials.

Columna esperades (poden variar en el nom, les podràs escollir):
- **id agenda** i **nombre agenda**: identifiquen l'elecció
- **ID**: identificador únic del votant
- **votos**: a qui ha votat el votant
"""
    )

    fitxer = st.file_uploader("Arrossega aquí l'Excel de vots (`.xlsx`)", type=["xlsx"])
    if not fitxer:
        st.info("Carrega primer el fitxer d'Excel per continuar.")
        return

    try:
        df = pd.read_excel(fitxer)
    except Exception as e:
        st.error(f"No s'ha pogut llegir l'Excel: {e}")
        return

    st.subheader("Mapeig de columnes")
    cols = list(df.columns)
    col_id_agenda = st.selectbox("Columna 'id agenda' (codi elecció)", cols, index=0)
    col_nom_agenda = st.selectbox("Columna 'nombre agenda' (nom elecció)", cols, index=1)
    col_id_votant = st.selectbox("Columna 'ID' (identificador votant)", cols, index=2)
    col_vots = st.selectbox("Columna 'votos' (a qui ha votat)", cols, index=3)

    if st.button("Generar PDF de paperetes"):
        with st.spinner("Processant i generant el PDF de paperetes..."):
            df_proc = calcular_orden_votants(df, col_id_votant)
            pdf_bytes = crear_pdf_papeletes(
                df_proc,
                col_id_agenda=col_id_agenda,
                col_nom_agenda=col_nom_agenda,
                col_id_votant=col_id_votant,
                col_vots=col_vots,
            )

        st.success("PDF generat correctament.")
        st.download_button(
            label="Descarregar PDF de paperetes",
            data=pdf_bytes,
            file_name="paperetes_icgsb.pdf",
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()

