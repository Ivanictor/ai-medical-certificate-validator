from paddle_ocr import paddle_ocr
import traceback

arquivo = r"C:\Dados_teste\Atestados_Teste\Atestados_digitais\CLARALUZ PEREIRA DE MELO SOUSA.pdf"
arquivo_2 = r"C:\Dados_teste\Atestados_Teste\Atestados_digitais\LUCIANA SOARES DE ARAUJO SANTANA.pdf"
arquivo_3 = r"C:\Dados_teste\Atestados_Teste\Atestados_digitais\JOAO VITOR ESPINDOLA SANTANA.pdf"
arquivo_4 = r"C:\Dados_teste\Atestados_Teste\Atestados_digitais\KEILIANA CESAR GONÇALVES.pdf"

with open(arquivo_3, "rb") as f:
    payload = f.read()

try:
    _, score, _, _, _, _, _, texto_paddle, _, _ = paddle_ocr(payload, "", "application/pdf")
    print(score)
except Exception:
    traceback.print_exc()
