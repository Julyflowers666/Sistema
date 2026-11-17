import os
from flask import Flask, render_template
from flask import (request, render_template, redirect, flash, url_for, session)
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from functools import wraps


    
load_dotenv()
app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
if not app.secret_key:
    raise RuntimeError("Configure a CHAVE SECRETA no arquivo .env")

def login_obrigatorio(funcao):
    @wraps(funcao)
    def verificar (*args, **kwargs):
        if "id_usuario" not in session:
            flash("faça login para continuar","warning")
            return redirect(url_for("login"))

        return funcao(*args,**kwargs)

    return verificar

def conectar_banco():
#ABRE A CONEXÃO COM MYSQL USANDO O ARQUIVO .ENV
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route("/")
def inicio():
    return "<h1>Bem-Vindo ao Senac Reserva</h1>"

@app.route("/salas")
@login_obrigatorio
def listar_salas():
    conexao = None
    curso = None
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
                SELECT id_sala, tipo_sala, capacidade, nome_sala,
                descricao, disponibilidade
                FROM sala
                ORDER BY id_sala
                """)
        salas = cursor.fetchall()
        return render_template("salas.html", salas=salas)
    except Error:
        app.logger.exception("falha ao consultar salas")
        return render_template("error.html", mensagem="nao foi possivel consultar as salas"), 500
    finally:
        if curso: cursor.close()
        if conexao and conexao.is_connected(): conexao.close()


@app.route("/reservas", methods=["GET", "POST"])
@login_obrigatorio
def reservar():

    id_usuario = session["id_usuario"]

    if request.method == "GET":
        conexao = None
        cursor = None
        try:
            conexao = conectar_banco()
            cursor = conexao.cursor (dictionary=True)
            cursor.execute('SELECT id_sala, nome_sala FROM sala WHERE disponibilidade = 1 ORDER BY id_sala')
            salas = cursor.fetchall()
            return render_template("reservas.html", salas=salas)
        except Error:
            app.logger.exception("falha ao carregar salas")
            return render_template("erro.html", mensagem="nao foi possivel carregar o formulario")
        finally:
            if cursor: cursor.close()
            if conexao and conexao.is_connected(): conexao.close()

    #le e valida os dados enviados
    try:
        id_sala = int(request.form["id_sala"])
        data_reserva = date.fromisoformat(
            request.form["data_reserva"]
        )
        horario_inicio = datetime.strptime(
            request.form["horario_inicio"], "%H:%M"
        ).time()
        horario_fim = datetime.strptime(
            request.form["horario_fim"], "%H:%M"
        ).time()
        finalidade = request.form["finalidade"].strip()

    except (KeyError, ValueError):
        flash("Dados Inválidos.", "danger")
        return redirect("/reservas")

    if horario_inicio >= horario_fim:
        flash("Horário final deve ser maior q o inicial", "danger")
        return redirect ("/reservas")

    if data_reserva < date.today():
        flash("A data não pode estar no passado.", "danger")
        return redirect("/reservas")

    if not finalidade or len(finalidade) > 200:
        flash("a finalidade deve ter entre 1 e 200 carancter", "danger")
        return redirect("/reservas")

    conexao = None
    cursor = None
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        conexao.start_transaction()
        #Verifica se a sala existe e está na ativa
        cursor.execute("""
            SELECT id_sala FROM sala
            WHERE id_sala = %s AND disponibilidade = 1
            FOR UPDATE
            """,(id_sala,))
        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Sala inexistente ou inativa.", "danger")
            return redirect("/reservas")

        #confere se o usuario temporario existe
        cursor.execute('SELECT id_usuario FROM usuario WHERE id_usuario = %s AND ativo = 1')
        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Usuario de teste nao cadastrado")
            return redirect("/reservas")
        #Verifica conflito de horário
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM reserva
            WHERE id_sala = %s
                AND data_reserva = %s
                AND status = 'confirmada'
                AND horario_inicio < %s
                AND horario_fim > %s
            """, (
                id_sala, data_reserva, horario_fim, horario_inicio))

        if cursor.fetchone()["total"] > 0:
            conexao.rollback()
            flash("Sala já reservada nesse horário.","danger")
            return redirect("/reservas")
        
# Gravar a reserva
        cursor.execute("""
            INSERT INTO reserva
            (
            horario_inicio, horario_fim, id_sala, id_usuario, data_reserva, status, finalidade)
            VALUES
            (%s, %s , %s , %s , %s , %s , %s)""",(
            horario_inicio, horario_fim, id_sala, data_reserva, "Confirmada", finalidade
            ))
        conexao.commit()


        flash("Reserva realizada com sucesso!", "success")
        return redirect("/reservas")

    except Error:
        if conexao.in_transaction:
            conexao.rollback()
        app.logger.exception("Erro ao salvar a reserva")
        flash("Erro ao cadastrar a reserva", "danger")
        return redirect("/reservas")

    finally:
        cursor.close()
        conexao.close()

@app.route("/login", methods = ["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    senha = request.form.get("senha","")

    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_usuario, id_perfil, nome, email, senha
            From usuario
            WHERE email = %s
            AND ativo =  1""",(email,))

        usuario = cursor.fetchone()

        if not usuario or not check_password_hash(
            usuario ["senha"], senha
        ):
            flash("E-mail ou senha invalido", "danger")
            return redirect(url_for("login"))

        session.clear()

        session["id_usuario"] = usuario["id_usuario"]
        session["nome"] = usuario["nome"]
        session["id_perfil"] = usuario["id_perfil"]

        flash("login realizado com sucesso","sucess")
        return redirect(url_for("minhas_reservas"))
    except:
        app.logger.exception("error durante o login")
        flash("nao foi possivel realizar o login", "danger")
        return redirect(url_for("login"))

    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()
####################

@app.route("/logout", methods=["POST"])
@login_obrigatorio
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))

@app.route("/minhas_reservas", methods=["GET"])
@login_obrigatorio
def minhas_reservas():
    id_usuario = session["id_usuario"]
    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("""
                SELECT r.id_reserva, s.nome_sala AS nome_sala,
                r.data_reserva, r.horario_inicio, r.horario_fim,
                r.finalidade, r.status 
                FROM reserva AS r
                INNER JOIN sala AS s ON r.id_sala = s.id_sala
                WHERE r.id_usuario = %s
                ORDER BY 
                r.data_reserva DESC,
                r.horario_inicio DESC""", (id_usuario,))

        reservas = cursor.fetchall()
        return render_template("minhas_reservas.html", reservas=reservas)
    
   # except Exception:
        app.logger.exception("Erro ao consultar reservas")
        flash("Não foi possível consultar suas reservas.", "danger")
        return redirect(url_for("listar_salas"))#
    
    except Exception as erro:
        app.logger.exception("Erro ao consultar reservas")
        return f"<h1>O erro é:</h1><p>{erro}</p>"
    
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()

@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)