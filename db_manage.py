import sqlite3
from datetime import date

def create_database_if_not_exists():
    conn = sqlite3.connect("banco_atestados.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS atestados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        status TEXT NOT NULL,
        arquivo BLOB NOT NULL,
        extensao TEXT NOT NULL,
        data_recebimento TEXT)"""
    )
    conn.commit()
    conn.close()

def atualizar_banco(nome, status, arquivo, extensao):
    conn = sqlite3.connect("banco_atestados.db")
    cursor = conn.cursor()

    data_recebimento = date.today()

    cursor.execute(
        """
        INSERT INTO atestados 
        (nome, status, arquivo, extensao, data_recebimento)
        VALUES (?, ?, ?, ?, ?)
        """,
        (nome, status, arquivo, extensao, data_recebimento))

    conn.commit()
    conn.close()