import sqlite3
from typing import Any

def connect_and_create_table_if_not_exists() -> sqlite3.Connection:
    """Cria o banco se ele não existir, só é executado dentro de enviar_dados_banco"""

    conexao = sqlite3.connect("atestados.db")

    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS atestados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL,
            email TEXT NOT NULL,
            arquivo BLOB NOT NULL,
            tipo_arquivo TEXT NOT NULL,
            horas_solicitadas INTEGER,
            status TEXT NOT NULL,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analisado INTEGER NOT NULL DEFAULT 0
        )
    """)

    conexao.commit()

    return conexao

def enviar_dados_banco(
        nome: str,
        cpf: str, 
        email: str, 
        horas_solicitadas: Any, 
        payload: bytes, 
        content_type: str, 
        status: str) -> bool:
    
    conexao = connect_and_create_table_if_not_exists()

    cursor = conexao.cursor()

    arquivo_blob = sqlite3.Binary(payload)

    try:

        cursor.execute("""
            INSERT INTO atestados (
                nome,
                cpf, 
                email,
                arquivo, 
                tipo_arquivo, 
                horas_solicitadas,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            nome,
            cpf, 
            email,
            arquivo_blob, 
            content_type, 
            horas_solicitadas, 
            status
        ))

        conexao.commit()
        return True

    except Exception as e:
        conexao.rollback()
        raise Exception(f"Erro ao enviar os dados ao banco: {e}")

    finally:
        conexao.close()
        


