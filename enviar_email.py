import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

load_dotenv()

remetente = os.getenv("email_outlook")
senha = os.getenv("senha_outlook")

def send_email(data_envio, destinatario, smtp_server, smtp_port, texto):
    msg = MIMEText(texto)
    msg["Subject"] = f"Resposta ao email enviado no dia {data_envio}"
    msg["From"] = remetente
    msg["To"] = destinatario

    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(remetente, senha)
        smtp.send_message(msg)