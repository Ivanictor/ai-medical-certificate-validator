import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk


class Aplicacao:

    def __init__(self, root):

        self.root = root
        self.root.title("Gerenciador de Atestados")
        self.root.geometry("800x500")

        # Guarda as imagens para evitar que sejam destruídas pelo Python
        self.imagens = {}

        # Botão para adicionar arquivo
        ttk.Button(
            root,
            text="Adicionar atestado",
            command=self.adicionar_arquivo
        ).pack(pady=10)

        # Tabela
        self.tabela = ttk.Treeview(
            root,
            columns=("nome", "status"),
            show="headings"
        )

        self.tabela.heading("nome", text="Atestado")
        self.tabela.heading("status", text="Status")

        self.tabela.column("nome", width=500)
        self.tabela.column("status", width=150)

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

        nome = caminho.split("/")[-1]

        self.tabela.insert(
            "",
            "end",
            values=(nome, "Pendente"),
            tags=(caminho,)
        )

    def visualizar_atestado(self, event):

        item = self.tabela.selection()

        if not item:
            return

        item = item[0]

        caminho = self.tabela.item(
            item,
            "tags"
        )[0]

        self.mostrar_imagem(caminho)

    def mostrar_imagem(self, caminho):

        janela = tk.Toplevel(self.root)

        janela.title("Visualizar atestado")

        imagem = Image.open(caminho)

        imagem.thumbnail((800, 800))

        imagem_tk = ImageTk.PhotoImage(imagem)

        label = ttk.Label(
            janela,
            image=imagem_tk
        )

        label.image = imagem_tk

        label.pack(
            padx=10,
            pady=10
        )


root = tk.Tk()

app = Aplicacao(root)

root.mainloop()