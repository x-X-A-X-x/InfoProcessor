#do pip install pypdf
#!/usr/bin/env python3
import argparse
import glob
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter, PageObject, Transformation

A4 = (595.275590551, 841.88976378)      # 210 x 297 mm in points (72 dpi)
LETTER = (612.0, 792.0)                 # 8.5 x 11 in in points

SIZES = {
    "A4": A4,
    "LETTER": LETTER,
}

def natural_sort_key(p: Path):
    # Simple natural-ish sort: split digits and text
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.findall(r"\d+|\D+", p.stem)]

def add_page_preserve(writer: PdfWriter, page: PageObject):
    """Add page without changing size or orientation."""
    # Honor any rotation metadata as-is
    writer.add_page(page)

def add_page_fitted(writer: PdfWriter, page: PageObject, target_w: float, target_h: float, force_landscape: bool):
    """Fit a page into a target canvas, preserving aspect ratio, centered."""
    src_w = float(page.mediabox.width)
    src_h = float(page.mediabox.height)

    # Optionally flip target to landscape
    tw, th = (max(target_w, target_h), min(target_w, target_h)) if force_landscape else (target_w, target_h)

    new_page = PageObject.create_blank_page(width=tw, height=th)

    # Scale to fit while preserving aspect ratio
    scale = min(tw / src_w, th / src_h)

    # Center offsets
    tx = (tw - src_w * scale) / 2.0
    ty = (th - src_h * scale) / 2.0

    # Build a transformation: scale then translate
    op = Transformation().scale(scale).translate(tx, ty)
    new_page.merge_transformed_page(page, op, expand=False)

    writer.add_page(new_page)

def merge_pdfs(
    inputs,
    output,
    recursive=False,
    normalize=None,
    landscape=False
):
    files = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            files.extend(sorted([Path(f) for f in glob.glob(str(p / pattern), recursive=recursive)], key=natural_sort_key))
        else:
            files.append(p)

    # Deduplicate and keep stable order
    seen = set()
    ordered = []
    for f in files:
        if f.suffix.lower() == ".pdf":
            rp = f.resolve()
            if rp not in seen and rp.exists():
                seen.add(rp)
                ordered.append(rp)

    if not ordered:
        raise SystemExit("No PDF files found.")

    writer = PdfWriter()

    # Determine normalization target if requested
    target = None
    if normalize:
        key = normalize.upper()
        if key not in SIZES:
            raise SystemExit(f"Unknown size '{normalize}'. Choose from: {', '.join(SIZES.keys())}")
        target = SIZES[key]

    for f in ordered:
        reader = PdfReader(str(f))
        for page in reader.pages:
            if target is None:
                add_page_preserve(writer, page)
            else:
                add_page_fitted(writer, page, target_w=target[0], target_h=target[1], force_landscape=landscape)

    # Ensure output directory exists
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fp:
        writer.write(fp)

def main():
    parser = argparse.ArgumentParser(
        description="Merge/append PDFs of any size/orientation; optionally normalize to A4/Letter."
    )
    parser.add_argument("inputs", nargs="+", help="PDF files and/or folders (folders will be scanned for PDFs).")
    parser.add_argument("-o", "--output", required=True, help="Output PDF path, e.g., merged.pdf")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into subfolders when a folder is given.")
    parser.add_argument("--normalize", choices=["A4", "LETTER"], help="Fit every page into this canvas size.")
    parser.add_argument("--landscape", action="store_true", help="When --normalize is set, make the target canvas landscape.")
    args = parser.parse_args()

    merge_pdfs(
        inputs=args.inputs,
        output=args.output,
        recursive=args.recursive,
        normalize=args.normalize,
        landscape=args.landscape
    )

if __name__ == "__main__":
    main()
