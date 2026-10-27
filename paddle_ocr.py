from paddleocr import PaddleOCR
from dotenv import load_dotenv
import re
import time
import numpy as np
import json
from TextSimilarity import compare_names
from call_ollama import (
    call_llama,
    get_token,
    image_converter,
    limitar_imagem,
    extrair_horas_afastamento,
    extrair_cid,
    extrair_medico,
    extrair_crm,
    extrair_data_emissao,
    extrair_data_inicio
    )

inicio = time.perf_counter()

load_dotenv()

bearer_token = get_token()

# ---------------------------------------------------------------------------
# Limiares do gate de qualidade (ponto de partida: calibrar com documentos rotulados)
# ---------------------------------------------------------------------------
THR_LINHA = 0.85          # linha com score abaixo disso conta como "baixa confiança"
MIN_CHARS_LINHA = 3       # ignora fragmentos muito curtos (score instável)
MIN_SCORE_POND = 0.92     # média ponderada por caracteres mínima
MAX_FRAC_BAIXA = 0.15     # fração máxima de caracteres em linhas de baixa confiança
MIN_CHARS_DOC = 80        # mínimo de caracteres lidos no CORPO do documento
THR_CAMPO = 0.90          # nome do beneficiário com score abaixo disso = incerto
BLOQUEAR_CAMPO_INCERTO = True   # False = segue para o Llama e apenas sinaliza em ocr_info

_OCR = None


def get_ocr():
    global _OCR

    if _OCR is None:
        _OCR = PaddleOCR(lang="pt", enable_mkldnn=False)

    return _OCR


# ---------------------------------------------------------------------------
# OCR com coleta de score por linha
# ---------------------------------------------------------------------------
def ocr_com_scores(payload: bytes, content_type: str) -> tuple[str, list[dict]]:
    """Roda o PaddleOCR em todas as páginas.
    Retorna o texto completo (como antes) e a lista de linhas com seus scores."""
    ocr = get_ocr()
    img = image_converter(payload, content_type)

    texto_completo = ""
    linhas = []

    for i, pagina in enumerate(img["pil"]):
        pagina = limitar_imagem(pagina)
        pagina_np = np.array(pagina)

        resultado = ocr.predict(pagina_np)

        for res in resultado:
            for texto, s, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
                pts = np.array(poly)
                box = [float(pts[:, 0].min()), float(pts[:, 1].min()),
                       float(pts[:, 0].max()), float(pts[:, 1].max())]
                linhas.append({"pagina": i, "texto": texto, "score": float(s), "box": box})
                texto_completo += texto + "\n"

    return texto_completo, linhas


# ---------------------------------------------------------------------------
# Gate de qualidade 
# ---------------------------------------------------------------------------
def qualidade_documento(linhas: list[dict], thr_linha: int = THR_LINHA, min_chars: int = MIN_CHARS_LINHA) -> dict:
    # ignora fragmentos muito curtos, cujo score é instável
    L = [l for l in linhas if len(l["texto"].strip()) >= min_chars]
    if not L:
        return {"n_chars": 0, "score_pond": 0.0, "frac_baixa": 1.0, "mediana": 0.0}

    s = np.array([l["score"] for l in L])
    w = np.array([len(l["texto"].strip()) for l in L], dtype=float)

    return {
        "n_chars": int(w.sum()),
        "score_pond": float((s * w).sum() / w.sum()),
        "frac_baixa": float(w[s < thr_linha].sum() / w.sum()),
        "mediana": float(np.median(s)),
    }


def decidir(q: dict, 
            min_pond: float = MIN_SCORE_POND, 
            max_frac_baixa: float = MAX_FRAC_BAIXA, 
            min_chars: int = MIN_CHARS_DOC) -> str:
    
    if q["n_chars"] < min_chars:
        return "REJEITADO"      # OCR quase não leu nada
    if q["score_pond"] >= min_pond and q["frac_baixa"] <= max_frac_baixa:
        return "APROVADO"
    return "BAIXA_QUALIDADE"    # manuscrito ou scan ruim


# Rótulos de campos preenchíveis. Aceita artigo inicial ("o interessado(a):"), variações de
# gênero "(a)" e "Nome do paciente". O (?!\w) evita casar prefixos de outras palavras (ex.: "Drogaria").
# Todos os rótulos são localizados (para não serem confundidos com valor do nome nem contarem
# como corpo), mas só os de NOME entram na decisão (ver RE_ROTULO_NOME).
_ROTULOS = (
    r"interessad[oa](?:\s*\(\s*[oa]\s*\))?"
    r"|pacient[ea]"
    r"|nome(?:\s+d[oa]s?\s+(?:pacient[ea]|m[ée]dic[oa]|interessad[oa](?:\s*\(\s*[oa]\s*\))?))?"
    r"|data|cid|crm"
    r"|dra?\.?"
    r"|sra?\.?(?:\s*\(\s*a\s*\)\.?)?"
    r"|m[ée]dic[oa]"
)
RE_ROTULO = re.compile(
    rf"^\s*(?:[oa]\s+)?({_ROTULOS})(?!\w)[\s:.\-]*(.*)$", re.I
)

# Rótulos do NOME do beneficiário (únicos avaliados no gate). "Nome do médico" fica de fora.
RE_ROTULO_NOME = re.compile(
    r"^(?:interessad|pacient|sra?\.?(?!\w)|nome(?!\s+d[oa]s?\s+m[ée]dic))", re.I
)


def campos_criticos(linhas: list[dict], min_chars: int = 2, linhas_abaixo: int = 1) -> dict:
    """Localiza os rótulos (Paciente, Interessado(a), Sr./Sra., Data, CRM, CID...) e, para cada um,
    o valor associado, buscando nesta ordem:
      1) o que vem depois do rótulo na mesma linha;
      2) caixas à direita, na mesma altura (outros rótulos ficam de fora);
      3) se nada foi achado, a(s) linha(s) logo ABAIXO do rótulo, por posição na página
         ("o interessado(a):" numa linha e o nome na seguinte).
    O score do campo é o menor entre os trechos encontrados."""
    campos = []
    for i, l in enumerate(linhas):
        m = RE_ROTULO.match(l["texto"])
        if not m:
            continue

        valores = []
        if len(m.group(2).strip()) >= min_chars:
            valores.append(l)

        x0, y0, x1, y1 = l["box"]
        h = max(y1 - y0, 1.0)
        outras = [(j, o) for j, o in enumerate(linhas)
                  if j != i and o["pagina"] == l["pagina"]
                  and len(o["texto"].strip()) >= min_chars
                  and not RE_ROTULO.match(o["texto"])]

        # 2) mesma altura, à direita
        for _, o in outras:
            ox0, oy0, ox1, oy1 = o["box"]
            mesma_altura = abs((oy0 + oy1) / 2 - (y0 + y1) / 2) < 0.6 * h
            if mesma_altura and ox0 >= x1 - 5:
                valores.append(o)

        # 3) logo abaixo, se não achou nada na mesma linha
        if not valores:
            abaixo = [o for _, o in outras
                      if o["box"][1] >= y1 - 0.3 * h and o["box"][1] - y1 <= 3 * h]
            abaixo.sort(key=lambda o: o["box"][1])
            valores.extend(abaixo[:linhas_abaixo])

        if valores:
            campos.append({
                "rotulo": m.group(1).lower(),
                "avaliar": bool(RE_ROTULO_NOME.match(m.group(1))),
                "valores": valores,
                "score_min": min(v["score"] for v in valores),
            })
    return campos


def avaliar_ocr(linhas: list[dict]) -> dict:
    """Gate em duas etapas:
    1) Qualidade do CORPO (linhas fora dos campos preenchíveis) = qualidade do scan/impressão.
    2) Qualidade do NOME do beneficiário, comparada ao corpo = indício de manuscrito.
    Os demais campos (data, CRM, CID...) são localizados apenas para saírem do corpo,
    mas não entram na decisão."""
    campos = campos_criticos(linhas)
    ids_campo = {id(v) for c in campos for v in c["valores"]}
    corpo = [l for l in linhas if id(l) not in ids_campo]

    q = qualidade_documento(corpo)
    decisao = decidir(q)

    campos_nome = [c for c in campos if c["avaliar"]]
    q["nome_localizado"] = bool(campos_nome)

    if decisao == "APROVADO" and any(c["score_min"] < THR_CAMPO for c in campos_nome):
        decisao = "CAMPO_INCERTO"   # corpo bem lido, mas o nome não

    q["decisao"] = decisao
    q["campos"] = [
        {"rotulo": c["rotulo"],
         "avaliado": c["avaliar"],
         "texto": " | ".join(v["texto"] for v in c["valores"]),
         "score_min": c["score_min"]}
        for c in campos
    ]
    return q


# ---------------------------------------------------------------------------
# Funções principais
# ---------------------------------------------------------------------------
def verifica_atestado_ocr(payload: bytes, content_type: str) -> tuple[str, list[dict]]:
    """Uso do OCR para validar se o documento é um atestado ou não"""
    print("Usando o PaddleOCR")

    texto_completo, linhas = ocr_com_scores(payload, content_type)

    return texto_completo, linhas


def montar_prompt(texto_completo: str) -> str:
    return (
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
        "- Se o período de afastamento informado for 'Vespertino', 'Matutino', 'Manhã' ou 'Tarde', considerar o número de horas como 4.\n"
        "- Se a data de início não estiver explícita, mas o documento indicar que o afastamento inicia na data da emissão, utilize a data de emissão.\n"
        "- Informe as datas de início e de emissão no formato DD/MM/YYYY. \n"
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


def paddle_ocr(nome_real: str, texto_completo: str, linhas: list[dict]) -> tuple:
    """OCR do texto completo, gate de qualidade e envio ao Llama para extração dos dados.

    Retorna:
        hora, score, crm, cid, medico, data_inicio, data_emissao,
        texto_paddle, nome, resposta, ocr_info

    Se o gate não aprovar o documento, o Llama NÃO é chamado: os campos vêm como None,
    texto_paddle traz a mensagem do motivo e ocr_info["decisao"] indica o status.
    """
    print("Avaliando a qualidade do OCR do documento...\n")

    # Gate: decide só com os sinais do OCR
    ocr_info = avaliar_ocr(linhas)
    ocr_info["linhas_baixas"] = [l for l in linhas if l["score"] < THR_LINHA]

    decisao = ocr_info["decisao"]
    bloquear = decisao in ("REJEITADO", "BAIXA_QUALIDADE") or (
        decisao == "CAMPO_INCERTO" and BLOQUEAR_CAMPO_INCERTO
    )

    if bloquear:
        if decisao == "REJEITADO":
            motivo = "OCR não conseguiu ler texto suficiente no documento."
        elif decisao == "CAMPO_INCERTO":
            motivo = "Nome do beneficiário com baixa confiança de leitura (possível manuscrito)."
        else:
            motivo = "Baixa qualidade de leitura do documento (scan ruim)."
        print(f"Gate do OCR: {ocr_info['decisao']}")
        return (None, None, None, None, None, None, None, motivo, None, None, ocr_info)

    prompt_1 = montar_prompt(texto_completo)

    resposta = call_llama(bearer_token=bearer_token, prompt=prompt_1)
    resposta_llm = json.loads(resposta["response"])
    texto_paddle = resposta_llm["choices"][0]["message"]["content"]

    match = re.search(r"PACIENTE\s*[:=]\s*(.+)", texto_paddle)  # Aceita "PACIENTE=" "PACIENTE: " e "PACIENTE ="

    if match:
        nome = match.group(1).strip()
    else:
        nome = texto_paddle

    hora = extrair_horas_afastamento(texto_paddle)

    medico = extrair_medico(texto_paddle)

    crm = extrair_crm(texto_paddle)

    cid = extrair_cid(texto_paddle)

    data_inicio = extrair_data_inicio(texto_paddle)

    data_emissao = extrair_data_emissao(texto_paddle)

    score = compare_names(nome, nome_real).get("similarity")

    return hora, score, crm, cid, medico, data_inicio, data_emissao, texto_paddle, nome, resposta, ocr_info


print("Tarefa concluída")


final = time.perf_counter()

print(f"Tempo de execução: {final - inicio:.2f} segundos")