import re

def formatar_cpf(cpf: str):
    return re.sub(r"\D", "", cpf)