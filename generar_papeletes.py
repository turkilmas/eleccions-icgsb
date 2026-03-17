import io
import sys
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _normalitzar(s: str) -> str:
    """Majúscules, sense espais ni accents, per comparar noms de columna."""
    s = str(s).upper().replace(" ", "").replace("_", "")
    for old, new in [("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("À", "A"), ("È", "E"), ("Ì", "I"), ("Ò", "O"), ("Ù", "U")]:
        s = s.replace(old, new)
    return s


def _detectar_columnes(df: pd.DataFrame) -> tuple[str, str, str, str]:
    """
    Intenta detectar les columnes id_agenda, nombre_agenda, id_votant, vots
    de manera tolerant a majúscules, espais, guions baixos i accents.
    """
    normalitzada = {_normalitzar(c): c for c in df.columns}

    def troba(*candidats: str) -> str:
        for cand in candidats:
            k = _normalitzar(cand)
            if k in normalitzada:
                return normalitzada[k]
        raise KeyError(f"No s'ha trobat cap de les columnes: {candidats}")

    # Id agenda: moltes variants
    col_id_agenda = troba(
        "Id agenda", "ID agenda", "id_agenda", "IdAgenda", "Agenda ID",
        "Id agenda", "IDAGENDA", "ID_AGENDA", "AGENDAID", "Codigo", "Código", "Codi"
    )
    # Nombre agenda: moltes variants
    col_nom_agenda = troba(
        "Nombre agenda", "Nombre de agenda", "nombre_agenda", "NombreAgenda",
        "NOMBREAGENDA", "NOMAGENDA", "NOMBRE_AGENDA", "Descripcion", "Descripción",
        "Titulo", "Título", "Nombre"
    )
    col_id_votant = troba("ID", "Id", "id", "IDVOTANT", "Votant")
    col_vots = troba("VOTO", "VOTOS", "Voto", "Votos")
    return col_id_agenda, col_nom_agenda, col_id_votant, col_vots


def _detectar_columnes_per_posicio(df: pd.DataFrame) -> Optional[tuple[str, str, str, str]]:
    """
    Si hi ha 4 columnes, intenta identificar-les: les que contenen UUID (ID votant)
    i text tipus "CANDIDATO" (vots); les altres dues serien id_agenda i nombre_agenda.
    Retorna (col_id_agenda, col_nom_agenda, col_id_votant, col_vots) o None.
    """
    if len(df.columns) != 4:
        return None
    cols = list(df.columns)
    # Trobar columna que sembla ID votant (valors amb guions, UUID)
    id_candidates = []
    voto_candidates = []
    for c in cols:
        sample = df[c].dropna().astype(str).head(3)
        if sample.empty:
            continue
        s = " ".join(sample)
        if "-" in s and len(s) > 30:  # sembla UUID
            id_candidates.append(c)
        if "CANDIDATO" in s.upper() or "VOTO" in s.upper() or "VOT" in s.upper():
            voto_candidates.append(c)
    if not id_candidates or not voto_candidates:
        return None
    col_id_votant = id_candidates[0]
    col_vots = voto_candidates[0]
    restants = [c for c in cols if c not in (col_id_votant, col_vots)]
    if len(restants) != 2:
        return None
    # El que tingui valors més curts / numèrics -> id_agenda; l'altre -> nombre_agenda
    a, b = restants[0], restants[1]
    len_a = df[a].astype(str).str.len().median()
    len_b = df[b].astype(str).str.len().median()
    if len_a <= len_b:
        col_id_agenda, col_nom_agenda = a, b
    else:
        col_id_agenda, col_nom_agenda = b, a
    return col_id_agenda, col_nom_agenda, col_id_votant, col_vots


def calcular_orden_votants_per_agenda(
    df: pd.DataFrame, col_id_agenda: str, col_id_votant: str
) -> pd.DataFrame:
    """
    Assigna a cada (agenda, ID) un ordinal 1..N dins de la seva agenda,
    en l'ordre d'aparició al fitxer.
    """
    vistos: dict[tuple, dict] = {}
    ordre: list[int | None] = []

    for _, fila in df[[col_id_agenda, col_id_votant]].iterrows():
        agenda = fila[col_id_agenda]
        votant = fila[col_id_votant]

        if pd.isna(agenda) or pd.isna(votant):
            ordre.append(None)
            continue

        if agenda not in vistos:
            vistos[agenda] = {}

        if votant not in vistos[agenda]:
            vistos[agenda][votant] = len(vistos[agenda]) + 1

        ordre.append(vistos[agenda][votant])

    df = df.copy()
    df["ordinal_votant"] = ordre
    totals = {agenda: len(vots) for agenda, vots in vistos.items()}
    df["total_votants"] = df[col_id_agenda].map(totals)
    return df


def agrupar_per_papeletes(
    df: pd.DataFrame,
    col_id_agenda: str,
    col_nom_agenda: str,
    col_id_votant: str,
    col_vots: str,
):
    """
    Retorna una llista de tuples:
      (id_agenda, nom_agenda, id_votant, ordinal_votant, total_votants, linies_excel, llista_vots)
    agrupada per (agenda, votant), ordenada per agenda i ordinal.
    """
    resultats = []
    linia_offset = 2  # suposem 1 línia de capçalera

    grouped = df.groupby([col_id_agenda, col_id_votant], dropna=True)
    for (id_agenda, id_votant), grup in grouped:
        if pd.isna(id_votant) or pd.isna(id_agenda):
            continue

        # Llegir el valor de la cel·la des del DataFrame per fila/columna (no el nom de la columna)
        primera_fila_ix = grup.index[0]
        valor_cel_id_agenda = df.loc[primera_fila_ix, col_id_agenda]
        valor_cel_nom_agenda = df.loc[primera_fila_ix, col_nom_agenda]
        if pd.isna(valor_cel_id_agenda):
            valor_cel_id_agenda = ""
        else:
            valor_cel_id_agenda = str(valor_cel_id_agenda)
        if pd.isna(valor_cel_nom_agenda):
            valor_cel_nom_agenda = ""
        else:
            valor_cel_nom_agenda = str(valor_cel_nom_agenda)

        ordinal = int(grup["ordinal_votant"].iloc[0])
        total = int(grup["total_votants"].iloc[0])
        linies_excel = [int(i) + linia_offset for i in grup.index.tolist()]

        vots_unics = sorted(set(grup[col_vots].dropna().astype(str)))

        resultats.append(
            (
                valor_cel_id_agenda,
                valor_cel_nom_agenda,
                str(id_votant),
                ordinal,
                total,
                linies_excel,
                vots_unics,
            )
        )

    resultats.sort(key=lambda x: (x[0], x[3]))  # per agenda i ordinal
    return resultats


def crear_pdf_papeletes(
    df: pd.DataFrame,
    sortida: Union[Path, io.BytesIO],
    col_id_agenda: str,
    col_nom_agenda: str,
    col_id_votant: str,
    col_vots: str,
) -> Optional[bytes]:
    dest = sortida if isinstance(sortida, io.BytesIO) else str(sortida)
    c = canvas.Canvas(dest, pagesize=A4)
    ample, alt = A4

    marge_x = 15 * mm
    marge_y = 15 * mm

    # 6 paperetes per pàgina: 2 columnes x 3 files
    cols = 2
    files = 3
    usable_w = ample - 2 * marge_x
    usable_h = alt - 2 * marge_y
    card_w = usable_w / cols
    card_h = usable_h / files

    papeletes = agrupar_per_papeletes(
        df, col_id_agenda, col_nom_agenda, col_id_votant, col_vots
    )

    pos_en_pagina = 0
    id_agenda_anterior = None

    for (
        id_agenda,
        nom_agenda,
        id_votant,
        ordinal,
        total,
        linies,
        vots_unics,
    ) in papeletes:
        # Canvi d’elecció (id agenda) → nova pàgina
        if id_agenda_anterior is not None and id_agenda != id_agenda_anterior:
            c.showPage()
            pos_en_pagina = 0
        id_agenda_anterior = id_agenda

        # 6 paperetes per pàgina → canvi de pàgina
        if pos_en_pagina >= cols * files:
            c.showPage()
            pos_en_pagina = 0

        pos = pos_en_pagina % (cols * files)
        fila = files - 1 - (pos // cols)  # de dalt cap a baix
        col = pos % cols

        x0 = marge_x + col * card_w
        y0 = marge_y + fila * card_h

        inner_margin = 3 * mm
        bx = x0 + inner_margin
        by = y0 + inner_margin
        bw = card_w - 2 * inner_margin
        bh = card_h - 2 * inner_margin

        # Fons color paper reciclat
        c.setFillColorRGB(0.96, 0.94, 0.88)
        c.rect(bx, by, bw, bh, fill=1, stroke=0)

        # Marc negre
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1)
        c.rect(bx, by, bw, bh, fill=0, stroke=1)

        # Títol
        c.setFillColorRGB(0, 0, 0)
        top_y = by + bh - 6 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(bx + 4 * mm, top_y, "ELECCIONS ICGSB")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bx + 4 * mm, top_y - 11, "VOT ELECTRÒNIC")

        # Dades d'agenda i votant: nom_agenda i id_agenda són VALORS de cel·les (no noms de columna)
        y = top_y - 25
        c.setFont("Helvetica", 8)
        # Si el nom de l'agenda conté "//", fem un salt de línia a cada fragment
        parts_nom = str(nom_agenda).split("//")
        for i, part in enumerate(parts_nom):
            text = part.strip()
            if not text:
                continue
            c.drawString(bx + 4 * mm, y, text)
            if i < len(parts_nom) - 1:
                y -= 11
        y -= 11
        c.drawString(bx + 4 * mm, y, f"Identificador votant: {id_votant}")
        y -= 15

        # Secció de vot
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bx + 4 * mm, y, "Vot emès:")
        y -= 11

        c.setFont("Helvetica", 8)
        if not vots_unics:
            c.drawString(bx + 8 * mm, y, "— Sense vot registrat —")
            y -= 10
        else:
            for vot in vots_unics:
                if y < by + 10 * mm:
                    break  # evitem escriure fora de la targeta
                c.drawString(bx + 8 * mm, y, f"- {vot}")
                y -= 9

        # Peu de papereta (dues línies: id agenda + papeleta, després línies Excel)
        c.setFont("Helvetica-Oblique", 7)
        linia1 = f"ID AGENDA: {id_agenda} - Papeleta: {ordinal}/{total}"
        linia2 = f"Línies Excel: {','.join(map(str, linies))}"
        # Línia 1 una mica per sobre, línia 2 una mica més avall perquè no quedin enganxades
        c.drawString(bx + 4 * mm, by + 5.5 * mm, linia1)
        c.drawString(bx + 4 * mm, by + 2 * mm, linia2)

        pos_en_pagina += 1

    c.save()
    if isinstance(sortida, io.BytesIO):
        sortida.seek(0)
        return sortida.getvalue()
    return None


def generar_pdf_des_de_excel(excel_source: Union[Path, io.BytesIO]) -> bytes:
    """
    Llegeix l'Excel des d'un fitxer o un stream i retorna el PDF de paperetes en bytes.
    Útil per a la pàgina web (upload).
    """
    if isinstance(excel_source, (Path, str)):
        xl = pd.ExcelFile(Path(excel_source))
    else:
        xl = pd.ExcelFile(excel_source)

    df = None
    for nom_full in xl.sheet_names:
        candidat = pd.read_excel(xl, sheet_name=nom_full, header=0)
        candidat.columns = candidat.columns.str.strip()
        try:
            _detectar_columnes(candidat)
            df = candidat
            break
        except KeyError:
            continue
    if df is None:
        df = pd.read_excel(xl, sheet_name=0, header=0)
        df.columns = df.columns.str.strip()

    try:
        col_id_agenda, col_nom_agenda, col_id_votant, col_vots = _detectar_columnes(df)
    except KeyError:
        detectat = _detectar_columnes_per_posicio(df)
        if detectat:
            col_id_agenda, col_nom_agenda, col_id_votant, col_vots = detectat
        else:
            col_id_votant = "ID"
            col_vots = "VOTO"
            col_id_agenda = "_AGENDA_ID"
            col_nom_agenda = "_AGENDA_NOM"
            df[col_id_agenda] = "—"
            df[col_nom_agenda] = "—"

    df_proc = calcular_orden_votants_per_agenda(df, col_id_agenda, col_id_votant)
    buffer = io.BytesIO()
    crear_pdf_papeletes(
        df_proc,
        buffer,
        col_id_agenda=col_id_agenda,
        col_nom_agenda=col_nom_agenda,
        col_id_votant=col_id_votant,
        col_vots=col_vots,
    )
    return buffer.getvalue()


def main() -> None:
    # Fitxer font: el que passis com a argument, o per defecte ExportGraduadosBarcelona.xlsx a Downloads
    if len(sys.argv) >= 2:
        excel_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        excel_path = Path.home() / "Downloads" / "ExportGraduadosBarcelona.xlsx"
    if not excel_path.exists():
        raise FileNotFoundError(f"No s'ha trobat l'arxiu: {excel_path}")

    print(f"Fitxer font: {excel_path}")

    # L’Excel pot tenir més d’un full: Hoja1 (només ID, VOTO) i Hoja2 (id, votos, nombre agenda, id agenda).
    # Llegim el full que tingui les columnes d’agenda per poder mostrar els valors reals.
    xl = pd.ExcelFile(excel_path)
    df = None
    sheet_usat = None
    for nom_full in xl.sheet_names:
        candidat = pd.read_excel(xl, sheet_name=nom_full, header=0)
        candidat.columns = candidat.columns.str.strip()
        try:
            _detectar_columnes(candidat)
            df = candidat
            sheet_usat = nom_full
            break
        except KeyError:
            continue
    if df is None:
        # Cap full té les 4 columnes; llegim el primer full
        df = pd.read_excel(excel_path, header=0)
        df.columns = df.columns.str.strip()
        sheet_usat = xl.sheet_names[0]
        print(f"Full utilitzat: {sheet_usat} (sense columnes d’agenda)")

    if sheet_usat:
        print(f"Full utilitzat: {sheet_usat}")

    try:
        col_id_agenda, col_nom_agenda, col_id_votant, col_vots = _detectar_columnes(df)
        print(f"Columnes: id_agenda={col_id_agenda!r}, nombre_agenda={col_nom_agenda!r}, id_votant={col_id_votant!r}, vots={col_vots!r}")
    except KeyError:
        detectat = _detectar_columnes_per_posicio(df)
        if detectat:
            col_id_agenda, col_nom_agenda, col_id_votant, col_vots = detectat
            print(f"Columnes (per posició): id_agenda={col_id_agenda!r}, nombre_agenda={col_nom_agenda!r}, id_votant={col_id_votant!r}, vots={col_vots!r}")
        else:
            col_id_votant = "ID"
            col_vots = "VOTO"
            col_id_agenda = "_AGENDA_ID"
            col_nom_agenda = "_AGENDA_NOM"
            df[col_id_agenda] = "—"
            df[col_nom_agenda] = "—"
            print("Avís: no s'han trobat columnes d'agenda; es mostraran '—'.")

    df_proc = calcular_orden_votants_per_agenda(df, col_id_agenda, col_id_votant)

    sortida = excel_path.parent / "paperetes_icgsb.pdf"
    crear_pdf_papeletes(
        df_proc,
        sortida,
        col_id_agenda=col_id_agenda,
        col_nom_agenda=col_nom_agenda,
        col_id_votant=col_id_votant,
        col_vots=col_vots,
    )
    print(f"PDF generat a: {sortida}")


if __name__ == "__main__":
    main()

