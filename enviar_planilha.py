import win32com.client
import os
from dotenv import load_dotenv

load_dotenv()

def enviar_dados_planilha(nome, email, horas):
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = True

    arquivo = excel.Workbooks.Open(os.getenv("excel_path"))

    planilha = arquivo.Worksheets("Envio")

    planilha.Range("H18").Value = nome
    planilha.Range("J18").Value = email
    planilha.Range("L18").Value = horas

    excel.Run("EnviarDados")

    arquivo.Save()
    arquivo.Close()
    excel.Quit()