import sqlite3
from typing import Any
from datetime import datetime

def connect_and_create_table_if_not_exists() -> sqlite3.Connection:
    """Cria o banco se ele não existir, só é executado dentro de enviar_dados_banco"""

    conexao = sqlite3.connect("atestados_digital.db")

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
            medico TEXT NOT NULL,
            crm TEXT NOT NULL,
            cid TEXT NOT NULL,
            data_inicio TEXT,
            data_emissao TEXT,
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
        medico: str,
        crm: str,
        cid: str,
        data_inicio: str,
        data_emissao: str, 
        payload: bytes, 
        content_type: str, 
        status: str) -> bool:
    
    conexao = connect_and_create_table_if_not_exists()

    cursor = conexao.cursor()

    arquivo_blob = sqlite3.Binary(payload)

    try:
        start_date = datetime.strptime(data_inicio, "%d/%m/%Y").date().isoformat()

    except ValueError:
        start_date = None

    try:
        emission_date = datetime.strptime(data_emissao, "%d/%m/%Y").date().isoformat()

    except ValueError:
        emission_date = None

    try:

        cursor.execute("""
            INSERT INTO atestados (
                nome,
                cpf, 
                email,
                arquivo, 
                tipo_arquivo, 
                horas_solicitadas,
                medico,
                crm,
                cid,
                data_inicio,
                data_emissao,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nome,
            cpf, 
            email,
            arquivo_blob, 
            content_type, 
            horas_solicitadas,
            medico,
            crm,
            cid,
            start_date,
            emission_date, 
            status
        ))

        conexao.commit()
        return True

    except Exception as e:
        conexao.rollback()
        raise Exception(f"Erro ao enviar os dados ao banco: {e}")

    finally:
        conexao.close()
        


