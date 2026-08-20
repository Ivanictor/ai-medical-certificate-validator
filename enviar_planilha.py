import win32com.client
from pathlib import Path
import sys
import os

if getattr(sys, "frozen", False):
    base_dir = Path(sys.executable).parent
else:
    base_dir = Path(__file__).resolve().parent

excel_path = base_dir / "teste_atestados.xlsm"

if not excel_path.exists():
    raise FileNotFoundError(f"Planilha não encontrada: {excel_path}")

def enviar_dados_planilha(nome, email, horas):
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = True

    arquivo = excel.Workbooks.Open(str(excel_path))

    planilha = arquivo.Worksheets("Envio")

    planilha.Range("H18").Value = nome
    planilha.Range("J18").Value = email
    planilha.Range("L18").Value = horas

    excel.Run("EnviarDados")

    arquivo.Save()
    arquivo.Close()
    excel.Quit()
    print("\nDados enviados para a planilha")