# AI Medical Certificate Validator

O projeto consiste em um sistema simples, ainda em desenvolvimento, para validar atestados e extrair informações deles (nome e horas solicitadas, por exemplo) de modo a agilizar o processo de validação de atestados realizados pelo setor de RH da SEAD

## Estrutura

O projeto foi construído até aqui com a utilização das seguintes tecnologias:

`Python`: Linguagem principal <br>
`PaddleOCR`: Biblioteca para reconhecimento óptico de caracteres (OCR) <br>
`Llama`: LLM (large language model) usada para análise dos textos extraídos pelo OCR. Modelo: llama3.2-vision:11b <br>
`SMTP`: Conexão e envio de emails de resposta <br>
`IMAP`: Conexão e leitura de emails <br>