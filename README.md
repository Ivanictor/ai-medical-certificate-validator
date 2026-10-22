# AI Medical Certificate Validator

O projeto consiste em um sistema simples, ainda em desenvolvimento, para validar atestados e extrair informações deles (nome e horas solicitadas, por exemplo) de modo a agilizar o processo de validação de atestados realizados pelo setor de RH da SEAD

## Estrutura

O projeto foi construído até aqui com a utilização das seguintes tecnologias:

`Python`: Linguagem principal <br>
`PaddleOCR`: Biblioteca para reconhecimento óptico de caracteres (OCR) <br>
`Llama`: LLM (large language model) usada para análise dos textos extraídos pelo OCR. Modelo: llama-3.1-8b-instruct <br>
`SMTP`: Conexão e envio de emails de resposta <br>
`IMAP`: Conexão e leitura de emails <br>
`RapidFuzz`: Biblioteca Python para realizar correspondência entre o nome no atestado e o nome informado no corpo do email usando Fuzzy Matching<br>
`SQLite`: Banco de dados <br>
`Tkinter`: Biblioteca Python utilizada para criar aplicações desktop <br>


## Funcionamento

O projeto considera o recebimento de atestados como realizado por meio de um e-mail institucional. Dessa forma, o sistema desenvolvido utiliza o protocolo IMAP para monitorar a caixa postal, avaliar as mensagens recebidas, filtrar os emails que se destinam ao envio de atestados (através do assunto) e extrair o arquivo em anexo.

Considera-se que os emails a serem enviados deverão conter "Atestado" no assunto, o nome e o CPF do beneficiário do atestado escritos no corpo do email e o arquivo em anexo. 

A cada email recebido, o sistema procurará por emails com o termo "Atestado" declarado no campo do assunto do email. Os emails que atenderão à condição serão analisados e o arquivo em anexo será convertido em imagem, redimensionado e encaminhado ao processo de reconhecimento óptico de caracteres (OCR), realizado com o PaddleOCR. O Paddle deverá extrair o texto presente no atestado e retorná-lo em forma de string, de modo que possa ser incluído no prompt a ser enviado para o Llama. 

O Llama, em seu modelo llama-3.1-8b-instruct, foi empregado com o objetivo de analisar os textos retirados dos atestados. Primeiro, o Llama analisa o texto e retorna se o documento é ou não um atestado, excluindo o documento da análise em caso negativo. Depois, caso o atestado seja validado, o Llama extrai dele as seguintes informações: o nome do beneficiário do atestado, a quantidade de horas requisitadas para abono, o nome do médico, o CRM do médico e o CID, a data de emissão e a data de início do afastamento (se estiverem explícitos no email). O nome identificado pelo Llama é comparado ao nome informado no corpo do email utilizando a técnica de fuzzy matching e o score calculado é utilizado para validar a qualidade da informação extraída pelo OCR e pela IA. Se o score não atingir um valor mínimo, os dados são registrados no banco com o status "nome não reconhecido pelo Llama". Caso o score seja bom o suficiente, os dados são registrados no banco de dados na mesma forma como foram extraídos. 

Por fim, os dados armazenados no banco são exibidos em uma aplicação desktop criada com o Tkinter, que acessa o banco de dados e permite a visualização dos atestados enviados, tal como as informações extraídas do corpo do atestado. Apresenta funções de filtro, edição dos documentos e/ou de informações e também o envio de novos atestados manualmente. O corpo dos atestados é exibido na aplicação, viabilizando a análise manual por parte dos funcionários do RH. 