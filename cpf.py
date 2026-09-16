import re

def formatar_cpf(cpf):
    return re.sub(r"\D", "", cpf)