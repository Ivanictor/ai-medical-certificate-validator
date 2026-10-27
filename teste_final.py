import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import os
import re
from pathlib import Path
import pandas as pd
import sqlite3
import time

inicio = time.perf_counter()

load_dotenv()

def enviar_email(caminho_anexo: Path, filename: str, subtype: str, maintype: str, nome_paciente: str) -> bool:

    remetente = os.getenv("email_outlook")
    destinatario = os.getenv("email_outlook")
    senha = os.getenv("senha_outlook")

    msg = EmailMessage()

    msg["From"] = remetente
    msg["To"] = destinatario
    msg["Subject"] = "Atestado"

    msg.set_content(
        f"Nome: {nome_paciente}\n"
        "CPF: XXXXXXXXXXX\n"
    )

    # Lê o arquivo
    with open(caminho_anexo, "rb") as arquivo:
        dados = arquivo.read()

    # Adiciona o anexo
    msg.add_attachment(
        dados,
        maintype=maintype,
        subtype=subtype,
        filename=filename
    )

    # Conecta ao servidor SMTP
    try:
        with smtplib.SMTP("mail.goias.gov.br", 587) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha)
            servidor.send_message(msg)

        print("E-mail enviado!")
        return True

    except smtplib.SMTPException as e:
        print(f"Erro ao enviar o email: {e}")
        return False

def loop_de_teste() -> list[int]:

    path = Path(os.getenv("ATESTADOS_DIGITAIS_URL"))
    #path = Path(os.getenv("ATESTADOS_DIGITAIS_URL"))
    lista_horas_enviadas = []

    for arquivo in path.iterdir():

        if arquivo.is_file() is not True:
            continue

        print(arquivo.name)

        if arquivo.suffix == ".pdf":
            maintype = "application"

        elif arquivo.suffix in (".png", ".jpg", ".jpeg"):
            maintype = "image"

        else:
            continue

        padrao = r"^(.+?)(?:\s+\d{2}-\d{2}-\d{2})?$"
        resultado = re.match(padrao, arquivo.stem)

        if resultado:
            nome_real = resultado.group(1)

        else:
            nome_real = arquivo.stem

        suffix = arquivo.suffix.lstrip(".")

        enviado = enviar_email(
            caminho_anexo=arquivo, 
            filename=arquivo.name, 
            subtype=suffix, 
            maintype=maintype,
            nome_paciente=nome_real)

        if enviado:
            lista_horas_enviadas.append(1)

        else:
            lista_horas_enviadas.append(0)

        time.sleep(40)

    return lista_horas_enviadas

def verifica_horas(lista_horas_enviadas: list):
    lista_horas = []
    #horas_rotulo = [8, 1, 8, 8, 4, 4, 8, 8, 24, 8, 16, 4, 4, 8, 4, 4, 24, 8, 16, 4, 8, 4, 4, 4, 8, 4, 8, 3, 4, 4, 8, 8, 4, 8, 4, 8, 8, 8, 8, 8, 8, 8, 8]
    horas_rotulo = [8, 3, 2, 8, 8, 8, 4, 4, 4, 16, 24, 8, 8, 16, 4, 8, 4, 4, 4, 4, 8, 8, 8, 8, 8, 5, 4, 4, 4, 8, 4, 4, 8, 8, 4, 8, 8, 4, 4, 4, 8, 4, 4, 16, 4, 8, 8, 8, 4, 8] #Atestados digitais

    acertos = 0

    for i, item in enumerate(lista_horas_enviadas):
        if item == 1:
            lista_horas.append(horas_rotulo[i])

    conexao = sqlite3.connect("atestados.db")
    df_banco = pd.read_sql(
        "SELECT nome, tipo_arquivo, horas_solicitadas, status FROM atestados ORDER BY nome", 
        conexao
        )

    qtd_atestados = len(df_banco["nome"])

    qtd_nomes_nao_reconhecidos = df_banco["status"].value_counts().get(
        "Nome não reconhecido pelo Llama", 0)

    df_processados = df_banco.query("status == 'Processado'")

    qtd_horas_nao_reconhecidas = df_processados["horas_solicitadas"].isin([0, "0"]).sum()

    for i, hora in enumerate(lista_horas):
        if df_banco.loc[i, "horas_solicitadas"] == hora:
            acertos += 1

    total_reconhecidos = len(df_processados["nome"])
    erros = total_reconhecidos - qtd_horas_nao_reconhecidas - acertos

    print(f"Quantidade de atestados reconhecidos: {qtd_atestados}/43\n")
    print(f"Quantidade de atestados com nome não reconhecido pelo Llama: {qtd_nomes_nao_reconhecidos}\n")
    print(f"Quantidade de atestados com horas não encontradas pelo Llama: {qtd_horas_nao_reconhecidas}\n")
    print(f"Acertos totais: {acertos}\n")
    print(f"Falsos positivos: {erros}\n")

    df_banco.to_csv("Test_report.csv")


lista_horas_enviadas = loop_de_teste()
print(lista_horas_enviadas)
#verifica_horas(lista_horas_enviadas)

fim = time.perf_counter()

print(f"Tempo de execução: {fim - inicio:.2f} segundos")




        