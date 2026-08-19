from dotenv import load_dotenv
import requests
import re
import os
import time
import base64
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image

load_dotenv()

# Cache em memória
_token_cache = {
    "token": None,
    "expires_at": 0
}

def get_token():
    """
    Verifica se ainda existe um token válido no cache. 
    Se houver, utiliza. Se não houver, cria outro
    """
    now = time.time()

    #Verifica se o token existente ainda é válido e reutiliza se ainda for
    global _token_cache
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    
    url = "https://api.go.gov.br/token"
    headers = {
        "Authorization": f"Basic {os.getenv('BASIC_AUTH')}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }

    response = requests.post(url=url, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        token = token_data["access_token"]

        #Margem de segurança: código considera expirado com 1 minuto de antecedência
        expires_in = token_data.get("expires_in", 3600)
        _token_cache = {
            "token": token,
            "expires_at": now + expires_in - 60
        }
        return token
    
    else:
        raise Exception(f"Erro ao obter token: {response.status_code} - {response.text}")

def call_llama(bearer_token, images, prompt):
    """Envia a requisição à API do Llama com o prompt, o token e as imagens"""

    print("Usando o Llama...")
    
    url = "https://api.go.gov.br/ia/modelos-linguagem-natural/v2.0/generate"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }


    data = {
        "model": "llama3.2-vision:11b",
        "prompt": prompt,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    if images:
        data["images"] = [images[0]]

    response = requests.post(url=url, headers=headers, json=data)

    if response.status_code == 200:
        return {"response": response.text, "status_code": response.status_code}
    else:
        return {"error": response.status_code, "message": response.text}
    
def image_converter(payload, content_type):
    """Converte bytes de PDFs ou Imagem para Base64 e PIL.Image"""
    if content_type == "application/pdf":
        paginas = convert_from_bytes(payload)

    elif content_type in ("image/jpeg", "image/png"):
        paginas = [Image.open(BytesIO(payload))]
    else:
        return {"base64": [], "pil": []}

    images = []

    for pagina in paginas:
        buffer = BytesIO()
        pagina.save(buffer, format="JPEG")

        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        images.append(image_base64)

    return {
        "base64": image_base64, 
        "pil": paginas
        }

def extrair_horas_afastamento(texto):
    # Tenta capturar o número que vem logo antes de "horas"
    match_hora = re.search(
        r"HORAS_AFASTAMENTO\s*[:=]\s*.*?(\d+(?:[.,]\d+)?)\s*horas",
        texto,
        re.IGNORECASE
    )

    if not match_hora:
        # Fallback: pega o primeiro número logo após "HORAS_AFASTAMENTO="
        match_hora = re.search(
            r"HORAS_AFASTAMENTO\s*[:=]\s*(\d+(?:[.,]\d+)?)",
            texto,
            re.IGNORECASE
        )

    hora = match_hora.group(1).strip().replace(",", ".") if match_hora else "0"
    return hora

def limitar_imagem(img, max_side=4000):
    largura, altura = img.size

    maior_lado = max(largura, altura)

    if maior_lado <= max_side:
        return img

    escala = max_side/maior_lado

    novo_tamanho = (int(largura*escala), int(altura*escala))

    return img.resize(novo_tamanho)