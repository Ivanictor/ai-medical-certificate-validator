import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import sqlite3
import io
import pymupdf


class Aplicacao:

    STATUS_SUGERIDOS = [
        "Pendente",
        "Processado",
        "Não processado",
        "Nome não reconhecido pelo Llama",
    ]

    def __init__(self, root):

        self.root = root
        self.root.title("Gerenciador de Atestados")
        self.root.geometry("1100x500")

        # Conexão com o banco (timeout evita "database is locked"
        # se o monitor de e-mail estiver gravando ao mesmo tempo)
        self.conexao = sqlite3.connect("atestados.db", timeout=30)

        self.criar_banco()

        # ==========================================================
        # BOTÃO
        # ==========================================================

        ttk.Button(
            root,
            text="Adicionar atestado",
            command=self.adicionar_arquivo
        ).pack(pady=10)

        # ==========================================================
        # TABELA
        # ==========================================================

        self.tabela = ttk.Treeview(
            root,
            columns=(
                "id",
                "nome",
                "cpf",
                "email",
                "horas",
                "status",
                "data"
            ),
            show="headings"
        )

        self.tabela.heading("id", text="ID")
        self.tabela.heading("nome", text="Nome")
        self.tabela.heading("cpf", text="CPF")
        self.tabela.heading("email", text="Email")
        self.tabela.heading("horas", text="Horas solicitadas")
        self.tabela.heading("status", text="Status")
        self.tabela.heading("data", text="Data de cadastro")

        # Larguras
        self.tabela.column("id", width=50)
        self.tabela.column("nome", width=220)
        self.tabela.column("cpf", width=120)
        self.tabela.column("email", width=220)
        self.tabela.column("horas", width=130)
        self.tabela.column("status", width=120)
        self.tabela.column("data", width=150)

        self.tabela.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        # Duplo clique para visualizar/editar
        self.tabela.bind(
            "<Double-1>",
            self.visualizar_atestado
        )

        # Carrega os registros existentes
        self.carregar_atestados()

    # ==============================================================
    # BANCO DE DADOS
    # ==============================================================

    def criar_banco(self):
        """Mesmo esquema criado pelo enviar_banco.py."""

        cursor = self.conexao.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS atestados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cpf TEXT NOT NULL,
                email TEXT NOT NULL,
                arquivo BLOB NOT NULL,
                tipo_arquivo TEXT NOT NULL,
                horas_solicitadas INTEGER,
                status TEXT NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conexao.commit()

    # ==============================================================
    # CARREGAR REGISTROS
    # ==============================================================

    def carregar_atestados(self):

        # Limpa a tabela
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        cursor = self.conexao.cursor()

        cursor.execute("""
            SELECT
                id,
                nome,
                cpf,
                email,
                horas_solicitadas,
                status,
                data_cadastro
            FROM atestados
            ORDER BY id DESC
        """)

        for registro in cursor.fetchall():

            self.tabela.insert(
                "",
                "end",
                values=registro
            )

    # ==============================================================
    # ADICIONAR ARQUIVO
    # ==============================================================

    def adicionar_arquivo(self):

        caminho = filedialog.askopenfilename(
            title="Selecione o atestado",
            filetypes=[
                ("Imagens", "*.jpg *.jpeg *.png"),
                ("PDF", "*.pdf"),
                ("Todos os arquivos", "*.*")
            ]
        )

        if not caminho:
            return

        # ==========================================================
        # LÊ O ARQUIVO
        # ==========================================================

        with open(caminho, "rb") as arquivo:
            dados = arquivo.read()

        # ==========================================================
        # IDENTIFICA O TIPO DO ARQUIVO
        # ==========================================================

        caminho_lower = caminho.lower()

        if caminho_lower.endswith(".pdf"):
            tipo_arquivo = "application/pdf"

        elif caminho_lower.endswith((".jpg", ".jpeg")):
            tipo_arquivo = "image/jpeg"

        elif caminho_lower.endswith(".png"):
            tipo_arquivo = "image/png"

        else:
            messagebox.showerror(
                "Erro",
                "Tipo de arquivo não suportado."
            )
            return

        # ==========================================================
        # DADOS TEMPORÁRIOS (apenas para teste)
        # ==========================================================

        nome = "Paciente de teste"
        cpf = "00000000000"
        email = "teste@email.com"
        horas_solicitadas = None
        status = "Pendente"

        # ==========================================================
        # INSERE NO BANCO
        # ==========================================================

        try:
            with self.conexao:
                self.conexao.execute("""
                    INSERT INTO atestados (
                        nome,
                        cpf,
                        email,
                        arquivo,
                        tipo_arquivo,
                        horas_solicitadas,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    nome,
                    cpf,
                    email,
                    sqlite3.Binary(dados),
                    tipo_arquivo,
                    horas_solicitadas,
                    status
                ))

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível inserir o atestado:\n\n{erro}"
            )
            return

        self.carregar_atestados()

        messagebox.showinfo(
            "Sucesso",
            "Atestado adicionado ao banco de dados."
        )

    # ==============================================================
    # VISUALIZAR ATESTADO
    # ==============================================================

    def visualizar_atestado(self, event):

        item = self.tabela.selection()

        if not item:
            return

        # Obtém o ID da linha selecionada
        id_atestado = self.tabela.item(
            item[0],
            "values"
        )[0]

        # Os valores são lidos do banco (e não da tabela) para evitar
        # que o Tk converta o CPF em número e perca zeros à esquerda.
        cursor = self.conexao.cursor()

        cursor.execute("""
            SELECT
                nome,
                cpf,
                horas_solicitadas,
                status,
                arquivo,
                tipo_arquivo
            FROM atestados
            WHERE id = ?
        """, (
            id_atestado,
        ))

        resultado = cursor.fetchone()

        if not resultado:
            messagebox.showerror(
                "Erro",
                "Atestado não encontrado."
            )
            return

        nome, cpf, horas, status, dados, tipo_arquivo = resultado

        self.mostrar_atestado(
            id_atestado,
            {
                "nome": nome,
                "cpf": cpf,
                "horas_solicitadas": horas,
                "status": status,
            },
            dados,
            tipo_arquivo
        )

    # ==============================================================
    # CARREGAR IMAGEM (PDF OU IMAGEM)
    # ==============================================================

    def carregar_imagem(self, dados, tipo_arquivo):
        """Retorna um objeto PIL.Image ou levanta exceção."""

        dados = bytes(dados)

        if tipo_arquivo == "application/pdf":

            documento = pymupdf.open(
                stream=dados,
                filetype="pdf"
            )

            try:
                # Zoom 2x para ficar nítido após o thumbnail
                pix = documento[0].get_pixmap(
                    matrix=pymupdf.Matrix(2, 2)
                )

                imagem = Image.open(
                    io.BytesIO(pix.tobytes("png"))
                )
                imagem.load()

            finally:
                documento.close()

        elif tipo_arquivo.startswith("image/"):

            imagem = Image.open(
                io.BytesIO(dados)
            )

        else:
            raise ValueError(
                f"Tipo de arquivo não suportado: {tipo_arquivo}"
            )

        imagem = imagem.convert("RGB")
        imagem.thumbnail((700, 700))

        return imagem

    # ==============================================================
    # MOSTRAR ATESTADO + FORMULÁRIO EDITÁVEL
    # ==============================================================

    def mostrar_atestado(
        self,
        id_atestado,
        valores,
        dados,
        tipo_arquivo
    ):

        janela = tk.Toplevel(self.root)
        janela.title(f"Atestado #{id_atestado}")
        janela.transient(self.root)

        # ----------------------------------------------------------
        # LADO ESQUERDO: IMAGEM
        # ----------------------------------------------------------

        frame_imagem = ttk.Frame(janela)
        frame_imagem.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        try:
            imagem = self.carregar_imagem(dados, tipo_arquivo)
            imagem_tk = ImageTk.PhotoImage(imagem)

            label_imagem = ttk.Label(frame_imagem, image=imagem_tk)

            # Mantém referência da imagem
            label_imagem.image = imagem_tk

        except Exception as erro:
            label_imagem = ttk.Label(
                frame_imagem,
                text=f"Não foi possível exibir o arquivo:\n\n{erro}",
                justify="center",
                wraplength=300
            )

        label_imagem.pack()

        # ----------------------------------------------------------
        # LADO DIREITO: FORMULÁRIO
        # ----------------------------------------------------------

        frame_form = ttk.LabelFrame(janela, text="Dados do atestado")
        frame_form.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="n")

        def texto(valor):
            return "" if valor is None else str(valor)

        variaveis = {
            "nome": tk.StringVar(value=texto(valores["nome"])),
            "cpf": tk.StringVar(value=texto(valores["cpf"])),
            "horas_solicitadas": tk.StringVar(
                value=texto(valores["horas_solicitadas"])
            ),
            "status": tk.StringVar(value=texto(valores["status"])),
        }

        rotulos = [
            ("nome", "Nome"),
            ("cpf", "CPF"),
            ("horas_solicitadas", "Horas solicitadas"),
            ("status", "Status"),
        ]

        for linha, (chave, rotulo) in enumerate(rotulos):

            ttk.Label(
                frame_form,
                text=rotulo
            ).grid(row=linha, column=0, padx=10, pady=8, sticky="w")

            if chave == "status":

                # Se o status atual não estiver na lista, inclui
                opcoes = list(self.STATUS_SUGERIDOS)
                atual = variaveis["status"].get()

                if atual and atual not in opcoes:
                    opcoes.insert(0, atual)

                campo = ttk.Combobox(
                    frame_form,
                    textvariable=variaveis["status"],
                    values=opcoes,
                    width=38
                )

            else:

                campo = ttk.Entry(
                    frame_form,
                    textvariable=variaveis[chave],
                    width=40
                )

            campo.grid(row=linha, column=1, padx=10, pady=8)

        ttk.Button(
            frame_form,
            text="Salvar alterações",
            command=lambda: self.salvar_alteracoes(
                id_atestado,
                variaveis,
                janela
            )
        ).grid(row=len(rotulos), column=0, columnspan=2, pady=15)

    # ==============================================================
    # SALVAR ALTERAÇÕES
    # ==============================================================

    def salvar_alteracoes(self, id_atestado, variaveis, janela):

        nome = variaveis["nome"].get().strip()
        cpf = variaveis["cpf"].get().strip()
        horas_texto = variaveis["horas_solicitadas"].get().strip()
        status = variaveis["status"].get().strip()

        # Campos obrigatórios (NOT NULL no banco)
        if not nome or not cpf or not status:
            messagebox.showwarning(
                "Campos obrigatórios",
                "Nome, CPF e Status não podem ficar vazios.",
                parent=janela
            )
            return

        # Horas: vazio -> NULL, senão precisa ser inteiro
        if horas_texto == "":
            horas = None

        else:
            try:
                horas = int(horas_texto)

            except ValueError:
                messagebox.showwarning(
                    "Horas inválidas",
                    "Informe as horas solicitadas como um número inteiro "
                    "ou deixe o campo vazio.",
                    parent=janela
                )
                return

        try:
            with self.conexao:  # commit automático / rollback em erro
                self.conexao.execute("""
                    UPDATE atestados
                    SET nome = ?,
                        cpf = ?,
                        horas_solicitadas = ?,
                        status = ?
                    WHERE id = ?
                """, (
                    nome,
                    cpf,
                    horas,
                    status,
                    id_atestado
                ))

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível salvar as alterações:\n\n{erro}",
                parent=janela
            )
            return

        self.carregar_atestados()

        messagebox.showinfo(
            "Sucesso",
            "Alterações salvas.",
            parent=janela
        )

    # ==============================================================
    # FECHAR
    # ==============================================================

    def fechar(self):

        self.conexao.close()

        self.root.destroy()


# ==============================================================
# INICIALIZAÇÃO
# ==============================================================

root = tk.Tk()

app = Aplicacao(root)

root.protocol(
    "WM_DELETE_WINDOW",
    app.fechar
)

root.mainloop()