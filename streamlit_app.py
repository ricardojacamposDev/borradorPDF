"""Streamlit interface for blurring areas in PDF pages."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import fitz
except ModuleNotFoundError as exc:  # pragma: no cover - environment issue
    raise ImportError(
        "O módulo 'fitz' (PyMuPDF) não foi encontrado. Ative a virtualenv do projeto "
        "e execute 'pip install -r requirements.txt' antes de rodar o Streamlit."
    ) from exc
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Foi encontrado um pacote 'fitz' incompatível. Remova-o com 'pip uninstall fitz' "
        "no Python global e rode esta aplicação usando o Python da pasta .venv: "
        "python -m streamlit run streamlit_app.py"
    ) from exc

import streamlit as st
import streamlit.elements.image as st_image
from PIL import Image
from streamlit.elements.lib.image_utils import image_to_url as _image_to_url
from streamlit.elements.lib.layout_utils import LayoutConfig

from pdf_blur.processing import Rect, blur_region
def _ensure_streamlit_image_patch() -> None:
    """Provide compatibility for streamlit_drawable_canvas on Streamlit >=1.50."""

    if hasattr(st_image, "image_to_url"):
        return

    def _patched_image_to_url(
        image: Image.Image,
        width: int,
        clamp: bool,
        channels: str,
        output_format: str,
        image_id: str,
    ) -> str:
        layout = LayoutConfig(width=width)
        return _image_to_url(
            image,
            layout,
            clamp=clamp,
            channels=channels,
            output_format=output_format,
            image_id=image_id,
        )

    st_image.image_to_url = _patched_image_to_url  # type: ignore[attr-defined]


_ensure_streamlit_image_patch()

from streamlit_drawable_canvas import st_canvas


def _streamlit_rerun() -> None:
    """Compatibility wrapper for Streamlit rerun API across versions."""

    if hasattr(st, "rerun"):
        st.rerun()
        return
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
        return
    raise RuntimeError("Nenhum método de rerun disponível nesta versão do Streamlit.")

PageIndex = int
_ImageBytes = bytes


@dataclass
class CanvasSelection:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def as_rect(self) -> Rect:
        return self.left, self.top, self.right, self.bottom


def _get_pdf_bytes() -> Optional[bytes]:
    uploaded = st.file_uploader("Envie um PDF", type="pdf")
    if uploaded is not None:
        data = uploaded.read()
        st.session_state["pdf_bytes"] = data
        st.session_state.setdefault("modified_pages", {})
        return data
    return st.session_state.get("pdf_bytes")


@st.cache_data(show_spinner=False)
def _page_count(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


@st.cache_data(show_spinner=False)
def _render_page(pdf_bytes: bytes, page_index: int, zoom: float = 2.0) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[page_index]
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _selection_from_canvas(canvas_result, scale_x: float, scale_y: float) -> Optional[CanvasSelection]:
    if not canvas_result.json_data:
        return None
    objects = canvas_result.json_data.get("objects", [])
    if not objects:
        return None
    obj = objects[-1]
    width = obj.get("width", 0)
    height = obj.get("height", 0)
    if width < 2 or height < 2:
        return None
    left = int(obj.get("left", 0) * scale_x)
    top = int(obj.get("top", 0) * scale_y)
    right = int((obj.get("left", 0) + width) * scale_x)
    bottom = int((obj.get("top", 0) + height) * scale_y)
    return CanvasSelection(left, top, right, bottom)


def _store_modified_page(page_index: PageIndex, image: Image.Image) -> None:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    st.session_state.setdefault("modified_pages", {})[page_index] = buffer.getvalue()


def _load_modified_page(page_index: PageIndex) -> Optional[Image.Image]:
    pages: Dict[PageIndex, bytes] = st.session_state.get("modified_pages", {})
    if page_index not in pages:
        return None
    return _image_from_bytes(pages[page_index])


def _build_pdf(pdf_bytes: bytes, overrides: Dict[PageIndex, bytes]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_index, image_data in overrides.items():
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        page = doc[page_index]
        page.clean_contents()
        page.insert_image(page.rect, stream=buffer.getvalue())
    output = io.BytesIO()
    doc.save(output)
    doc.close()
    return output.getvalue()


def _display_canvas(image: Image.Image, page_index: PageIndex):
    max_width = 900
    if image.width <= max_width:
        display_width = image.width
        display_height = image.height
    else:
        scale = max_width / image.width
        display_width = int(image.width * scale)
        display_height = int(image.height * scale)
    display_image = image.resize((display_width, display_height))

    canvas_result = st_canvas(
        fill_color="rgba(71, 193, 225, 0.3)",
        stroke_color="#47c1e1",
        stroke_width=3,
        background_image=display_image,
        update_streamlit=True,
        drawing_mode="rect",
        height=display_height,
        width=display_width,
        key=f"canvas-page-{page_index}",
    )
    scale_x = image.width / display_width
    scale_y = image.height / display_height
    selection = _selection_from_canvas(canvas_result, scale_x, scale_y)
    return selection


def main() -> None:
    st.set_page_config(page_title="Borrador de PDF (Streamlit)", layout="wide")
    st.title("Borrador de PDF via Streamlit")
    st.write("Faça upload de um PDF, selecione uma área retangular e aplique desfoque antes de baixar o arquivo novamente.")

    pdf_bytes = _get_pdf_bytes()
    if not pdf_bytes:
        st.info("Envie um PDF para começar.")
        return

    page_count = _page_count(pdf_bytes)
    if page_count <= 1:
        st.info("Este PDF possui apenas uma página.")
        current_page = 1
    else:
        current_page = st.slider(
            "Página",
            min_value=1,
            max_value=page_count,
            value=min(st.session_state.get("current_page", 1), page_count),
        )
    st.session_state["current_page"] = current_page
    page_index = current_page - 1

    base_image = _image_from_bytes(_render_page(pdf_bytes, page_index))
    modified_image = _load_modified_page(page_index)
    working_image = modified_image if modified_image is not None else base_image

    blur_radius = st.slider("Raio do desfoque (px)", min_value=2, max_value=60, value=12)
    selection = _display_canvas(working_image, page_index)

    col_left, col_right = st.columns([1, 1])
    with col_left:
        if selection:
            st.success(
                f"Seleção pronta: x[{selection.left}, {selection.right}] y[{selection.top}, {selection.bottom}]."
            )
        else:
            st.info("Desenhe um retângulo na imagem para definir a área a borrar.")

        if st.button("Aplicar desfoque", disabled=selection is None):
            if selection is None:
                st.warning("Selecione uma área antes de aplicar o desfoque.")
            else:
                updated = blur_region(working_image, selection.as_rect, radius=blur_radius)
                _store_modified_page(page_index, updated)
                st.success("Área borrada nesta página.")
                _streamlit_rerun()

    with col_right:
        if page_index in st.session_state.get("modified_pages", {}):
            if st.button("Desfazer alterações desta página"):
                st.session_state["modified_pages"].pop(page_index, None)
                _streamlit_rerun()
        else:
            st.caption("Esta página ainda não foi modificada.")

    overrides: Dict[int, bytes] = st.session_state.get("modified_pages", {})
    if overrides:
        st.divider()
        st.subheader("Exportar PDF")
        output_data = _build_pdf(pdf_bytes, overrides)
        st.download_button(
            "Baixar PDF borrado",
            data=output_data,
            file_name="pdf-borrado.pdf",
            mime="application/pdf",
        )
    else:
        st.info("Nenhuma página foi modificada ainda.")


if __name__ == "__main__":
    main()
