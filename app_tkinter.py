import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import sqlite3
import io
import fitz


class Aplicacao:

    def __init__(self, root):

        self.root = root
        self.root.title("Gerenciador de Atestados")
        self.root.geometry("1100x500")

        # Conexão com o banco
        self.conexao = sqlite3.connect("atestados.db")

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

        self.tabela.heading(
            "id",
            text="ID"
        )

        self.tabela.heading(
            "nome",
            text="Nome"
        )

        self.tabela.heading(
            "cpf",
            text="CPF"
        )

        self.tabela.heading(
            "email",
            text="Email"
        )

        self.tabela.heading(
            "horas",
            text="Horas solicitadas"
        )

        self.tabela.heading(
            "status",
            text="Status"
        )

        self.tabela.heading(
            "data",
            text="Data de cadastro"
        )

        # Larguras
        self.tabela.column(
            "id",
            width=50
        )

        self.tabela.column(
            "nome",
            width=220
        )

        self.tabela.column(
            "cpf",
            width=120
        )

        self.tabela.column(
            "email",
            width=220
        )

        self.tabela.column(
            "horas",
            width=130
        )

        self.tabela.column(
            "status",
            width=120
        )

        self.tabela.column(
            "data",
            width=150
        )

        self.tabela.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        # Duplo clique para visualizar
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

        registros = cursor.fetchall()

        for registro in registros:

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
                (
                    "Imagens",
                    "*.jpg *.jpeg *.png"
                ),
                (
                    "PDF",
                    "*.pdf"
                ),
                (
                    "Todos os arquivos",
                    "*.*"
                )
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

        elif caminho_lower.endswith(".jpg") or caminho_lower.endswith(".jpeg"):

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
        # DADOS TEMPORÁRIOS
        # ==========================================================
        #
        # Como esse botão é apenas para teste, usamos valores
        # temporários.
        #
        # No fluxo real, esses valores virão do OCR/LLM.
        # ==========================================================

        nome = "Paciente de teste"
        cpf = "00000000000"
        email = "teste@email.com"
        horas_solicitadas = None
        status = "Pendente"

        # ==========================================================
        # INSERE NO BANCO
        # ==========================================================

        cursor = self.conexao.cursor()

        cursor.execute("""
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

        self.conexao.commit()

        # Atualiza a tabela
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

        cursor = self.conexao.cursor()

        cursor.execute("""
            SELECT
                nome,
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

        nome, dados, tipo_arquivo = resultado

        self.mostrar_atestado(
            nome,
            dados,
            tipo_arquivo
        )

    # ==============================================================
    # MOSTRAR ATESTADO
    # ==============================================================

    def mostrar_atestado(
        self,
        nome,
        dados,
        tipo_arquivo
    ):

        # ==========================================================
        # PDF
        # ==========================================================

        if tipo_arquivo == "application/pdf":

            try:

                documento = fitz.open(
                    stream=dados,
                    filetype="pdf"
                )

                pagina = documento[0]

                pix = pagina.get_pixmap()

                imagem = Image.open(
                    io.BytesIO(
                        pix.tobytes("png")
                    )
                )

                documento.close()

            except Exception as erro:

                messagebox.showerror(
                    "Erro",
                    f"Não foi possível abrir o PDF:\n\n{erro}"
                )

                return

        # ==========================================================
        # IMAGEM
        # ==========================================================

        elif tipo_arquivo.startswith("image/"):

            try:

                imagem = Image.open(
                    io.BytesIO(dados)
                )

            except Exception as erro:

                messagebox.showerror(
                    "Erro",
                    f"Não foi possível abrir a imagem:\n\n{erro}"
                )

                return

        # ==========================================================
        # TIPO NÃO SUPORTADO
        # ==========================================================

        else:

            messagebox.showerror(
                "Erro",
                f"Tipo de arquivo não suportado:\n{tipo_arquivo}"
            )

            return

        # ==========================================================
        # REDIMENSIONAMENTO
        # ==========================================================

        imagem.thumbnail(
            (800, 800)
        )

        imagem_tk = ImageTk.PhotoImage(
            imagem
        )

        # ==========================================================
        # JANELA
        # ==========================================================

        janela = tk.Toplevel(
            self.root
        )

        janela.title(
            f"Atestado - {nome}"
        )

        label = ttk.Label(
            janela,
            image=imagem_tk
        )

        # Mantém referência da imagem
        label.image = imagem_tk

        label.pack(
            padx=10,
            pady=10
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

