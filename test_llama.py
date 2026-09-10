from paddle_ocr import paddle_ocr
from pathlib import Path
import re
import time
import os
from dotenv import load_dotenv

inicio = time.perf_counter()

load_dotenv()

path = Path(os.getenv("ATESTADOS_URL"))

scores = []
horas = []
for arquivo in path.iterdir():

    if arquivo.is_file() is not True:
        continue

    print(arquivo.name)
    
    with open(arquivo, "rb") as f:
        arquivo_bytes = f.read()

    if arquivo.name.endswith(".pdf"):
        content_type = "application/pdf"

    elif arquivo.suffix.lower() in [".jpg", ".jpeg"]:
        content_type = "image/jpeg"

    elif arquivo.name.endswith(".png"):
        content_type = "image/png"

    padrao = r"^(.+?)(?:\s+\d{2}-\d{2}-\d{2})?$"
    resultado = re.match(padrao, arquivo.stem)

    if resultado:
        nome_real = resultado.group(1)

    else:
        nome_real = arquivo.stem


    hora, score, _, nome, _ = paddle_ocr(payload=arquivo_bytes, 
                                                        nome_real=nome_real, 
                                                        content_type=content_type)

    horas.append(hora)
    scores.append(score.get("similarity"))

    with open("Teste_LLama.txt", "a", encoding="utf-8") as f:
        f.write(f"Nome extraído: {nome}, Nome real: {nome_real},\n Horas extraídas: {hora}, Score: {score}\n\n")

#print(resposta)

print(scores)

print(f"Média: {sum(scores)/len(scores)}")

fim = time.perf_counter()

print(f"Tempo de execução: {fim - inicio:.2f} segundos")
