# PDF to Markdown Converter (Local GUI & Streamlit Web App)

[![Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Herramienta completa para convertir documentos PDF a formato **Markdown (`.md`)** estructurado y limpio, preservando tablas, títulos y párrafos, ideal para integración con modelos de lenguaje (LLMs), sistemas RAG y análisis de documentos.

El proyecto incluye dos versiones:
1. **Versión Web (Streamlit):** Diseñada para ejecutarse en el navegador o desplegarse en la nube (**Render.com**), ligera, en memoria y sin generación de CSV.
2. **Versión de Escritorio Local (GUI Tkinter):** Con soporte para OCR avanzado (IBM Docling), interfaz gráfica nativa y extracción opcional a CSV.

---

## 🌐 1. Versión Web (Streamlit)

La versión web permite arrastrar y soltar cualquier PDF, previsualizar el Markdown formateado en tiempo real y descargarlo con un solo clic. **No genera ningún archivo CSV**.

### Ejecución Local

1. **Instalar dependencias necesarias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Iniciar la aplicación:**
   ```bash
   streamlit run app.py
   ```
   La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`.

### Características de la Versión Web
- **Conversión en Memoria:** No escribe archivos temporales en el disco del servidor.
- **Bajo Consumo de Memoria:** Utiliza `PyMuPDF4LLM` (< 60 MB RAM), perfecto para planes gratuitos de hosting.
- **Previsualización dual:** Pestaña con vista previa renderizada y pestaña con el código Markdown en crudo.
- **Métricas:** Muestra páginas procesadas, tiempo de ejecución, recuento de palabras y caracteres.
- **Filtro de páginas:** Permite procesar todo el documento o páginas específicas (ej. `1-3, 5`).

---

## 🚀 2. Guía de Despliegue en Render.com

La aplicación está lista para desplegarse de forma gratuita en [Render.com](https://render.com).

### Método Automático (Blueprint con `render.yaml`)
1. Sube tu repositorio a GitHub.
2. En el panel de Render, haz clic en **New +** y selecciona **Blueprint**.
3. Conecta tu repositorio `pdf-to-md`.
4. Render detectará automáticamente el archivo [render.yaml](render.yaml) y configurará todo el servicio.
5. Haz clic en **Apply**.

### Método Manual (Web Service)
1. En Render.com, haz clic en **New +** $\to$ **Web Service**.
2. Conecta tu repositorio de GitHub: `aldovalenciapalma-commits/pdf-to-md`.
3. Configura los siguientes campos:
   - **Name:** `pdf-to-md` (o el nombre que prefieras)
   - **Region:** Elige la más cercana (ej. *Oregon (US West)* u *Ohio (US East)*)
   - **Branch:** `main`
   - **Language / Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
     ```
   - **Instance Type:** `Free` (512 MB RAM)
4. En **Advanced Settings**, añade la variable de entorno:
   - `PYTHON_VERSION`: `3.11.9`
5. Haz clic en **Create Web Service**.
6. En un par de minutos, Render te proporcionará la URL pública (ej. `https://pdf-to-md.onrender.com`).

---

## 💻 3. Versión de Escritorio Local (GUI Tkinter)

Para uso en tu equipo local con soporte para documentos escaneados e imágenes mediante OCR:

1. Inicia la aplicación con un doble clic en:
   ```cmd
   run_gui.bat
   ```
   o por consola:
   ```bash
   python gui.py
   ```
2. **Características:**
   - Selección mediante ventana nativa de Windows.
   - Motor **Rápido (PyMuPDF)** o **Avanzado (Docling OCR)**.
   - Opción para extraer imágenes y generar CSVs de resumen y movimientos.
   - **Protección contra sobreescritura:** Agrega automáticamente `(1)`, `(2)` si el archivo de salida ya existe.

---

## ⌨️ 4. Versión de Consola (CLI)

También puedes convertir archivos o carpetas completas desde la terminal:

```bash
# Convertir un archivo individual
python convert.py documento.pdf

# Convertir una carpeta completa
python convert.py ./mis_pdfs -o ./salidas/

# Usar el motor de OCR avanzado
python convert.py documento_escaneado.pdf --engine advanced
```

---

## 📦 Estructura del Proyecto

```text
├── app.py              # Aplicación Web en Streamlit (v2)
├── requirements.txt    # Dependencias optimizadas para Streamlit y Render.com
├── render.yaml         # Configuración de despliegue en Render.com
├── gui.py              # Interfaz gráfica de escritorio en Tkinter (v1)
├── convert.py          # Módulo principal de conversión y CLI
├── md_to_csv.py        # Parser de estados de cuenta y generador de CSV
├── run_gui.bat         # Acceso directo para iniciar la GUI en Windows
└── README.md           # Documentación del proyecto
```
