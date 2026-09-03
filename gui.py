import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Auto-redirección al entorno virtual (.venv) si existe y el script fue ejecutado con Python global
project_dir = Path(__file__).parent.resolve()
venv_python = project_dir / ".venv" / "Scripts" / "python.exe"

if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    import subprocess
    result = subprocess.run([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(result.returncode)

# Inyectar certificados del sistema de Windows para redes corporativas con proxy/SSL inspection
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Import conversion functions from convert.py module
from convert import convert_with_fast_engine, convert_with_docling_engine, is_digital_pdf, get_unique_output_path


class PDFConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Convertidor PDF a Markdown (Local)")
        self.root.geometry("680x560")
        self.root.minsize(620, 500)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Color Palette - Sleek Modern Dark Theme
        self.bg_color = "#1e1e2e"
        self.card_bg = "#252538"
        self.fg_color = "#cdd6f4"
        self.accent_color = "#89b4fa"
        self.accent_hover = "#b4befe"
        self.btn_cancel = "#f38ba8"
        
        self.root.configure(bg=self.bg_color)
        
        # Set ttk style configurations
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("TLabel", background=self.card_bg, foreground=self.fg_color)
        self.style.configure("Header.TLabel", background=self.bg_color, foreground=self.accent_color, font=("Segoe UI", 16, "bold"))
        self.style.configure("SubHeader.TLabel", background=self.bg_color, foreground="#a6adc8", font=("Segoe UI", 9))
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        self.style.configure("TRadiobutton", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("TCheckbutton", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        
        # Accent button style
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), background=self.accent_color, foreground="#11111b")
        self.style.map("Accent.TButton", background=[("active", self.accent_hover)])
        
        # Cancel button style
        self.style.configure("Cancel.TButton", font=("Segoe UI", 10), background="#45475a", foreground=self.fg_color)
        
        # Variables
        self.input_file_var = tk.StringVar()
        self.output_file_var = tk.StringVar()
        self.engine_var = tk.StringVar(value="auto")
        self.extract_images_var = tk.BooleanVar(value=False)
        self.generate_csv_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Selecciona un archivo PDF para comenzar.")
        self.is_processing = False
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Header
        header_frame = ttk.Frame(self.root, padding=(20, 15, 20, 5))
        header_frame.pack(side="top", fill="x")
        
        title_label = ttk.Label(header_frame, text="Convertidor Local PDF a Markdown", style="Header.TLabel")
        title_label.pack(anchor="w")
        
        subtitle_label = ttk.Label(header_frame, text="Convierte documentos sin consumir créditos ni enviar información a la nube", style="SubHeader.TLabel")
        subtitle_label.pack(anchor="w", pady=(2, 0))

        # Action Buttons Footer (Aceptar / Cancelar) - EMPAQUETADO AL FONDO PRIMERO PARA QUE SIEMPRE SEA VISIBLE
        footer_frame = ttk.Frame(self.root, padding=(20, 10, 20, 15))
        footer_frame.pack(side="bottom", fill="x")
        
        btn_cancel = tk.Button(footer_frame, text="Cancelar / Salir", command=self.on_cancel,
                               font=("Segoe UI", 10), bg="#45475a", fg=self.fg_color,
                               activebackground="#585b70", activeforeground=self.fg_color,
                               relief="flat", bd=6, padx=15, cursor="hand2")
        btn_cancel.pack(side="right", padx=(10, 0))
        
        self.btn_convert = tk.Button(footer_frame, text="✔ Aceptar / Convertir", command=self.start_conversion,
                                     font=("Segoe UI", 10, "bold"), bg="#89b4fa", fg="#11111b",
                                     activebackground="#b4befe", activeforeground="#11111b",
                                     relief="flat", bd=6, padx=20, cursor="hand2")
        self.btn_convert.pack(side="right")
        
        # Main Card Container (ocupa el espacio central entre header y footer)
        main_card = ttk.Frame(self.root, style="Card.TFrame", padding=(20, 12, 20, 12))
        main_card.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 10))
        
        # 1. Input File Selection
        ttk.Label(main_card, text="1. Archivo PDF de Entrada:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        input_box = ttk.Frame(main_card, style="Card.TFrame")
        input_box.pack(fill="x", pady=(4, 12))
        
        self.input_entry = tk.Entry(input_box, textvariable=self.input_file_var, font=("Segoe UI", 10),
                                    bg="#313244", fg=self.fg_color, insertbackground=self.fg_color, relief="flat", bd=5)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_browse_in = tk.Button(input_box, text="Examinar...", command=self.browse_input_file,
                                  font=("Segoe UI", 9, "bold"), bg="#45475a", fg=self.fg_color,
                                  activebackground="#585b70", activeforeground=self.fg_color, relief="flat", bd=4, cursor="hand2")
        btn_browse_in.pack(side="right")
        
        # 2. Output File Path & Name Selection
        ttk.Label(main_card, text="2. Ruta y Nombre de los Archivos de Salida (.md / .csv):", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        output_box = ttk.Frame(main_card, style="Card.TFrame")
        output_box.pack(fill="x", pady=(4, 12))
        
        self.output_entry = tk.Entry(output_box, textvariable=self.output_file_var, font=("Segoe UI", 10),
                                     bg="#313244", fg=self.fg_color, insertbackground=self.fg_color, relief="flat", bd=5)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_browse_out = tk.Button(output_box, text="Guardar Como...", command=self.browse_output_file,
                                   font=("Segoe UI", 9, "bold"), bg="#45475a", fg=self.fg_color,
                                   activebackground="#585b70", activeforeground=self.fg_color, relief="flat", bd=4, cursor="hand2")
        btn_browse_out.pack(side="right")
        
        # 3. Motor de Conversión
        ttk.Label(main_card, text="3. Motor de Conversión:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        engine_box = ttk.Frame(main_card, style="Card.TFrame")
        engine_box.pack(fill="x", pady=(4, 8))
        
        rb_auto = ttk.Radiobutton(engine_box, text="Auto (Recomendado)", variable=self.engine_var, value="auto")
        rb_fast = ttk.Radiobutton(engine_box, text="Rápido (PyMuPDF)", variable=self.engine_var, value="fast")
        rb_docling = ttk.Radiobutton(engine_box, text="Avanzado / OCR (Docling)", variable=self.engine_var, value="advanced")
        
        rb_auto.pack(side="left", padx=(0, 15))
        rb_fast.pack(side="left", padx=(0, 15))
        rb_docling.pack(side="left")
        
        # Checkbox opciones
        chk_img = ttk.Checkbutton(main_card, text="Extraer imágenes incrustadas en carpeta /media", variable=self.extract_images_var)
        chk_img.pack(anchor="w", pady=(4, 2))
        
        chk_csv = ttk.Checkbutton(main_card, text="Generar automáticamente archivos CSV (Resumen y Movimientos)", variable=self.generate_csv_var)
        chk_csv.pack(anchor="w", pady=(2, 8))
        
        # Progress & Status Bar
        self.progress = ttk.Progressbar(main_card, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 4))
        
        self.lbl_status = ttk.Label(main_card, textvariable=self.status_var, font=("Segoe UI", 9, "italic"), foreground="#b4befe")
        self.lbl_status.pack(anchor="w")

    def browse_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo PDF",
            filetypes=[("Archivos PDF (*.pdf)", "*.pdf"), ("Todos los archivos (*.*)", "*.*")]
        )
        if file_path:
            pdf_path = Path(file_path)
            self.input_file_var.set(str(pdf_path))
            
            # Suggest default output markdown path (con sufijo (1), (2)... si ya existe para nunca sobreescribir)
            default_out = get_unique_output_path(pdf_path.parent / f"{pdf_path.stem}.md")
            self.output_file_var.set(str(default_out))
            self.status_var.set(f"PDF seleccionado: {pdf_path.name}")

    def browse_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Guardar archivos Markdown y CSV como",
            defaultextension=".md",
            filetypes=[("Archivos Markdown y CSV (*.md)", "*.md"), ("Todos los archivos (*.*)", "*.*")]
        )
        if file_path:
            self.output_file_var.set(file_path)

    def start_conversion(self):
        input_file = self.input_file_var.get().strip()
        output_file = self.output_file_var.get().strip()
        
        if not input_file or not os.path.exists(input_file):
            messagebox.showwarning("Archivo no encontrado", "Por favor selecciona un archivo PDF válido.")
            return
            
        if not output_file:
            messagebox.showwarning("Ruta de salida vacía", "Por favor especifica la ruta y nombre de los archivos de salida.")
            return
            
        if self.is_processing:
            return

        # Garantizar nombre único con (1), (2)... si ya existe para nunca sobreescribir ni borrar archivos
        unique_out = get_unique_output_path(Path(output_file))
        if unique_out != Path(output_file):
            output_file = str(unique_out)
            self.output_file_var.set(output_file)
            
        self.is_processing = True
        self.btn_convert.config(state="disabled", bg="#585b70")
        self.progress.start(10)
        self.status_var.set("Procesando conversión local de PDF... Por favor espera.")
        
        # Run conversion in a separate thread so GUI remains responsive
        threading.Thread(target=self._run_conversion_thread, args=(Path(input_file), Path(output_file)), daemon=True).start()

    def _run_conversion_thread(self, input_path: Path, output_path: Path):
        engine = self.engine_var.get()
        extract_img = self.extract_images_var.get()
        
        try:
            # Determine engine
            selected_engine = engine
            if engine == "auto":
                is_digital = is_digital_pdf(input_path)
                selected_engine = "fast" if is_digital else "advanced"
                
            # Ejecutar conversión a Markdown
            if selected_engine == "fast":
                convert_with_fast_engine(input_path, output_path, write_images=extract_img)
            else:
                convert_with_docling_engine(input_path, output_path)
                
            csv_files = []
            if self.generate_csv_var.get():
                try:
                    from md_to_csv import export_to_csv
                    main_csv, mov_csv = export_to_csv(output_path, output_dir=output_path.parent)
                    if main_csv and main_csv.exists():
                        csv_files.append(main_csv.name)
                    if mov_csv and mov_csv.exists():
                        csv_files.append(mov_csv.name)
                except Exception as ex:
                    print(f"Error generando CSV: {ex}")

            self.root.after(0, self._on_success, output_path, selected_engine, csv_files)
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_success(self, output_path: Path, engine_used: str, csv_files: list = None):
        self.progress.stop()
        self.is_processing = False
        self.btn_convert.config(state="normal", bg="#89b4fa")
        extra_info = " + CSVs" if csv_files else ""
        self.status_var.set(f"¡Éxito! Guardado en: {output_path.name}{extra_info} (Motor: {engine_used.upper()})")
        
        detalles_csv = ""
        if csv_files:
            detalles_csv = "\nArchivos CSV generados en la misma ruta:\n" + "\n".join(f"• {f}" for f in csv_files) + "\n"

        msg = (
            f"Se han generado correctamente los archivos en la ruta de guardado:\n\n"
            f"Carpeta: {output_path.parent}\n"
            f"• {output_path.name}\n"
            f"{detalles_csv}\n"
            f"¿Deseas abrir la carpeta de destino?"
        )

        res = messagebox.askyesno("Conversión Exitosa", msg)
        if res:
            os.startfile(output_path.parent)

    def _on_error(self, err_msg: str):
        self.progress.stop()
        self.is_processing = False
        self.btn_convert.config(state="normal", bg="#89b4fa")
        self.status_var.set("Error durante la conversión.")
        messagebox.showerror("Error de Conversión", f"Ocurrió un error al procesar el archivo:\n\n{err_msg}")

    def on_cancel(self):
        if self.is_processing:
            if messagebox.askyesno("Cancelar", "¿Hay una conversión en progreso. ¿Deseas salir de todas formas?"):
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = PDFConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
