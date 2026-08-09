import os
import json
import csv

from datetime import datetime
from functools import wraps
from io import StringIO

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    Response
)

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "troque-esta-chave"
)

database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///workshop.db"
)

# Compatibilidade com URLs antigas do PostgreSQL
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# CONFIGURAÇÕES DO WORKSHOP
# ============================================================

LIMITE_PARTICIPANTES = 55


# ============================================================
# MODELO DO BANCO
# ============================================================

class Inscricao(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    cpf = db.Column(
        db.String(30),
        nullable=False
    )

    whatsapp = db.Column(
        db.String(30),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        nullable=False
    )

    cnpj = db.Column(
        db.String(30),
        nullable=False
    )

    regime = db.Column(
        db.String(50),
        nullable=False
    )

    sozinho = db.Column(
        db.String(10),
        nullable=False
    )

    # IMPORTANTE:
    # quantidade representa o TOTAL de pessoas da inscrição.
    #
    # Exemplo:
    # sozinho = sim  -> quantidade = 1
    # acompanhado    -> quantidade = 2, 3, 4...
    #
    quantidade = db.Column(
        db.Integer,
        nullable=False
    )

    # Lista de acompanhantes armazenada em JSON.
    #
    # Exemplo:
    # ["João da Silva", "Maria Souza"]
    acompanhantes = db.Column(
        db.Text,
        nullable=True
    )

    data_inscricao = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# ============================================================
# TOTAL DE PARTICIPANTES
# ============================================================

def total_participantes():

    resultado = db.session.query(
        db.func.coalesce(
            db.func.sum(Inscricao.quantidade),
            0
        )
    ).scalar()

    return int(resultado or 0)


# ============================================================
# DADOS GLOBAIS DISPONÍVEIS NOS TEMPLATES
# ============================================================

@app.context_processor
def dados_globais():

    total = total_participantes()

    return {
        "total_participantes": total,
        "vagas_restantes": max(
            0,
            LIMITE_PARTICIPANTES - total
        ),
        "limite_participantes": LIMITE_PARTICIPANTES
    }


# ============================================================
# FORMULÁRIO PRINCIPAL
# ============================================================

@app.route("/", methods=["GET", "POST"])
def workshop():

    if request.method == "POST":

        # ----------------------------------------------------
        # Verifica quantas vagas ainda existem
        # ----------------------------------------------------

        total_atual = total_participantes()

        if total_atual >= LIMITE_PARTICIPANTES:
            return render_template("encerrado.html")


        # ----------------------------------------------------
        # Tipo de participação
        # ----------------------------------------------------

        sozinho = request.form.get(
            "sozinho",
            ""
        ).strip()


        # ----------------------------------------------------
        # Quantidade TOTAL de pessoas
        # ----------------------------------------------------
        #
        # Sozinho:
        #   1 pessoa
        #
        # Acompanhado:
        #   quantidade informada pelo usuário
        #
        # Exemplo:
        #   quantidade = 2
        #   significa:
        #       participante principal + 1 acompanhante
        # ----------------------------------------------------

        try:

            if sozinho == "sim":

                quantidade = 1

            elif sozinho == "nao":

                quantidade = int(
                    request.form.get(
                        "quantidade",
                        "0"
                    )
                )

            else:

                quantidade = 0

        except (ValueError, TypeError):

            quantidade = 0


        # ----------------------------------------------------
        # Validação da quantidade
        # ----------------------------------------------------

        if quantidade < 1:

            flash(
                "Informe uma quantidade válida de participantes.",
                "erro"
            )

            return render_template(
                "workshop.html"
            )


        # ----------------------------------------------------
        # Se for acompanhado, precisa ter pelo menos 2 pessoas
        # ----------------------------------------------------

        if sozinho == "nao" and quantidade < 2:

            flash(
                "Para participar acompanhado, informe pelo menos 2 pessoas no total.",
                "erro"
            )

            return render_template(
                "workshop.html"
            )


        # ----------------------------------------------------
        # Verifica limite de 55 pessoas
        # ----------------------------------------------------

        if total_atual + quantidade > LIMITE_PARTICIPANTES:

            disponiveis = (
                LIMITE_PARTICIPANTES - total_atual
            )

            flash(
                f"Restam apenas {disponiveis} vaga(s). "
                f"Reduza a quantidade de participantes.",
                "erro"
            )

            return render_template(
                "workshop.html"
            )


        # ====================================================
        # ACOMPANHANTES
        # ====================================================

        acompanhantes = []


        if sozinho == "nao":

            # ------------------------------------------------
            # A quantidade informada já inclui o participante
            # principal.
            #
            # Portanto:
            #
            # quantidade 2 = 1 acompanhante
            # quantidade 3 = 2 acompanhantes
            # quantidade 4 = 3 acompanhantes
            # ------------------------------------------------

            quantidade_acompanhantes = quantidade - 1


            for i in range(
                1,
                quantidade_acompanhantes + 1
            ):

                nome_acompanhante = request.form.get(
                    f"acompanhante_{i}",
                    ""
                ).strip()


                # ------------------------------------------------
                # Todos os acompanhantes são obrigatórios
                # ------------------------------------------------

                if not nome_acompanhante:

                    flash(
                        f"Informe o nome completo do acompanhante {i}.",
                        "erro"
                    )

                    return render_template(
                        "workshop.html"
                    )


                acompanhantes.append(
                    nome_acompanhante
                )


        # ====================================================
        # DADOS PRINCIPAIS
        # ====================================================

        dados = {

            "nome": request.form.get(
                "nome",
                ""
            ).strip(),

            "cpf": request.form.get(
                "cpf",
                ""
            ).strip(),

            "whatsapp": request.form.get(
                "whatsapp",
                ""
            ).strip(),

            "email": request.form.get(
                "email",
                ""
            ).strip(),

            "cnpj": request.form.get(
                "cnpj",
                ""
            ).strip(),

            "regime": request.form.get(
                "regime",
                ""
            ).strip(),

            "sozinho": sozinho,

            "quantidade": quantidade,

            "acompanhantes": json.dumps(
                acompanhantes,
                ensure_ascii=False
            )
        }


        # ====================================================
        # VALIDAÇÃO DOS DADOS PRINCIPAIS
        # ====================================================

        if not all([
            dados["nome"],
            dados["cpf"],
            dados["whatsapp"],
            dados["email"],
            dados["cnpj"],
            dados["regime"],
            dados["sozinho"]
        ]):

            flash(
                "Preencha todos os campos obrigatórios.",
                "erro"
            )

            return render_template(
                "workshop.html"
            )


        # ====================================================
        # GRAVA NO BANCO
        # ====================================================

        try:

            nova_inscricao = Inscricao(
                **dados
            )

            db.session.add(
                nova_inscricao
            )

            db.session.commit()


        except Exception as erro:

            db.session.rollback()

            print(
                "ERRO AO GRAVAR INSCRIÇÃO:",
                erro
            )

            flash(
                "Não foi possível realizar a inscrição. "
                "Tente novamente.",
                "erro"
            )

            return render_template(
                "workshop.html"
            )


        # ====================================================
        # REDIRECIONA PARA SUCESSO
        # ====================================================

        return redirect(
            url_for(
                "sucesso",
                id=nova_inscricao.id
            )
        )


    # ========================================================
    # GET
    # ========================================================

    if total_participantes() >= LIMITE_PARTICIPANTES:

        return render_template(
            "encerrado.html"
        )


    return render_template(
        "workshop.html"
    )


# ============================================================
# PÁGINA DE SUCESSO
# ============================================================

@app.route("/sucesso")
def sucesso():

    return render_template(
        "sucesso.html"
    )


# ============================================================
# ADMINISTRAÇÃO
# ============================================================

ADMIN_USUARIO = os.environ.get(
    "ADMIN_USUARIO",
    "admin"
)

ADMIN_SENHA = os.environ.get(
    "ADMIN_SENHA",
    "troque-esta-senha"
)


def admin_required(func):

    @wraps(func)
    def wrapper(
        *args,
        **kwargs
    ):

        if session.get(
            "admin_logado"
        ):

            return func(
                *args,
                **kwargs
            )

        return redirect(
            url_for(
                "admin_login"
            )
        )

    return wrapper


# ============================================================
# LOGIN ADMIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        )

        senha = request.form.get(
            "senha",
            ""
        )


        if (
            usuario == ADMIN_USUARIO
            and
            senha == ADMIN_SENHA
        ):

            session[
                "admin_logado"
            ] = True

            return redirect(
                url_for(
                    "admin"
                )
            )


        flash(
            "Usuário ou senha incorretos.",
            "erro"
        )


    return render_template(
        "admin_login.html"
    )


# ============================================================
# LOGOUT ADMIN
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logado",
        None
    )

    return redirect(
        url_for(
            "admin_login"
        )
    )


# ============================================================
# PAINEL ADMIN
# ============================================================

@app.route("/admin")
@admin_required
def admin():

    inscricoes = Inscricao.query.order_by(
        Inscricao.id.desc()
    ).all()

    return render_template(
        "admin.html",
        inscricoes=inscricoes
    )


# ============================================================
# EXPORTAÇÃO CSV
# ============================================================

@app.route("/admin/exportar")
@admin_required
def exportar():

    inscricoes = Inscricao.query.order_by(
        Inscricao.id.asc()
    ).all()


    output = StringIO()

    writer = csv.writer(
        output
    )


    # --------------------------------------------------------
    # Cabeçalho
    # --------------------------------------------------------

    writer.writerow([
        "ID",
        "Nome",
        "CPF",
        "WhatsApp",
        "E-mail",
        "CNPJ",
        "Regime",
        "Sozinho",
        "Quantidade Total",
        "Acompanhantes",
        "Data"
    ])


    # --------------------------------------------------------
    # Dados
    # --------------------------------------------------------

    for inscricao in inscricoes:

        acompanhantes_texto = ""

        if inscricao.acompanhantes:

            try:

                lista = json.loads(
                    inscricao.acompanhantes
                )

                acompanhantes_texto = (
                    " | ".join(lista)
                )

            except Exception:

                acompanhantes_texto = (
                    inscricao.acompanhantes
                )


        writer.writerow([

            inscricao.id,

            inscricao.nome,

            inscricao.cpf,

            inscricao.whatsapp,

            inscricao.email,

            inscricao.cnpj,

            inscricao.regime,

            inscricao.sozinho,

            inscricao.quantidade,

            acompanhantes_texto,

            inscricao.data_inscricao.strftime(
                "%d/%m/%Y %H:%M"
            )
        ])


    return Response(

        "\ufeff" + output.getvalue(),

        mimetype="text/csv; charset=utf-8",

        headers={
            "Content-Disposition":
                "attachment; filename=inscricoes_workshop.csv"
        }
    )


# ============================================================
# BANCO DE DADOS / MIGRAÇÃO
# ============================================================

with app.app_context():

    # Cria as tabelas que ainda não existem
    db.create_all()


    # --------------------------------------------------------
    # Verifica se a coluna acompanhantes existe.
    #
    # Isso é importante porque você já tinha um banco criado.
    # Não queremos apagar os cadastros existentes.
    # --------------------------------------------------------

    try:

        inspector = inspect(
            db.engine
        )

        colunas = [
            coluna["name"]
            for coluna in inspector.get_columns(
                "inscricao"
            )
        ]


        if "acompanhantes" not in colunas:

            with db.engine.begin() as conn:

                conn.execute(
                    text(
                        "ALTER TABLE inscricao "
                        "ADD COLUMN acompanhantes TEXT"
                    )
                )

    except Exception as erro:

        print(
            "Aviso durante verificação do banco:",
            erro
        )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
