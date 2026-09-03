import os
import sys
import subprocess
from pathlib import Path

# Auto-redirección al entorno virtual (.venv) si existe y el script fue ejecutado con Python global
project_dir = Path(__file__).parent.resolve()
venv_python = project_dir / ".venv" / "Scripts" / "python.exe"

if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    # Re-ejecutar automáticamente usando el Python del entorno virtual con el script y los argumentos originales
    result = subprocess.run([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(result.returncode)

# Inyectar certificados del sistema de Windows para redes corporativas con proxy/SSL inspection
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import time
import argparse
from typing import Optional, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

console = Console()

def is_digital_pdf(pdf_path: Path, char_threshold_per_page: int = 80) -> bool:
    """
    Checks if a PDF has searchable digital text or if it's scanned/image-based.
    """
    try:
        import pymupdf as fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return False
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        avg_chars = total_chars / len(doc)
        doc.close()
        return avg_chars >= char_threshold_per_page
    except Exception:
        return False


def get_unique_output_path(base_path: Path) -> Path:
    """
    Si base_path ya existe (o sus archivos asociados .csv/.md),
    devuelve una ruta única agregando (1), (2), etc. al final del nombre,
    garantizando que nunca se sobreescriba ni borre ningún archivo existente.
    """
    parent = base_path.parent
    stem = base_path.stem
    ext = base_path.suffix if base_path.suffix else ".md"

    def file_exists(s: str) -> bool:
        return (
            (parent / f"{s}{ext}").exists()
            or (parent / f"{s}.csv").exists()
            or (parent / f"{s}_movimientos.csv").exists()
        )

    if not file_exists(stem):
        return parent / f"{stem}{ext}"

    import re
    match = re.search(r"^(.*?)\s*\((\d+)\)$", stem)
    if match:
        base_stem = match.group(1).strip()
        counter = int(match.group(2)) + 1
    else:
        base_stem = stem
        counter = 1

    while file_exists(f"{base_stem} ({counter})"):
        counter += 1

    return parent / f"{base_stem} ({counter}){ext}"


def convert_with_fast_engine(pdf_path: Path, output_md_path: Path, write_images: bool = False) -> str:
    """
    Converts PDF to Markdown using PyMuPDF4LLM (ultra-fast).
    """
    import pymupdf as fitz
    import pymupdf4llm

    image_path_opt = str(output_md_path.parent / "media") if write_images else None
    if write_images and image_path_opt:
        os.makedirs(image_path_opt, exist_ok=True)

    md_text = pymupdf4llm.to_markdown(
        str(pdf_path),
        write_images=write_images,
        image_path=image_path_opt
    )

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    return md_text


def convert_with_docling_engine(pdf_path: Path, output_md_path: Path) -> str:
    """
    Converts PDF to Markdown using Docling (IBM layout analysis & OCR).
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    md_text = result.document.export_to_markdown()

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    return md_text


def process_single_pdf(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    engine: str = "auto",
    extract_images: bool = False,
    generate_csv: bool = True
) -> dict:
    """
    Processes a single PDF file and returns conversion status.
    """
    start_time = time.time()
    pdf_path = pdf_path.resolve()

    if not pdf_path.exists():
        return {
            "file": pdf_path.name,
            "status": "Error",
            "engine_used": "-",
            "time_sec": 0,
            "output": "",
            "error": "File not found"
        }

    # Determine output file path (asegurando nombre único con (1), (2)... si ya existe)
    if output_dir:
        candidate_md = output_dir / f"{pdf_path.stem}.md"
    else:
        candidate_md = pdf_path.parent / f"{pdf_path.stem}.md"
    out_md_path = get_unique_output_path(candidate_md)

    # Select engine
    selected_engine = engine
    if engine == "auto":
        is_digital = is_digital_pdf(pdf_path)
        selected_engine = "fast" if is_digital else "advanced"

    try:
        if selected_engine == "fast":
            convert_with_fast_engine(pdf_path, out_md_path, write_images=extract_images)
        else:
            convert_with_docling_engine(pdf_path, out_md_path)

        if generate_csv:
            try:
                from md_to_csv import export_to_csv
                export_to_csv(out_md_path, output_dir=out_md_path.parent)
            except Exception:
                pass

        elapsed = round(time.time() - start_time, 2)
        return {
            "file": pdf_path.name,
            "status": "Success",
            "engine_used": selected_engine.upper(),
            "time_sec": elapsed,
            "output": str(out_md_path),
            "error": None
        }
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        return {
            "file": pdf_path.name,
            "status": "Error",
            "engine_used": selected_engine.upper(),
            "time_sec": elapsed,
            "output": "",
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description="Local PDF to Markdown Converter (PyMuPDF4LLM & Docling)"
    )
    parser.add_argument("input", type=str, help="Path to a PDF file or directory containing PDFs")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Directory to save generated Markdown files")
    parser.add_argument(
        "-e", "--engine", choices=["auto", "fast", "advanced"], default="auto",
        help="Conversion engine: 'fast' (PyMuPDF4LLM), 'advanced' (Docling OCR), or 'auto' (default)"
    )
    parser.add_argument("--extract-images", action="store_true", help="Extract embedded images (fast engine only)")
    parser.add_argument("--no-csv", action="store_true", help="Do not generate CSV files alongside Markdown")

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None

    console.print(Panel.fit(
        "[bold cyan]Local PDF to Markdown Converter[/bold cyan]\n"
        "[dim]Convert PDFs locally without cloud AI credits[/dim]",
        border_style="cyan"
    ))

    # Find target files
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            console.print("[bold red]Error:[/bold red] The input file must be a PDF.")
            sys.exit(1)
        pdf_files = [input_path]
    elif input_path.is_dir():
        pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("**/*.pdf"))
        # Remove duplicates if recursive found same file
        pdf_files = sorted(list(set(pdf_files)))
        if not pdf_files:
            console.print(f"[bold yellow]No PDF files found in directory:[/bold yellow] {input_path}")
            sys.exit(0)
    else:
        console.print(f"[bold red]Error:[/bold red] Input path '[yellow]{args.input}[/yellow]' does not exist.")
        sys.exit(1)

    console.print(f"Found [bold green]{len(pdf_files)}[/bold green] PDF file(s) to process.\n")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing PDFs...", total=len(pdf_files))
        for pdf_file in pdf_files:
            progress.update(task, description=f"Processing [cyan]{pdf_file.name}[/cyan]...")
            res = process_single_pdf(
                pdf_file,
                output_dir=output_dir,
                engine=args.engine,
                extract_images=args.extract_images,
                generate_csv=not args.no_csv
            )
            results.append(res)
            progress.advance(task)

    # Print summary table
    table = Table(title="Conversion Summary", show_header=True, header_style="bold magenta")
    table.add_column("Filename", style="dim", width=30)
    table.add_column("Engine", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Time (s)", justify="right")
    table.add_column("Output File", style="green")

    for r in results:
        status_str = f"[bold green]OK[/bold green]" if r["status"] == "Success" else f"[bold red]FAILED[/bold red]"
        out_str = r["output"] if r["status"] == "Success" else f"[red]{r['error']}[/red]"
        table.add_row(
            r["file"],
            r["engine_used"],
            status_str,
            str(r["time_sec"]),
            out_str
        )

    console.print("\n")
    console.print(table)
    console.print(f"\n[bold green]Done![/bold green] Processed {len(results)} file(s).")


if __name__ == "__main__":
    main()
