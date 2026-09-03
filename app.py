import os
import sys
import time
import base64
from pathlib import Path

# Auto-redirección al entorno virtual (.venv) si existe y fue ejecutado con Python global
project_dir = Path(__file__).parent.resolve()
venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    import subprocess
    result = subprocess.run([str(venv_python), "-m", "streamlit", "run", str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(result.returncode)

import streamlit as st
from streamlit.runtime import exists

# Si se ejecuta con 'python app.py' en vez de 'streamlit run app.py', lanzar Streamlit automáticamente
if not exists():
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", str(Path(__file__).resolve())] + sys.argv[1:]
    sys.exit(stcli.main())

import pymupdf
import pymupdf4llm

# Configuración de la página
st.set_page_config(
    page_title="PDF to Markdown Converter",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados sutiles
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #555555;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# Barra lateral
with st.sidebar:
    st.image("https://raw.githubusercontent.com/pymupdf/PyMuPDF/master/doc/images/pymupdf-logo.png", width=120)
    st.title("⚙️ Configuración")
    
    st.markdown("### Opciones de Conversión")
    extract_images = st.checkbox("Extraer imágenes incrustadas", value=False, help="Si se activa, extrae y referencia las imágenes del PDF.")
    
    pages_option = st.radio("Páginas a procesar:", ["Todas las páginas", "Rango específico"])
    page_range = None
    if pages_option == "Rango específico":
        page_input = st.text_input("Ingresa las páginas (ej. 1-3, 5):", placeholder="1-3")
        if page_input.strip():
            try:
                # Parsear páginas (1-indexed a 0-indexed)
                selected_pages = []
                for part in page_input.split(","):
                    part = part.strip()
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        selected_pages.extend(range(start - 1, end))
                    elif part.isdigit():
                        selected_pages.append(int(part) - 1)
                page_range = selected_pages
            except Exception:
                st.warning("Formato de páginas inválido. Se procesarán todas.")
                page_range = None

    st.divider()
    st.markdown("### ℹ️ Acerca de")
    st.info(
        "**Motor:** PyMuPDF4LLM\n\n"
        "• Conversión ultrarrápida en memoria.\n"
        "• Diseñado para LLMs, RAG y búsqueda semántica.\n"
        "• Optimizado para funcionar en servidores con 512 MB RAM (Render.com)."
    )
    
    st.markdown("---")
    st.markdown("[📂 Repositorio en GitHub](https://github.com/aldovalenciapalma-commits/pdf-to-md)")

# Contenido principal
st.markdown('<div class="main-header">📄 Convertidor PDF a Markdown</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Convierte tus documentos PDF a formato Markdown (.md) estructurado y limpio en segundos.</div>', unsafe_allow_html=True)

# Cargador de archivos
uploaded_file = st.file_uploader(
    "Selecciona o arrastra un archivo PDF:",
    type=["pdf"],
    help="Sube un archivo PDF para extraer su contenido estructurado en Markdown."
)

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    file_size_kb = len(file_bytes) / 1024
    file_name = uploaded_file.name
    stem = Path(file_name).stem

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.write(f"📁 **Archivo:** `{file_name}`")
    with col_info2:
        st.write(f"⚖️ **Tamaño:** `{file_size_kb:.1f} KB`")
    with col_info3:
        pass

    # Botón para iniciar conversión
    if st.button("🚀 Convertir a Markdown", type="primary", use_container_width=True):
        start_time = time.time()
        with st.spinner("Procesando documento PDF... Por favor espera."):
            try:
                # Abrir documento en memoria con PyMuPDF
                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                
                # Convertir a Markdown
                kwargs = {}
                if page_range:
                    valid_pages = [p for p in page_range if 0 <= p < total_pages]
                    if valid_pages:
                        kwargs["pages"] = valid_pages
                
                md_text = pymupdf4llm.to_markdown(
                    doc,
                    write_images=extract_images,
                    **kwargs
                )
                
                # Si el PDF es un escaneo o imagen (sin texto digital seleccionable), aplicar OCR automático con RapidOCR
                if not md_text.strip():
                    try:
                        from rapidocr import RapidOCR
                        engine = RapidOCR()
                        ocr_pages = []
                        pages_to_process = list(range(total_pages))
                        if page_range:
                            pages_to_process = [p for p in page_range if 0 <= p < total_pages]
                        
                        for p_idx in pages_to_process:
                            page = doc[p_idx]
                            pix = page.get_pixmap(dpi=150)
                            res = engine(pix.tobytes("png"))
                            if res and hasattr(res, "txts") and res.txts:
                                if hasattr(res, "to_markdown") and callable(res.to_markdown):
                                    p_text = res.to_markdown()
                                else:
                                    p_text = "\n\n".join(res.txts)
                                ocr_pages.append(f"## Página {p_idx + 1}\n\n" + p_text)
                        if ocr_pages:
                            md_text = "\n\n---\n\n".join(ocr_pages)
                    except Exception:
                        pass

                elapsed = time.time() - start_time
                num_words = len(md_text.split())
                num_chars = len(md_text)

                # Guardar resultado en sesión
                st.session_state["md_result"] = md_text
                st.session_state["elapsed"] = elapsed
                st.session_state["pages"] = total_pages
                st.session_state["words"] = num_words
                st.session_state["chars"] = num_chars
                st.session_state["stem"] = stem
                st.session_state["converted"] = True
                doc.close()

            except Exception as e:
                st.error(f"Ocurrió un error al convertir el archivo: {str(e)}")

    # Mostrar resultados si ya fue convertido
    if st.session_state.get("converted") and "md_result" in st.session_state:
        st.success(f"¡Conversión completada en {st.session_state['elapsed']:.2f} segundos!")
        
        # Métricas de la conversión (compatibles con proxies corporativos sin requerir chunks JS externos)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card">📄 <b>Páginas:</b> {st.session_state["pages"]}</div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card">⏱️ <b>Tiempo:</b> {st.session_state["elapsed"]:.2f} s</div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card">🔤 <b>Palabras:</b> {st.session_state["words"]:,}</div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card">📊 <b>Caracteres:</b> {st.session_state["chars"]:,}</div>', unsafe_allow_html=True)

        st.markdown("### 📥 Descargar Resultado")
        out_filename = f"{st.session_state['stem']}.md"
        
        # Enlace de descarga HTML Base64 nativo (funciona 100% incluso en redes corporativas con proxy)
        b64_str = base64.b64encode(st.session_state["md_result"].encode("utf-8")).decode("utf-8")
        dl_html = (
            f'<a href="data:text/markdown;charset=utf-8;base64,{b64_str}" '
            f'download="{out_filename}" '
            f'style="display: inline-block; padding: 12px 24px; font-size: 16px; font-weight: bold; '
            f'color: #ffffff; background-color: #1E88E5; border-radius: 6px; text-decoration: none; '
            f'box-shadow: 0 2px 4px rgba(0,0,0,0.2); margin-bottom: 15px;">⬇️ Descargar {out_filename}</a>'
        )
        st.markdown(dl_html, unsafe_allow_html=True)

        st.markdown("---")
        
        # Selección de vista previa
        view_mode = st.radio("Modo de visualización:", ["📖 Vista Previa del Documento", "📝 Código Markdown en Crudo"], horizontal=True)
        
        if view_mode == "📖 Vista Previa del Documento":
            st.markdown(st.session_state["md_result"], unsafe_allow_html=True)
        else:
            st.code(st.session_state["md_result"], language="markdown")

else:
    # Estado inicial / guía rápida
    st.info("👆 Por favor sube un archivo PDF para comenzar.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### ⚡ Rápido y Eficiente")
        st.write("Convierte documentos en milisegundos utilizando PyMuPDF4LLM.")
    with col2:
        st.markdown("#### 📊 Tablas Estructuradas")
        st.write("Identifica y formatea tablas en sintaxis nativa de Markdown.")
    with col3:
        st.markdown("#### 🔒 100% Privado")
        st.write("El procesamiento se realiza directamente en memoria sin persistencia externa.")

