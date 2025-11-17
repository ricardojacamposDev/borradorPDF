"""Tkinter-based UI for blurring rectangular areas in PDF pages."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

try:
    import fitz
except ModuleNotFoundError as exc:  # pragma: no cover - environment issue
    raise ImportError(
        "O módulo 'fitz' não foi encontrado. Instale PyMuPDF dentro do ambiente "
        "virtual do projeto (pip install -r requirements.txt) antes de executar o app."
    ) from exc
except Exception as exc:  # pragma: no cover - captura pacote errado
    raise ImportError(
        "Um pacote 'fitz' incompatível foi encontrado. Remova-o com 'pip uninstall fitz' "
        "e instale PyMuPDF (fornecido em requirements.txt) dentro do ambiente virtual."
    ) from exc

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .processing import Rect, blur_region

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 10 fallback
    RESAMPLE = Image.LANCZOS

CanvasRect = Tuple[float, float, float, float]


class PdfBlurApp:
    """Interactive desktop application for selecting and blurring PDF regions."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Borrador de PDF com Desfoque")
        self.root.geometry("1024x768")

        self.doc: Optional[fitz.Document] = None
        self.doc_path: Optional[Path] = None
        self.current_page_index: int = 0
        self.page_images: Dict[int, Image.Image] = {}
        self.modified_pages: Set[int] = set()
        self.zoom: float = 2.0
        self.display_scale: float = 1.0
        self.image_offset: Tuple[float, float] = (0.0, 0.0)
        self.selection_start: Optional[Tuple[float, float]] = None
        self.selection_rect_id: Optional[int] = None
        self.selection_coords: Optional[CanvasRect] = None
        self.canvas_image_id: Optional[int] = None
        self.display_image: Optional[Image.Image] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None

        self.blur_radius = tk.DoubleVar(value=12.0)
        self.status_var = tk.StringVar(value="Abra um PDF para começar")

        self._build_layout()

    # ------------------------------------------------------------------ UI ----
    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(12, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Abrir PDF", command=self.open_pdf).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Página anterior", command=self.go_prev_page).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Próxima página", command=self.go_next_page).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Label(toolbar, text="Raio do desfoque").pack(side=tk.LEFT)
        radius_slider = ttk.Scale(
            toolbar,
            from_=2,
            to=40,
            variable=self.blur_radius,
            command=lambda _=None: self._update_radius_label(),
        )
        radius_slider.pack(side=tk.LEFT, padx=(4, 0))
        self.radius_label = ttk.Label(toolbar, text=f"{self.blur_radius.get():.0f}px")
        self.radius_label.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Button(toolbar, text="Aplicar desfoque", command=self.apply_blur).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Salvar PDF...", command=self.save_pdf).pack(side=tk.LEFT, padx=(8, 0))

        self.canvas = tk.Canvas(self.root, background="#1e1e1e")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.canvas.update_idletasks()

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, padding=(12, 6))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _update_radius_label(self) -> None:
        self.radius_label.configure(text=f"{self.blur_radius.get():.0f}px")

    # ----------------------------------------------------------- File actions ----
    def open_pdf(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Arquivos PDF", "*.pdf")])
        if not file_path:
            return

        if self.doc is not None:
            self.doc.close()

        self.doc = fitz.open(file_path)
        self.doc_path = Path(file_path)
        self.current_page_index = 0
        self.page_images.clear()
        self.modified_pages.clear()
        self.status_var.set(
            f"{self.doc_path.name} — {self.doc.page_count} páginas"
        )
        self._ensure_page_image(self.current_page_index)
        self._render_current_page()

    def save_pdf(self) -> None:
        if not self.doc:
            messagebox.showinfo("Nenhum PDF", "Abra um arquivo antes de salvar.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Arquivos PDF", "*.pdf")],
            initialfile=(self.doc_path.name if self.doc_path else "saida.pdf"),
        )
        if not save_path:
            return

        for page_index in self.modified_pages:
            page = self.doc[page_index]
            image = self.page_images[page_index]
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            page.clean_contents()
            page.insert_image(page.rect, stream=buffer.getvalue())

        self.doc.save(save_path)
        messagebox.showinfo("PDF salvo", f"Arquivo gravado em\n{save_path}")
        self.status_var.set(f"Arquivo salvo: {save_path}")

    # ----------------------------------------------------------- Navigation ----
    def go_prev_page(self) -> None:
        if not self.doc:
            return
        if self.current_page_index == 0:
            return
        self.current_page_index -= 1
        self._ensure_page_image(self.current_page_index)
        self._render_current_page()

    def go_next_page(self) -> None:
        if not self.doc:
            return
        if self.current_page_index >= self.doc.page_count - 1:
            return
        self.current_page_index += 1
        self._ensure_page_image(self.current_page_index)
        self._render_current_page()

    # ------------------------------------------------------------ Rendering ----
    def _ensure_page_image(self, page_index: int) -> None:
        if page_index in self.page_images:
            return
        assert self.doc is not None
        page = self.doc[page_index]
        matrix = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.page_images[page_index] = image

    def _render_current_page(self) -> None:
        if not self.doc:
            return

        image = self.page_images[self.current_page_index]
        canvas_width = max(self.canvas.winfo_width(), 100)
        canvas_height = max(self.canvas.winfo_height(), 100)
        scale = min(canvas_width / image.width, canvas_height / image.height, 1.0)
        if scale <= 0:
            scale = 1.0
        self.display_scale = scale
        display_size = (
            int(image.width * scale),
            int(image.height * scale),
        )
        self.display_image = image.resize(display_size, RESAMPLE)
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        offset_x = (canvas_width - display_size[0]) / 2
        offset_y = (canvas_height - display_size[1]) / 2
        self.image_offset = (offset_x, offset_y)

        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(
                offset_x,
                offset_y,
                image=self.tk_image,
                anchor=tk.NW,
            )
        else:
            self.canvas.coords(self.canvas_image_id, offset_x, offset_y)
            self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)

        # Remove previous selection rectangle as it is no longer accurate.
        if self.selection_rect_id is not None:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None
            self.selection_coords = None

        self.status_var.set(
            f"Página {self.current_page_index + 1} de {self.doc.page_count}"
        )

    # ---------------------------------------------------------- Mouse input ----
    def _on_mouse_down(self, event: tk.Event) -> None:
        if not self.doc or not self.tk_image:
            return
        self.selection_start = (event.x, event.y)
        if self.selection_rect_id is not None:
            self.canvas.delete(self.selection_rect_id)
        self.selection_rect_id = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#47c1e1",
            width=2,
            dash=(4, 2),
        )

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if self.selection_start is None or self.selection_rect_id is None:
            return
        self.canvas.coords(
            self.selection_rect_id,
            self.selection_start[0],
            self.selection_start[1],
            event.x,
            event.y,
        )

    def _on_mouse_up(self, event: tk.Event) -> None:
        if self.selection_start is None or self.selection_rect_id is None:
            return
        x0, y0 = self.selection_start
        x1, y1 = event.x, event.y
        if abs(x1 - x0) < 2 or abs(y1 - y0) < 2:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None
            self.selection_coords = None
        else:
            self.selection_coords = (x0, y0, x1, y1)
        self.selection_start = None

    # ------------------------------------------------------------- Blurring ----
    def apply_blur(self) -> None:
        if not self.doc:
            messagebox.showinfo("Nenhum PDF", "Abra um arquivo antes de aplicar o desfoque.")
            return
        if not self.selection_coords:
            messagebox.showwarning("Seleção vazia", "Arraste o mouse sobre a área que deseja borrar.")
            return

        rect = self._canvas_to_image_rect(self.selection_coords)
        if rect is None:
            messagebox.showwarning("Seleção inválida", "Selecione uma área dentro da página exibida.")
            return

        page_image = self.page_images[self.current_page_index]
        updated = blur_region(page_image, rect, radius=self.blur_radius.get())
        self.page_images[self.current_page_index] = updated
        self.modified_pages.add(self.current_page_index)
        self._render_current_page()
        messagebox.showinfo("Desfoque aplicado", "A área selecionada foi borrada. Lembre-se de salvar o PDF.")

    def _canvas_to_image_rect(self, selection: CanvasRect) -> Optional[Rect]:
        if not self.display_image:
            return None

        x0, y0, x1, y1 = selection
        offset_x, offset_y = self.image_offset
        left = min(x0, x1) - offset_x
        right = max(x0, x1) - offset_x
        top = min(y0, y1) - offset_y
        bottom = max(y0, y1) - offset_y

        left /= self.display_scale
        right /= self.display_scale
        top /= self.display_scale
        bottom /= self.display_scale

        image_width, image_height = self.page_images[self.current_page_index].size

        left = max(0, min(int(left), image_width))
        right = max(0, min(int(right), image_width))
        top = max(0, min(int(top), image_height))
        bottom = max(0, min(int(bottom), image_height))

        if left >= right or top >= bottom:
            return None

        return left, top, right, bottom


def launch() -> None:
    root = tk.Tk()
    app = PdfBlurApp(root)
    root.mainloop()
