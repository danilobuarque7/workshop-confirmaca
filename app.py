import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
import json
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave")
database_url = os.environ.get("DATABASE_URL", "sqlite:///workshop.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

LIMITE_PARTICIPANTES = 55

class Inscricao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(30), nullable=False)
    whatsapp = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(30), nullable=False)
    regime = db.Column(db.String(50), nullable=False)
    sozinho = db.Column(db.String(10), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    acompanhantes = db.Column(db.Text, nullable=True)
    data_inscricao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def total_participantes():
    resultado = db.session.query(db.func.coalesce(db.func.sum(Inscricao.quantidade), 0)).scalar()
    return int(resultado or 0)

@app.context_processor
def dados_globais():
    total = total_participantes()
    return {
        "total_participantes": total,
        "vagas_restantes": max(0, LIMITE_PARTICIPANTES - total),
        "limite_participantes": LIMITE_PARTICIPANTES
    }

@app.route("/", methods=["GET", "POST"])
def workshop():
    if request.method == "POST":
        total_atual = total_participantes()

        try:
            quantidade = 1 if request.form.get("sozinho") == "sim" else int(request.form.get("quantidade", "0"))
        except ValueError:
            quantidade = 0
            
        acompanhantes = []

        if request.form.get("sozinho") == "nao":
            for i in range(1, quantidade + 1):
                nome_acompanhante = request.form.get(f"acompanhante_{i}", "").strip()

                if nome_acompanhante:
                   acompanhantes.append(nome_acompanhante)

        if total_atual >= LIMITE_PARTICIPANTES:
            return render_template("encerrado.html")

        if quantidade < 1:
            flash("Informe uma quantidade válida de participantes.", "erro")
            return render_template("workshop.html")

        if total_atual + quantidade > LIMITE_PARTICIPANTES:
            disponiveis = LIMITE_PARTICIPANTES - total_atual
            flash(f"Restam apenas {disponiveis} vaga(s). Reduza a quantidade de participantes.", "erro")
            return render_template("workshop.html")

        dados = {
            "nome": request.form.get("nome", "").strip(),
            "cpf": request.form.get("cpf", "").strip(),
            "whatsapp": request.form.get("whatsapp", "").strip(),
            "email": request.form.get("email", "").strip(),
            "cnpj": request.form.get("cnpj", "").strip(),
            "regime": request.form.get("regime", "").strip(),
            "sozinho": request.form.get("sozinho", "").strip(),
            "quantidade": quantidade,
            "acompanhantes": json.dumps(acompanhantes, ensure_ascii=False)
        }

        if dados["sozinho"] == "nao" and len(acompanhantes) != quantidade:
            flash("Informe o nome completo de todos os acompanhantes.", "erro")
            return render_template("workshop.html")
    
        if not all([dados["nome"], dados["cpf"], dados["whatsapp"], dados["email"],
                    dados["cnpj"], dados["regime"], dados["sozinho"]]):
            flash("Preencha todos os campos obrigatórios.", "erro")
            return render_template("workshop.html")                        

        db.session.add(Inscricao(**dados))
        db.session.commit()

        return redirect(url_for("sucesso", id=Inscricao.query.order_by(Inscricao.id.desc()).first().id))

    if total_participantes() >= LIMITE_PARTICIPANTES:
        return render_template("encerrado.html")

    return render_template("workshop.html")

@app.route("/sucesso")
def sucesso():
    return render_template("sucesso.html")

from functools import wraps
from flask import session

ADMIN_USUARIO = os.environ.get("ADMIN_USUARIO", "admin")
ADMIN_SENHA = os.environ.get("ADMIN_SENHA", "troque-esta-senha")


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("admin_logado"):
            return func(*args, **kwargs)
        return redirect(url_for("admin_login"))
    return wrapper


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")

        if usuario == ADMIN_USUARIO and senha == ADMIN_SENHA:
            session["admin_logado"] = True
            return redirect(url_for("admin"))

        flash("Usuário ou senha incorretos.", "erro")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logado", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin():
    inscricoes = Inscricao.query.order_by(Inscricao.id.desc()).all()
    return render_template("admin.html", inscricoes=inscricoes)


@app.route("/admin/exportar")
def exportar():
    import csv
    from io import StringIO
    from flask import Response
    inscricoes = Inscricao.query.order_by(Inscricao.id.asc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Nome","CPF","WhatsApp","E-mail","CNPJ","Regime","Sozinho","Quantidade","Data"])
    for i in inscricoes:
        writer.writerow([i.id,i.nome,i.cpf,i.whatsapp,i.email,i.cnpj,i.regime,i.sozinho,i.quantidade,i.data_inscricao.strftime("%d/%m/%Y %H:%M")])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition":"attachment; filename=inscricoes_workshop.csv"})

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
