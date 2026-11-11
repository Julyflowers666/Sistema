import os
from flask import Flask, render_template
from flask import request, render_template, redirect, flash
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
if not app.secret_key:
    raise RuntimeError("Configure a CHAVE SECRETA no arquivo .env")


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
        app.log_exception("falha ao consultar salas")
        return render_template("error.html", mensagem="nao foi possivel consultar as salas"), 500
    finally:
        if curso: cursor.close()
        if conexao and conexao.is_connected(): conexao.close()

USUARIO_TESTE_ID = 1

@app.route("/reservas", methods=["GET", "POST"])
def reservar():
    if request.method == "GET":
        conexao = None
        cursor = None
        try:
            conexao = conectar_banco()
            cursor = conexao.cursor (dictionary=True)
            cursor.execute('SELECT id_sala, nome FROM sala_sala WHERE ativa = 1'\
                           'ORDEM BY id_sala')
            salas = cursor.fetchall()
            return render_template("reservas.html")
        except Error:
            app.loger.exception('falha ao carregar salas')
            return render_template('erro.html', mensagem="nao foi possivel carregar o formulario")
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
        cursor.execute('SELECT id_usuario FROM usuario WHERE id_usuario = %s AND disponibilidade = 1', (USUARIO_TESTE_ID,))
        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Usuario de teste nao cadastrado")
            return redirect("/reservar")
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
            horario_inicio, horario_fim, id_sala, USUARIO_TESTE_ID, data_reserva, "Confirmada", finalidade
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
    return render_template("login.html")
if __name__ == "__main__":
    app.run(debug=True)