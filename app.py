import os
from flask import Flask
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def conectar_branco():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        passworf=os.getenv("DB_PASSAWORD"),
        database=os.getenv("DB_NAME")
    )
@app.route("/")

def listar_salas():
    conexao = conectar_branco()
    curso = conexao.cursor(dictionary=True)

    curso.execute("""
    
    """)

    salas = cursor.


def inicio():
    return "<h1> bem vindo ao senac reserva </h1>"

if __name__ == "__main__":
    app.run(debug=True)
