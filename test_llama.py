from paddle_ocr import paddle_ocr
from pathlib import Path
import re
import time
import os
from dotenv import load_dotenv

inicio = time.perf_counter()

load_dotenv()

path = Path(os.getenv("ATESTADOS_URL"))

horas_rotulo = [8, 1, 8, 8, 4, 4, 8, 8, 24, 8, 16, 4, 4, 8, 4, 4, 24, 8, 16, 4, 8, 4, 4, 4, 8, 4, 8, 3, 4, 4, 8, 8, 4, 8, 4, 8, 8, 8, 8, 8, 8, 8, 8]

scores = []
horas = []
with open("Teste_LLama.txt", "w", encoding="utf-8") as write:
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

        write.write(f"Nome extraído: {nome}, Nome real: {nome_real},\n Horas extraídas: {hora}, Score: {score['similarity']}\n\n")

#print(resposta)

print(scores)

print(f"Média: {sum(scores)/len(scores)}")

quantidade = sum(1 for score in scores if score > 0.8)
total = len(scores)

print("\n Validação por nomes: \n")
print("Acertos: ", quantidade)
print("Total: ", total)
print(f"Percentual de acertos:  {quantidade*100/total :.2f} %")

soma = 0
for score in scores:
    soma += score
print("Média: ", soma/total)


acertos_horas = 0
unknown = 0
for i, hora in enumerate(horas):
    if hora == str(horas_rotulo[i]):
        acertos_horas += 1
    elif hora == "NÃO IDENTIFICADO":
        unknown += 1

print("\n Acertos nas horas de afastamento: \n")
print("Acertos: ", acertos_horas)
print("Total: ", total)
print(f"Percentual de acertos: {acertos_horas*100/total:.2f} %") 
print("Contagem de horas não identificadas: ", unknown)
print(f"\n Horas afastamento: \n {horas}")

fim = time.perf_counter()

print(f"Tempo de execução: {fim - inicio:.2f} segundos")
