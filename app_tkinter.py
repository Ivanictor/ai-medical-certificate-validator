import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from datetime import datetime, date
import sqlite3
import unicodedata
import io
import pymupdf


# ==================================================================
# FUNÇÕES AUXILIARES 
# ==================================================================

def normalizar(texto):
    """Minúsculas e sem acentos, para buscar 'joao' e achar 'João'."""

    if texto is None:
        return ""

    decomposto = unicodedata.normalize("NFKD", str(texto))

    return "".join(
        c for c in decomposto
        if not unicodedata.combining(c)
    ).casefold()


def somente_digitos(texto):
    """Mantém só os números, para o CPF casar com ou sem pontuação."""

    return "".join(c for c in str(texto or "") if c.isdigit())


def escapar_like(texto):
    """Escapa os curingas do LIKE para o termo ser buscado literalmente."""

    return (
        texto
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def data_br_para_iso(texto):
    """'25/12/2026' -> '2026-12-25'. Levanta ValueError se for inválida."""

    return datetime.strptime(texto, "%d/%m/%Y").strftime("%Y-%m-%d")


def data_iso_para_br(texto):
    """'2026-12-25' -> '25/12/2026'.

    Valores vazios viram ''. Se o valor não estiver no formato ISO
    (dado antigo ou digitado à mão), ele é devolvido como está."""

    if not texto:
        return ""

    try:
        return datetime.strptime(str(texto), "%Y-%m-%d").strftime("%d/%m/%Y")

    except ValueError:
        return str(texto)


class Aplicacao:

    STATUS_SUGERIDOS = [
        "Pendente",
        "Processado",
        "Não processado",
        "Nome não reconhecido pelo Llama",
        "Rejeitado"
    ]

    OPCAO_TODOS = "Todos"

    # Tempo (ms) de espera após a digitação antes de aplicar o filtro
    ATRASO_FILTRO_MS = 250

    # Colunas de texto adicionadas ao esquema do banco (usadas na migração)
    COLUNAS_NOVAS = (
        "medico",
        "crm",
        "cid",
        "data_inicio",
        "data_emissao",
    )

    def __init__(self, root):

        self.root = root
        self.root.title("Gerenciador de Atestados")
        self.root.geometry("1300x620")

        # Conexão com o banco (timeout evita "database is locked"
        # se o monitor de e-mail estiver gravando ao mesmo tempo)
        self.conexao = sqlite3.connect("atestados.db", timeout=30)

        # Funções usadas pelos filtros dentro das consultas SQL
        self.conexao.create_function("normalizar", 1, normalizar)
        self.conexao.create_function("somente_digitos", 1, somente_digitos)

        self._filtro_pendente = None

        self.criar_banco()

        # ==========================================================
        # BOTÕES
        # ==========================================================

        frame_botoes = ttk.Frame(root)
        frame_botoes.pack(pady=10)

        ttk.Button(
            frame_botoes,
            text="Adicionar atestado",
            command=self.adicionar_arquivo
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botoes,
            text="Marcar como analisado",
            command=lambda: self.alterar_analisado(1)
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botoes,
            text="Marcar como não analisado",
            command=lambda: self.alterar_analisado(0)
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botoes,
            text="Excluir selecionado(s)",
            command=self.excluir_selecionados
        ).pack(side="left", padx=5)

        # ==========================================================
        # FILTROS
        # ==========================================================

        self.criar_filtros()

        # ==========================================================
        # TABELA
        # ==========================================================

        frame_tabela = ttk.Frame(root)
        frame_tabela.pack(fill="both", expand=True, padx=10, pady=10)

        self.tabela = ttk.Treeview(
            frame_tabela,
            columns=(
                "id",
                "nome",
                "cpf",
                "email",
                "horas",
                "medico",
                "crm",
                "cid",
                "data_inicio",
                "data_emissao",
                "status",
                "analisado",
                "data"
            ),
            show="headings"
        )

        self.tabela.heading("id", text="ID")
        self.tabela.heading("nome", text="Nome")
        self.tabela.heading("cpf", text="CPF")
        self.tabela.heading("email", text="Email")
        self.tabela.heading("horas", text="Horas solicitadas")
        self.tabela.heading("medico", text="Médico")
        self.tabela.heading("crm", text="CRM")
        self.tabela.heading("cid", text="CID")
        self.tabela.heading("data_inicio", text="Início do afastamento")
        self.tabela.heading("data_emissao", text="Data de emissão")
        self.tabela.heading("status", text="Status")
        self.tabela.heading("analisado", text="Analisado")
        self.tabela.heading("data", text="Data de cadastro")

        # Larguras: (largura, âncora, estica?)
        # minwidth = largura, para a barra de rolagem horizontal aparecer
        # quando a janela ficar menor que a soma das colunas.
        larguras = {
            "id": (50, "w", False),
            "nome": (180, "w", True),
            "cpf": (105, "w", False),
            "email": (180, "w", True),
            "horas": (115, "w", False),
            "medico": (170, "w", True),
            "crm": (80, "w", False),
            "cid": (70, "w", False),
            "data_inicio": (130, "w", False),
            "data_emissao": (110, "w", False),
            "status": (200, "w", False),
            "analisado": (75, "center", False),
            "data": (140, "w", False),
        }

        for coluna, (largura, ancora, estica) in larguras.items():
            self.tabela.column(
                coluna,
                width=largura,
                minwidth=largura,
                anchor=ancora,
                stretch=estica
            )

        self.tabela.tag_configure(
            "analisado",
            foreground="#9a9a9a"
        )

        scroll_y = ttk.Scrollbar(
            frame_tabela,
            orient="vertical",
            command=self.tabela.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_tabela,
            orient="horizontal",
            command=self.tabela.xview
        )

        self.tabela.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )

        self.tabela.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        frame_tabela.rowconfigure(0, weight=1)
        frame_tabela.columnconfigure(0, weight=1)

        # Duplo clique para visualizar/editar
        self.tabela.bind(
            "<Double-1>",
            self.visualizar_atestado
        )

        # Tecla Delete exclui os itens selecionados
        self.tabela.bind(
            "<Delete>",
            lambda event: self.excluir_selecionados()
        )

        # Os filtros só passam a reagir depois que a tabela existe
        self.ativar_filtros()

        # Carrega os registros existentes
        self.carregar_atestados()

    # ==============================================================
    # BANCO DE DADOS
    # ==============================================================

    def criar_banco(self):
        """Mesmo esquema criado pelo enviar_dados_banco, incluindo
        médico, CRM, CID, datas de início e emissão e a coluna
        "analisado" (0 = não analisado, 1 = analisado).

        As datas de início e emissão são gravadas em formato ISO
        (AAAA-MM-DD); a interface as exibe como DD/MM/AAAA."""

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
                medico TEXT NOT NULL,
                crm TEXT NOT NULL,
                cid TEXT NOT NULL,
                data_inicio TEXT,
                data_emissao TEXT,
                status TEXT NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analisado INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Migração: bancos criados antes desta versão não têm algumas
        # colunas. O CREATE TABLE IF NOT EXISTS não altera tabelas
        # existentes, então as colunas que faltam são adicionadas aqui.
        # Os registros antigos ficam com texto vazio nos campos novos
        # (DEFAULT '') e como "não analisado" (DEFAULT 0).
        colunas = [
            linha[1]
            for linha in cursor.execute("PRAGMA table_info(atestados)")
        ]

        if "analisado" not in colunas:
            cursor.execute("""
                ALTER TABLE atestados
                ADD COLUMN analisado INTEGER NOT NULL DEFAULT 0
            """)

        for coluna in self.COLUNAS_NOVAS:
            if coluna not in colunas:
                cursor.execute(f"""
                    ALTER TABLE atestados
                    ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''
                """)

        self.conexao.commit()

    # ==============================================================
    # FILTROS
    # ==============================================================

    def criar_filtros(self):
        """Cria a barra de filtros (as variáveis e os campos)."""

        self.var_filtro_nome = tk.StringVar()
        self.var_filtro_cpf = tk.StringVar()
        self.var_filtro_status = tk.StringVar(value=self.OPCAO_TODOS)
        self.var_filtro_analisado = tk.StringVar(value=self.OPCAO_TODOS)
        self.var_filtro_data_de = tk.StringVar()
        self.var_filtro_data_ate = tk.StringVar()

        frame = ttk.LabelFrame(self.root, text="Filtros")
        frame.pack(fill="x", padx=10)

        # ----------------------------------------------------------
        # Linha 0: nome, CPF, status e analisado
        # ----------------------------------------------------------

        ttk.Label(frame, text="Nome").grid(
            row=0, column=0, padx=(10, 4), pady=6, sticky="w"
        )
        ttk.Entry(
            frame,
            textvariable=self.var_filtro_nome,
            width=26
        ).grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        ttk.Label(frame, text="CPF").grid(
            row=0, column=2, padx=(0, 4), pady=6, sticky="w"
        )
        ttk.Entry(
            frame,
            textvariable=self.var_filtro_cpf,
            width=16
        ).grid(row=0, column=3, padx=(0, 12), pady=6, sticky="w")

        ttk.Label(frame, text="Status").grid(
            row=0, column=4, padx=(0, 4), pady=6, sticky="w"
        )
        self.combo_status = ttk.Combobox(
            frame,
            textvariable=self.var_filtro_status,
            values=[self.OPCAO_TODOS] + self.STATUS_SUGERIDOS,
            state="readonly",
            width=30
        )
        self.combo_status.grid(
            row=0, column=5, padx=(0, 12), pady=6, sticky="w"
        )

        ttk.Label(frame, text="Analisado").grid(
            row=0, column=6, padx=(0, 4), pady=6, sticky="w"
        )
        ttk.Combobox(
            frame,
            textvariable=self.var_filtro_analisado,
            values=[self.OPCAO_TODOS, "Sim", "Não"],
            state="readonly",
            width=8
        ).grid(row=0, column=7, padx=(0, 10), pady=6, sticky="w")

        # ----------------------------------------------------------
        # Linha 1: intervalo da data de cadastro e limpar filtros
        # ----------------------------------------------------------

        ttk.Label(frame, text="Cadastro de").grid(
            row=1, column=0, padx=(10, 4), pady=6, sticky="w"
        )
        ttk.Entry(
            frame,
            textvariable=self.var_filtro_data_de,
            width=14
        ).grid(row=1, column=1, padx=(0, 12), pady=6, sticky="w")

        ttk.Label(frame, text="até").grid(
            row=1, column=2, padx=(0, 4), pady=6, sticky="w"
        )
        ttk.Entry(
            frame,
            textvariable=self.var_filtro_data_ate,
            width=14
        ).grid(row=1, column=3, padx=(0, 12), pady=6, sticky="w")

        ttk.Label(
            frame,
            text="(formato DD/MM/AAAA)",
            foreground="#777777"
        ).grid(row=1, column=4, columnspan=2, pady=6, sticky="w")

        ttk.Button(
            frame,
            text="Limpar filtros",
            command=self.limpar_filtros
        ).grid(row=1, column=6, columnspan=2, padx=(0, 10), pady=6, sticky="e")

        # ----------------------------------------------------------
        # Linha 2: resultado / avisos
        # ----------------------------------------------------------

        self.label_resultado = ttk.Label(
            frame,
            text="",
            foreground="#555555"
        )
        self.label_resultado.grid(
            row=2, column=0, columnspan=8, padx=10, pady=(0, 6), sticky="w"
        )

    def ativar_filtros(self):
        """Faz a tabela ser atualizada sempre que um filtro mudar."""

        variaveis = (
            self.var_filtro_nome,
            self.var_filtro_cpf,
            self.var_filtro_status,
            self.var_filtro_analisado,
            self.var_filtro_data_de,
            self.var_filtro_data_ate,
        )

        for variavel in variaveis:
            variavel.trace_add("write", self.agendar_filtro)

    def agendar_filtro(self, *args):
        """Espera um instante após a digitação para não recarregar a
        tabela a cada tecla."""

        if self._filtro_pendente is not None:
            self.root.after_cancel(self._filtro_pendente)

        self._filtro_pendente = self.root.after(
            self.ATRASO_FILTRO_MS,
            self.executar_filtro
        )

    def executar_filtro(self):

        self._filtro_pendente = None
        self.carregar_atestados()

    def limpar_filtros(self):

        self.var_filtro_nome.set("")
        self.var_filtro_cpf.set("")
        self.var_filtro_status.set(self.OPCAO_TODOS)
        self.var_filtro_analisado.set(self.OPCAO_TODOS)
        self.var_filtro_data_de.set("")
        self.var_filtro_data_ate.set("")

    def atualizar_opcoes_status(self):
        """Lista de status do filtro: os sugeridos mais qualquer outro
        valor que exista no banco (por exemplo, digitado à mão)."""

        cursor = self.conexao.cursor()

        cursor.execute("SELECT DISTINCT status FROM atestados ORDER BY status")

        extras = [
            linha[0]
            for linha in cursor.fetchall()
            if linha[0] not in self.STATUS_SUGERIDOS
        ]

        self.combo_status["values"] = (
            [self.OPCAO_TODOS] + self.STATUS_SUGERIDOS + extras
        )

    def montar_filtros(self):
        """Converte o estado dos filtros em condições SQL.

        Retorna (condicoes, parametros, avisos)."""

        condicoes = []
        parametros = []
        avisos = []

        # Nome: contém o termo (sem diferenciar maiúsculas e acentos)
        nome = self.var_filtro_nome.get().strip()

        if nome:
            condicoes.append("normalizar(nome) LIKE ? ESCAPE '\\'")
            parametros.append(f"%{escapar_like(normalizar(nome))}%")

        # CPF: contém os dígitos digitados (com ou sem pontuação)
        cpf = self.var_filtro_cpf.get().strip()

        if cpf:
            digitos = somente_digitos(cpf)

            if digitos:
                condicoes.append("somente_digitos(cpf) LIKE ?")
                parametros.append(f"%{digitos}%")

            else:
                # CPF não tem letras: nada pode casar
                condicoes.append("1 = 0")

        # Status: valor exato escolhido na lista
        status = self.var_filtro_status.get()

        if status and status != self.OPCAO_TODOS:
            condicoes.append("status = ?")
            parametros.append(status)

        # Analisado: Sim / Não
        analisado = self.var_filtro_analisado.get()

        if analisado == "Sim":
            condicoes.append("analisado = 1")

        elif analisado == "Não":
            condicoes.append("analisado = 0")

        # Data de cadastro: intervalo (início e fim inclusos)
        data_de = self.var_filtro_data_de.get().strip()
        data_ate = self.var_filtro_data_ate.get().strip()

        if data_de:
            try:
                condicoes.append("date(data_cadastro) >= ?")
                parametros.append(data_br_para_iso(data_de))

            except ValueError:
                condicoes.pop()
                avisos.append("Data inicial inválida (use DD/MM/AAAA).")

        if data_ate:
            try:
                condicoes.append("date(data_cadastro) <= ?")
                parametros.append(data_br_para_iso(data_ate))

            except ValueError:
                condicoes.pop()
                avisos.append("Data final inválida (use DD/MM/AAAA).")

        if (
            data_de and data_ate
            and not avisos
            and data_br_para_iso(data_de) > data_br_para_iso(data_ate)
        ):
            avisos.append("A data inicial é posterior à data final.")

        return condicoes, parametros, avisos

    # ==============================================================
    # CARREGAR REGISTROS
    # ==============================================================

    def carregar_atestados(self):
        """Recarrega a tabela respeitando os filtros atuais."""

        self.atualizar_opcoes_status()

        # Limpa a tabela
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        condicoes, parametros, avisos = self.montar_filtros()

        consulta = """
            SELECT
                id,
                nome,
                cpf,
                email,
                horas_solicitadas,
                medico,
                crm,
                cid,
                data_inicio,
                data_emissao,
                status,
                analisado,
                data_cadastro
            FROM atestados
        """

        if condicoes:
            consulta += " WHERE " + " AND ".join(condicoes)

        consulta += " ORDER BY id DESC"

        cursor = self.conexao.cursor()

        cursor.execute(consulta, parametros)

        registros = cursor.fetchall()

        for (
            id_atestado,
            nome,
            cpf,
            email,
            horas,
            medico,
            crm,
            cid,
            data_inicio,
            data_emissao,
            status,
            analisado,
            data_cadastro,
        ) in registros:

            valores = (
                id_atestado,
                nome,
                cpf,
                email,
                "" if horas is None else horas,
                medico,
                crm,
                cid,
                data_iso_para_br(data_inicio),
                data_iso_para_br(data_emissao),
                status,
                "Sim" if analisado == 1 else "Não",
                data_cadastro,
            )

            tags = ("analisado",) if analisado == 1 else ()

            self.tabela.insert(
                "",
                "end",
                values=valores,
                tags=tags
            )

        # Resumo (ou aviso de data inválida) abaixo dos filtros
        total = cursor.execute(
            "SELECT COUNT(*) FROM atestados"
        ).fetchone()[0]

        if avisos:
            self.label_resultado.configure(
                text="  ".join(avisos),
                foreground="#b00020"
            )

        else:
            self.label_resultado.configure(
                text=f"Exibindo {len(registros)} de {total} atestado(s).",
                foreground="#555555"
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
        medico = "Médico de teste"
        crm = "00000"
        cid = "Z00"
        data_inicio = date.today().isoformat()
        data_emissao = date.today().isoformat()
        status = "Pendente"

        # ==========================================================
        # INSERE NO BANCO
        # (analisado não é informado: o DEFAULT 0 cuida disso)
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
                        medico,
                        crm,
                        cid,
                        data_inicio,
                        data_emissao,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nome,
                    cpf,
                    email,
                    sqlite3.Binary(dados),
                    tipo_arquivo,
                    horas_solicitadas,
                    medico,
                    crm,
                    cid,
                    data_inicio,
                    data_emissao,
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
    # MARCAR / DESMARCAR COMO ANALISADO
    # ==============================================================

    def alterar_analisado(self, valor):
        """Define analisado = valor (1 ou 0) nos atestados selecionados."""

        selecao = self.tabela.selection()

        if not selecao:
            messagebox.showinfo(
                "Analisado",
                "Selecione ao menos um atestado na tabela."
            )
            return

        ids = [str(self.tabela.item(item, "values")[0]) for item in selecao]

        try:
            with self.conexao:  # commit automático / rollback em erro
                self.conexao.executemany(
                    "UPDATE atestados SET analisado = ? WHERE id = ?",
                    [(valor, id_atestado) for id_atestado in ids]
                )

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível atualizar os atestados:\n\n{erro}"
            )
            return

        self.carregar_atestados()

        # Mantém a seleção para facilitar ajustes seguidos
        # (registros que saíram do filtro simplesmente não aparecem)
        for item in self.tabela.get_children():
            if str(self.tabela.item(item, "values")[0]) in ids:
                self.tabela.selection_add(item)

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
        # que o Tk converta CPF/CRM em número e perca zeros à esquerda.
        cursor = self.conexao.cursor()

        cursor.execute("""
            SELECT
                nome,
                cpf,
                horas_solicitadas,
                medico,
                crm,
                cid,
                data_inicio,
                data_emissao,
                status,
                analisado,
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

        (
            nome,
            cpf,
            horas,
            medico,
            crm,
            cid,
            data_inicio,
            data_emissao,
            status,
            analisado,
            dados,
            tipo_arquivo,
        ) = resultado

        self.mostrar_atestado(
            id_atestado,
            {
                "nome": nome,
                "cpf": cpf,
                "horas_solicitadas": horas,
                "medico": medico,
                "crm": crm,
                "cid": cid,
                "data_inicio": data_iso_para_br(data_inicio),
                "data_emissao": data_iso_para_br(data_emissao),
                "status": status,
                "analisado": analisado,
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
            "medico": tk.StringVar(value=texto(valores["medico"])),
            "crm": tk.StringVar(value=texto(valores["crm"])),
            "cid": tk.StringVar(value=texto(valores["cid"])),
            "data_inicio": tk.StringVar(
                value=texto(valores["data_inicio"])
            ),
            "data_emissao": tk.StringVar(
                value=texto(valores["data_emissao"])
            ),
            "status": tk.StringVar(value=texto(valores["status"])),
            "analisado": tk.IntVar(value=1 if valores["analisado"] else 0),
        }

        rotulos = [
            ("nome", "Nome"),
            ("cpf", "CPF"),
            ("horas_solicitadas", "Horas solicitadas"),
            ("medico", "Médico"),
            ("crm", "CRM"),
            ("cid", "CID"),
            ("data_inicio", "Início do afastamento\n(DD/MM/AAAA)"),
            ("data_emissao", "Data de emissão\n(DD/MM/AAAA)"),
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

        # Caixa de seleção "Analisado" (gravada junto com as alterações)
        ttk.Checkbutton(
            frame_form,
            text="Analisado",
            variable=variaveis["analisado"],
            onvalue=1,
            offvalue=0
        ).grid(
            row=len(rotulos),
            column=0,
            columnspan=2,
            padx=10,
            pady=8,
            sticky="w"
        )

        ttk.Button(
            frame_form,
            text="Salvar alterações",
            command=lambda: self.salvar_alteracoes(
                id_atestado,
                variaveis,
                janela
            )
        ).grid(row=len(rotulos) + 1, column=0, columnspan=2, pady=15)

        ttk.Button(
            frame_form,
            text="Excluir atestado",
            command=lambda: self.excluir_da_janela(
                id_atestado,
                janela
            )
        ).grid(row=len(rotulos) + 2, column=0, columnspan=2, pady=(0, 15))

    # ==============================================================
    # SALVAR ALTERAÇÕES
    # ==============================================================

    def salvar_alteracoes(self, id_atestado, variaveis, janela):

        nome = variaveis["nome"].get().strip()
        cpf = variaveis["cpf"].get().strip()
        horas_texto = variaveis["horas_solicitadas"].get().strip()
        medico = variaveis["medico"].get().strip()
        crm = variaveis["crm"].get().strip()
        cid = variaveis["cid"].get().strip()
        data_inicio_texto = variaveis["data_inicio"].get().strip()
        data_emissao_texto = variaveis["data_emissao"].get().strip()
        status = variaveis["status"].get().strip()
        analisado = 1 if variaveis["analisado"].get() else 0

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

        # Datas: vazio -> '' (registros antigos não têm esses dados),
        # senão precisam estar em DD/MM/AAAA e são gravadas em ISO.
        datas_iso = {}

        for rotulo, texto_data in (
            ("Início do afastamento", data_inicio_texto),
            ("Data de emissão", data_emissao_texto),
        ):
            if texto_data == "":
                datas_iso[rotulo] = ""
                continue

            try:
                datas_iso[rotulo] = data_br_para_iso(texto_data)

            except ValueError:
                messagebox.showwarning(
                    "Data inválida",
                    f"{rotulo}: use o formato DD/MM/AAAA "
                    "ou deixe o campo vazio.",
                    parent=janela
                )
                return

        data_inicio = datas_iso["Início do afastamento"]
        data_emissao = datas_iso["Data de emissão"]

        try:
            with self.conexao:  # commit automático / rollback em erro
                self.conexao.execute("""
                    UPDATE atestados
                    SET nome = ?,
                        cpf = ?,
                        horas_solicitadas = ?,
                        medico = ?,
                        crm = ?,
                        cid = ?,
                        data_inicio = ?,
                        data_emissao = ?,
                        status = ?,
                        analisado = ?
                    WHERE id = ?
                """, (
                    nome,
                    cpf,
                    horas,
                    medico,
                    crm,
                    cid,
                    data_inicio,
                    data_emissao,
                    status,
                    analisado,
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
    # EXCLUIR ATESTADOS
    # ==============================================================

    def excluir_selecionados(self):
        """Exclui da tabela principal os atestados selecionados."""

        selecao = self.tabela.selection()

        if not selecao:
            messagebox.showinfo(
                "Excluir",
                "Selecione ao menos um atestado na tabela."
            )
            return

        ids = [self.tabela.item(item, "values")[0] for item in selecao]

        if len(ids) == 1:
            mensagem = (
                f"Excluir o atestado #{ids[0]}?\n\n"
                "Esta ação não pode ser desfeita."
            )
        else:
            mensagem = (
                f"Excluir {len(ids)} atestados selecionados?\n\n"
                "Esta ação não pode ser desfeita."
            )

        if not messagebox.askyesno(
            "Confirmar exclusão",
            mensagem,
            icon="warning",
            default="no"
        ):
            return

        self.excluir_por_ids(ids)

    def excluir_por_ids(self, ids, parent=None):
        """Apaga os registros do banco. Retorna True se deu certo."""

        try:
            with self.conexao:  # commit automático / rollback em erro
                self.conexao.executemany(
                    "DELETE FROM atestados WHERE id = ?",
                    [(id_atestado,) for id_atestado in ids]
                )

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível excluir:\n\n{erro}",
                parent=parent
            )
            return False

        self.carregar_atestados()
        return True

    def excluir_da_janela(self, id_atestado, janela):
        """Exclui o atestado aberto na janela de detalhes."""

        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Excluir o atestado #{id_atestado}?\n\n"
            "Esta ação não pode ser desfeita.",
            icon="warning",
            default="no",
            parent=janela
        ):
            return

        if self.excluir_por_ids([id_atestado], parent=janela):
            janela.destroy()

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