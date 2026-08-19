from paddleocr import PaddleOCR
from dotenv import load_dotenv
import re
import time
import numpy as np
from TextSimilarity import compare_names
from call_ollama import call_llama, get_token, image_converter, limitar_imagem, extrair_horas_afastamento

inicio = time.perf_counter()

load_dotenv()

bearer_token = get_token()

def paddle_ocr(payload, nome_real):

    print("Usando o PaddleOCR...")

    ocr = PaddleOCR(lang="pt", enable_mkldnn=False)

    img = image_converter(payload)

    for pagina in img:

        pagina = limitar_imagem(pagina)

        pagina_np = np.array(pagina)

        resultado = ocr.predict(pagina_np)

        texto_completo = ""
        for res in resultado:
            textos = res["rec_texts"]
            for texto in textos:
                texto_completo += texto + "\n"

    prompt_1 = (
            "Você é um sistema de extração de informações de atestados médicos.\n\n"
    
            "Leia TODO o texto a seguir, que foi extraído de um atestado, antes de responder.\n"
            "Extraia apenas as informações solicitadas.\n"
            "A resposta deve conter EXATAMENTE o formato especificado.\n\n"
    
            "CAMPOS A EXTRAIR:\n"
            "- Nome completo do beneficiário do atestado\n"
            "- Data de emissão\n"
            "- Data de início do afastamento\n"
            "- Quantidade de horas de afastamento\n"
            "- Nome completo do médico\n"
            "- CRM do médico\n"
            "- CID\n\n"
    
            "REGRAS GERAIS:\n"
            "- Preserve exatamente a grafia encontrada no documento.\n"
            "- Não corrija nomes.\n"
            "- Ignore nomes de hospitais, clínicas, laboratórios, empresas, logotipos e instituições.\n"
            "- O médico é o profissional responsável pela assinatura ou emissão do documento.\n"
            "- Utilize somente o CRM do médico responsável.\n"
            "- Utilize datas no formato DD/MM/AAAA sempre que possível.\n"
            "- O campo PACIENTE deve conter o nome da pessoa beneficiária do atestado, ou seja, a pessoa que será afastada de suas atividades habituais.\n"
            "- Em atestados comuns, a pessoa beneficiária é o paciente atendido.\n"
            "- Em atestados de acompanhamento, a pessoa beneficiária é o acompanhante que recebeu o atestado, mesmo que o documento também informe o nome do paciente atendido.\n\n"
    
            "REGRAS PARA O PACIENTE:\n"
            "- Identifique corretamente para quem o atestado foi emitido.\n"
            "- Utilize o contexto do documento para determinar quem será afastado de suas atividades.\n"
            "- Caso parte do nome esteja pouco legível, utilize o contexto do documento para identificar o nome mais provável.\n"
            "- Nunca invente um nome completamente diferente do que está visível.\n\n"
    
            "REGRAS PARA OS DEMAIS CAMPOS:\n"
            "- Nunca complete informações parcialmente legíveis.\n"
            "- Nunca deduza datas, CRM, CID, horas ou nome do médico.\n"
            "- Se houver qualquer dúvida sobre um desses campos, responda 'NÃO IDENTIFICADO'.\n\n"
    
            "REGRAS ESPECÍFICAS:\n"
            "- Se o documento não possuir CID, responda 'NÃO INFORMADO'.\n"
            "- Se houver mais de um CID, informe todos separados por vírgula.\n"
            "- Se houver afastamento em dias, converta para horas considerando 8 horas por dia.\n"
            "- Se o afastamento estiver em horas, mantenha o valor informado.\n"
            "- Se houver mais de um médico, utilize apenas aquele que assina o atestado.\n"
            "- Se o período de afastamento informado for 'Vespertino' ou 'Matutino', considerar o número de horas como 4.\n"
            "- Se a data de início não estiver explícita, mas o documento indicar que o afastamento inicia na data da emissão, utilize a data de emissão.\n"
            "- Não inclua informações adicionais junto ao CRM.\n"
            "- Informe apenas o número do CRM exatamente como aparece no documento.\n"
            "- Não inclua RQE, especialidade ou outros registros profissionais no campo CRM.\n\n"
    
            "VERIFICAÇÃO FINAL:\n"
            "- Revise todos os campos antes de responder.\n"
            "- Se houver dúvida em qualquer campo, exceto PACIENTE, responda 'NÃO IDENTIFICADO'.\n"
            "- Para PACIENTE, informe o nome mais provável de ser o beneficiário.\n\n"
    
            "IMPORTANTE:\n"
            "- Não escreva explicações.\n"
            "- Não escreva comentários.\n"
            "- Não escreva frases.\n"
            "- Não utilize Markdown.\n"
            "- Não escreva nenhuma linha além das especificadas abaixo.\n\n"
    
            "FORMATO OBRIGATÓRIO:\n"
            "PACIENTE=<valor>\n"
            "DATA_EMISSAO=<valor>\n"
            "DATA_INICIO=<valor>\n"
            "HORAS_AFASTAMENTO=<valor>\n"
            "MEDICO=<valor>\n"
            "CRM=<valor>\n"
            "CID=<valor>\n\n"
            "O texto a ser analisado está apresentado abaixo:\n"
            "============ INÍCIO DO TEXTO EXTRAÍDO ===========\n"
            f"\n{texto_completo}\n"
            "============ FIM DO TEXTO EXTRAÍDO =============="
        )
    
    
    resposta = call_llama(bearer_token=bearer_token, images=None, prompt=prompt_1)
    texto_paddle = resposta.get("response") or ""

    match = re.search(r"PACIENTE\s*[:=]\s*(.+)", texto_paddle) #Aceita "PACIENTE=" "PACIENTE: " e "PACIENTE ="

    if match:
        nome = match.group(1).strip()
    else:
        nome = texto_paddle

    hora = extrair_horas_afastamento(texto_paddle)

    score = compare_names(nome, nome_real)

    return hora, score

print("Tarefa concluída")


final = time.perf_counter()

print(f"Tempo de execução: {final - inicio:.2f} segundos")