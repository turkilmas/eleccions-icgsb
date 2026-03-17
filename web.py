"""
Pàgina web per generar paperetes: botó Examinar + Generar PDF.
Executar: python web.py
Obrir al navegador: http://127.0.0.1:5000
"""
import io

from flask import Flask, request, send_file, render_template

from generar_papeletes import generar_pdf_des_de_excel

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generar", methods=["POST"])
def generar():
    if "excel" not in request.files:
        return "Cal seleccionar un fitxer Excel.", 400
    fitxer = request.files["excel"]
    if not fitxer or fitxer.filename == "":
        return "Cap fitxer seleccionat.", 400
    if not fitxer.filename.lower().endswith((".xlsx", ".xls")):
        return "El fitxer ha de ser Excel (.xlsx).", 400
    try:
        pdf_bytes = generar_pdf_des_de_excel(io.BytesIO(fitxer.read()))
    except Exception as e:
        return str(e), 500
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="paperetes_icgsb.pdf",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
