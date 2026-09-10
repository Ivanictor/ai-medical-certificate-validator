from imap_tools import MailBox, AND
from dotenv import load_dotenv
import os
import re
import json
import smtplib
from datetime import date
import traceback
from call_ollama import get_token, call_llama, image_converter
from enviar_email import send_email
from paddle_ocr import paddle_ocr
from enviar_planilha import enviar_dados_planilha
import time

load_dotenv()

bearer_token = get_token()

smtp_server = "mail.goias.gov.br"
imap_server = "mail.goias.gov.br"
imap_port = 993
smtp_port = 587

email_local = os.getenv("email_outlook")
senha = os.getenv("senha_outlook")

ARQUIVO_PROCESSADOS = "processados.json"

prompt = (
    """Leia o documento a seguir e responda: 
    'Sim', caso o documento seja um atestado;
    'Não', caso o documento não seja um atestado.
    Seu formato de resposta deve incluir apenas 'Sim' ou 'Não', 
    não explique sua decisão"""
    )


def carregar_processados():
    if os.path.exists(ARQUIVO_PROCESSADOS):
        with open(ARQUIVO_PROCESSADOS, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def salvar_processado(message_id, processados):
    if not message_id:
        return
    processados.add(message_id)
    with open(ARQUIVO_PROCESSADOS, "w") as f:
        json.dump(list(processados), f)


processados = carregar_processados()

while True:
    try:
        print("\nConectando ao servidor IMAP...\n")
        with MailBox(imap_server).login(email_local, senha) as mailbox:

            while True:
                respostas = mailbox.idle.wait(timeout=60)

                if not respostas:
                    print("\nNenhuma alteração na caixa de entrada nos últimos 60 segundos")
                    continue
                print("\nFoi detectada uma alteração na caixa de entrada")

                mensagens = list(mailbox.fetch(AND(seen=False, subject="Atestado"), mark_seen=False))

                if not mensagens:
                    print("\nNenhum e-mail com o assunto 'Atestado' foi encontrado")

                for msg in mensagens:

                    message_id = msg.headers.get("message-id", [""])[0]

                    if message_id and message_id in processados:
                        print(f"\nE-mail {message_id} já processado anteriormente, pulando")
                        try:
                            mailbox.flag(msg.uid, "\\Seen", True)
                        except Exception as e:
                            print(f"Falha ao marcar e-mail já processado como lido: {e}")
                        continue

                    email_remetente = msg.from_
                    anexo_valido = False

                    for att in msg.attachments:
                        if att.content_type not in ("application/pdf", "image/jpeg", "image/png"):
                            continue

                        anexo_valido = True

                        payload = att.payload

                        images = image_converter(payload, att.content_type)

                        validacao = call_llama(bearer_token, images["base64"], prompt=prompt)

                        validacao_atestado = validacao.get("response") or ""

                        print(f"Resposta do Llama: {validacao_atestado}")

                        if validacao_atestado == "Não":

                            print("\nO documento não é atestado")

                            texto = "O documento que você enviou não é um atestado válido"
                            data_envio = date.today().strftime("%d/%m/%Y")
                            try:
                                send_email(
                                    data_envio=data_envio,
                                    destinatario=email_remetente,
                                    smtp_server=smtp_server,
                                    smtp_port=smtp_port,
                                    texto=texto)

                            except smtplib.SMTPException as e:
                                print(f"Erro SMTP: {e}")

                        elif validacao_atestado == "Sim":
                            texto_email = msg.text
                            nome_real = re.search(r"Nome:\s*(.*)", texto_email).group(1)
                            hora, score = paddle_ocr(payload, nome_real, att.content_type)

                            if score < 0.8:
                                print("\nNome não reconhecido, enviado 'aplicação manual' ")
                                enviar_dados_planilha(
                                    "Preenchimento manual", email_remetente, "Preenchimento manual"
                                    )

                            elif score >= 0.8:
                                print(f"Nome reconhecido: {nome_real}")
                                enviar_dados_planilha(nome_real, email_remetente, hora)

                        else:
                            print("\nLlama respondeu no formato errado")
                            enviar_dados_planilha("Preenchimento manual", email_remetente, "Preenchimento manual")

                    if not anexo_valido:
                        print("\nNão há anexos válidos\n")
                        texto = "Não há anexos válidos ao seu email. Você se esqueceu de anexar o atestado?"
                        data_envio = date.today().strftime("%d/%m/%Y")
                        try:
                            send_email(
                                data_envio=data_envio,
                                destinatario=email_remetente,
                                smtp_server=smtp_server,
                                smtp_port=smtp_port,
                                texto=texto)

                        except smtplib.SMTPException as e:
                            print(f"Erro SMTP: {e}")

                    if anexo_valido:
                        salvar_processado(message_id, processados)
                        try:
                            mailbox.flag(msg.uid, "\\Seen", True)
                        except Exception as e:
                            print(f"Falha ao marcar como lido, mas já registrado localmente: {e}")

    except Exception as e:
        print(f"Erro no processamento: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        traceback.print_exc()
        print("Tentando reconectar em 30 segundos..")
        time.sleep(30)