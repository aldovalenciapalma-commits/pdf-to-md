import os
import sys
import re
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Auto-redirección al entorno virtual (.venv) si existe
project_dir = Path(__file__).parent.resolve()
venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    import subprocess
    result = subprocess.run([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    sys.exit(result.returncode)


def clean_currency(val: str) -> Optional[float]:
    """Limpia cadenas como '$ 12,463.43', '23,401.86' o '18 50,201.89' a float."""
    if not val or val.strip() in ("", "-", "N/A"):
        return None
    # Si viene con cantidad y monto (ej. '9 27,350.03' o '18 50,201.89'), tomar el último elemento
    tokens = val.strip().split()
    target = tokens[-1] if len(tokens) > 1 and re.search(r"\d+\.\d{2}", tokens[-1]) else val
    clean = re.sub(r"[^\d.-]", "", target.replace(",", ""))
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


def extract_count_and_amount(val: str) -> Tuple[Optional[int], Optional[float]]:
    """Separa cadenas de tipo '9 27,350.03' en (9, 27350.03)."""
    if not val:
        return None, None
    tokens = val.strip().split()
    if len(tokens) >= 2 and tokens[0].isdigit():
        count = int(tokens[0])
        amount = clean_currency(tokens[1])
        return count, amount
    return None, clean_currency(val)


def extract_header_fields(text: str) -> Dict[str, str]:
    """Extrae campos del encabezado fuera de tablas (titular, dirección, sucursal, etc.)."""
    lines = [line.strip() for line in text.splitlines()]
    fields = {}

    # El titular suele ser la primera línea con texto real que no sea imagen o encabezado
    for line in lines:
        if line and not line.startswith(("#", "<!--", "|", "-", "SUCURSAL", "DIRECCION", "PLAZA")):
            fields["titular"] = line
            break

    # Extracción de campos con etiquetas conocidas
    patterns = {
        "sucursal": r"SUCURSAL:\s*\n+([^\n]+)",
        "direccion_sucursal": r"DIRECCION:\s*\n+([^\n]+)",
        "plaza": r"PLAZA:\s*\n+([^\n]+)",
        "telefono_sucursal": r"TELEFONO:\s*\n+([^\n]+)",
        "codigo_postal": r"\bCP\s*(\d{5})\b",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields[key] = match.group(1).strip()

    return fields


def parse_key_value_tables(text: str) -> Dict[str, str]:
    """Extrae pares clave-valor de tablas Markdown de 2 columnas."""
    kv_data = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Ignorar separadores |---|---|
        if set(line.replace("|", "").strip()) <= {"-", " "}:
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == 2:
            key, val = cells[0], cells[1]
            if key and val:
                # Normalizar clave (sin acentos, minúsculas, espacios como guiones bajos)
                norm_key = key.lower()
                norm_key = norm_key.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                norm_key = re.sub(r"[^a-z0-9]+", "_", norm_key).strip("_")
                kv_data[norm_key] = val

    return kv_data


def extract_movements_table(text: str) -> List[Dict[str, any]]:
    """
    Extrae con alta precisión la tabla de movimientos/transacciones de la carátula o estado de cuenta.
    Maneja líneas continuas de descripción y montos de transferencias SPEI.
    """
    lines = text.splitlines()
    in_mov_section = False
    raw_rows = []

    for line in lines:
        s = line.strip()
        if "Detalle de Movimientos" in s or "Movimientos Realizados" in s:
            in_mov_section = True
            continue

        if in_mov_section:
            if not s.startswith("|") or "Comportamiento" in s or "Otros productos" in s:
                if s and not s.startswith("|"):
                    in_mov_section = False
                continue
            cells = [c.strip() for c in s.split("|")[1:-1]]
            if len(cells) == 8:
                raw_rows.append(cells)

    movements = []
    current_mov = None

    for row in raw_rows:
        c0, c1, c2, c3, c4, c5, c6, c7 = row[:8]
        # Omitir filas de encabezado
        if c0 in ("FECHA", "OPER", "---------") or "---" in c0:
            continue

        # Si inicia con fecha de operación válida (ej. '05/JUL')
        if re.match(r"^\d{2}/[A-Za-z]{3}", c0):
            cargo = clean_currency(c4)
            abono = clean_currency(c5)
            saldo = clean_currency(c7) if clean_currency(c7) is not None else clean_currency(c6)
            desc = c2
            ref = c3

            # En algunos casos SPEI, el cargo queda anexado al final del texto de referencia
            if cargo is None and abono is None and ref:
                match_amt = re.search(r"([\d,]+\.\d{2})$", ref)
                if match_amt:
                    cargo = clean_currency(match_amt.group(1))
                    ref = ref[:match_amt.start()].strip()

            full_desc = f"{desc} {ref}".strip()
            current_mov = {
                "fecha_operacion": c0,
                "fecha_liquidacion": c1,
                "descripcion": full_desc,
                "cargo": cargo if cargo is not None else "",
                "abono": abono if abono is not None else "",
                "saldo": saldo if saldo is not None else ""
            }
            movements.append(current_mov)
        elif current_mov and (c2 or c3):
            # Línea de continuación de la descripción del movimiento anterior
            cont = f"{c2} {c3}".strip()
            current_mov["descripcion"] += " " + cont
            # Limpiar repeticiones automáticas de palabras si el OCR las duplicó
            current_mov["descripcion"] = re.sub(r"(\b.+?\b)(?:\s+\1)+", r"\1", current_mov["descripcion"]).strip()

    return movements


def parse_markdown_statement(md_path: Path) -> Tuple[Dict[str, any], List[Dict[str, any]]]:
    """Analiza el archivo Markdown y devuelve (diccionario_resumen, lista_movimientos)."""
    text = md_path.read_text(encoding="utf-8")

    header_data = extract_header_fields(text)
    kv_data = parse_key_value_tables(text)

    # Extraer periodo (ej: 'DEL 05/07/2026 AL 04/08/2026')
    periodo_raw = kv_data.get("periodo", "")
    fecha_inicio, fecha_fin = "", ""
    match_fechas = re.findall(r"\d{2}/\d{2}/\d{4}", periodo_raw)
    if len(match_fechas) >= 2:
        fecha_inicio, fecha_fin = match_fechas[0], match_fechas[1]

    # Separar conteos y montos de depósitos / retiros
    cant_dep, total_dep = extract_count_and_amount(kv_data.get("depositos_abonos", ""))
    cant_ret, total_ret = extract_count_and_amount(kv_data.get("retiros_cargos", ""))

    # Consolidar resumen
    summary = {
        "archivo_origen": md_path.name,
        "titular": header_data.get("titular", ""),
        "rfc": kv_data.get("r_f_c", ""),
        "no_cuenta": kv_data.get("no_de_cuenta", ""),
        "no_cliente": kv_data.get("no_de_cliente", ""),
        "clabe": kv_data.get("no_cuenta_clabe", "").replace(" ", ""),
        "fecha_corte": kv_data.get("fecha_de_corte", ""),
        "periodo_inicio": fecha_inicio,
        "periodo_fin": fecha_fin,
        "dias_periodo": kv_data.get("dias_del_periodo", ""),
        "saldo_anterior": clean_currency(kv_data.get("saldo_anterior", "")),
        "cantidad_depositos": cant_dep if cant_dep is not None else "",
        "total_depositos": total_dep if total_dep is not None else "",
        "cantidad_retiros": cant_ret if cant_ret is not None else "",
        "total_retiros": total_ret if total_ret is not None else "",
        "saldo_final": clean_currency(kv_data.get("saldo_final", "")),
        "saldo_promedio": clean_currency(kv_data.get("saldo_promedio", "")),
        "sucursal": header_data.get("sucursal", ""),
        "plaza": header_data.get("plaza", ""),
        "codigo_postal": header_data.get("codigo_postal", ""),
    }

    # Extraer movimientos y relacionar con la cuenta
    movements = extract_movements_table(text)
    for m in movements:
        m["no_cuenta"] = summary["no_cuenta"]
        m["fecha_corte"] = summary["fecha_corte"]

    return summary, movements


def export_to_csv(md_path: Path, output_dir: Optional[Path] = None) -> Tuple[Path, Optional[Path]]:
    """Genera los archivos CSV correspondientes en la misma ruta de guardado del Markdown."""
    out_dir = output_dir or md_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    summary, movements = parse_markdown_statement(md_path)

    # 1. Exportar archivo CSV con el mismo nombre base y en la misma ruta
    main_csv = out_dir / f"{md_path.stem}.csv"
    with open(main_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"[OK] CSV generado: {main_csv}")

    # 2. Si hay movimientos detallados, exportar también el desglose de movimientos
    mov_csv = None
    if movements:
        mov_csv = out_dir / f"{md_path.stem}_movimientos.csv"
        fields = list(movements[0].keys())
        with open(mov_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(movements)
        print(f"[OK] CSV Movimientos generado: {mov_csv} ({len(movements)} registros)")

    return main_csv, mov_csv


def main():
    parser = argparse.ArgumentParser(description="Analiza Markdown de estados de cuenta y genera archivos CSV.")
    parser.add_argument("input", type=str, help="Ruta al archivo Markdown (.md) o directorio")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Directorio donde guardar los CSV")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output_dir) if args.output_dir else None

    if input_path.is_file():
        export_to_csv(input_path, out_dir)
    elif input_path.is_dir():
        md_files = sorted(list(input_path.glob("*.md")))
        if not md_files:
            print(f"No se encontraron archivos .md en {input_path}")
            return

        all_summaries = []
        all_movements = []
        for md_file in md_files:
            s, m = parse_markdown_statement(md_file)
            all_summaries.append(s)
            all_movements.extend(m)

        target_dir = out_dir or input_path
        consolidated_summary_csv = target_dir / "resumen_estados_cuenta_consolidado.csv"
        if all_summaries:
            with open(consolidated_summary_csv, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(all_summaries[0].keys()))
                writer.writeheader()
                writer.writerows(all_summaries)
            print(f"[OK] CSV Consolidado generado: {consolidated_summary_csv} ({len(all_summaries)} archivos procesados)")

        if all_movements:
            consolidated_mov_csv = target_dir / "movimientos_consolidados.csv"
            fields = list(all_movements[0].keys())
            with open(consolidated_mov_csv, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(all_movements)
            print(f"[OK] CSV Movimientos Consolidado generado: {consolidated_mov_csv} ({len(all_movements)} registros)")


if __name__ == "__main__":
    main()
