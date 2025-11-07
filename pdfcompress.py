#Do this first #pip install pymupdf pillow
import os
import threading
import math
import fitz  # PyMuPDF
from PIL import Image
from tkinter import Tk, Label, Button, Scale, HORIZONTAL, filedialog, StringVar, IntVar, Checkbutton

# -------- Helpers --------
def human_size(n):
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"

def est_output_name(in_path, dpi):
    base, _ = os.path.splitext(in_path)
    return f"{base}_compressed_{dpi}dpi.pdf"

# -------- Core compression (rasterize pages) --------
def compress_pdf_raster(in_path, out_path, dpi=144, jpeg_quality=70, grayscale=False, progress_cb=None):
    """
    Re-renders each page to an image at specified DPI and writes back into a compact PDF.
    - dpi: 96–200 is a good practical range
    - jpeg_quality: 40–85 typical (PyMuPDF embeds as JPEG where applicable)
    - grayscale: optional extra shrink
    """
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    src = fitz.open(in_path)
    dst = fitz.open()

    for i, page in enumerate(src, start=1):
        pix = page.get_pixmap(matrix=mat, alpha=False)  # render page
        mode = "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

        if grayscale:
            img = img.convert("L")  # grayscale
            # Pillow will convert back to RGB when saved as JPEG unless we keep 'L'
            # PyMuPDF will embed as JPEG/PNG depending—keep as L to promote smaller size

        # Save to in-memory bytes as JPEG to control quality, then insert
        import io
        buf = io.BytesIO()
        # If page has transparency, above used alpha=False; safe for most PDFs
        img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        img_bytes = buf.getvalue()

        # Insert the JPEG as a full-page image
        new_page = dst.new_page(width=page.rect.width, height=page.rect.height)
        rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
        new_page.insert_image(rect, stream=img_bytes)

        if progress_cb:
            progress_cb(i, len(src))

    # Final save with aggressive cleanup/deflate
    dst.save(out_path, deflate=True, clean=True, garbage=4, linear=True)
    dst.close()
    src.close()

# -------- Tkinter GUI --------
class App:
    def __init__(self, master):
        self.master = master
        master.title("PDF Compressor (No Ghostscript)")

        self.pdf_path = None
        self.status = StringVar(value="Pick a PDF to start.")
        self.sel_var = StringVar(value="No file selected.")
        self.out_var = StringVar(value="-")

        # DPI slider
        Label(master, text="Target DPI (lower = smaller):").grid(row=0, column=0, sticky="w", padx=10, pady=(10,0))
        self.dpi_slider = Scale(master, from_=72, to=200, orient=HORIZONTAL, length=320)
        self.dpi_slider.set(140)
        self.dpi_slider.grid(row=0, column=1, padx=10, pady=(10,0), sticky="w")

        # JPEG quality slider
        Label(master, text="JPEG Quality (40–85):").grid(row=1, column=0, sticky="w", padx=10)
        self.q_slider = Scale(master, from_=40, to=85, orient=HORIZONTAL, length=320)
        self.q_slider.set(70)
        self.q_slider.grid(row=1, column=1, padx=10, sticky="w")

        # Grayscale option
        self.gray_flag = IntVar(value=0)
        self.gray_chk = Checkbutton(master, text="Convert to Grayscale (smaller)", variable=self.gray_flag)
        self.gray_chk.grid(row=2, column=1, padx=10, pady=(0,8), sticky="w")

        # Choose PDF
        Button(master, text="Choose PDF…", command=self.choose_pdf).grid(row=3, column=0, padx=10, pady=6, sticky="w")
        Label(master, textvariable=self.sel_var, wraplength=420).grid(row=3, column=1, padx=10, pady=6, sticky="w")

        # Compress
        Button(master, text="Compress", command=self.on_compress).grid(row=4, column=0, padx=10, pady=8, sticky="w")
        Label(master, text="Output file:").grid(row=5, column=0, padx=10, sticky="w")
        Label(master, textvariable=self.out_var, wraplength=420).grid(row=5, column=1, padx=10, sticky="w")

        # Status
        Label(master, textvariable=self.status, fg="#064", wraplength=520, justify="left").grid(row=6, column=0, columnspan=2, padx=10, pady=(4,12), sticky="w")

        for i in range(2):
            master.grid_columnconfigure(i, weight=1)
        master.resizable(False, False)

    def choose_pdf(self):
        p = filedialog.askopenfilename(title="Select PDF", filetypes=[("PDF files", "*.pdf")])
        if p:
            self.pdf_path = p
            self.sel_var.set(p)
            self.status.set("Ready.")

    def on_compress(self):
        if not self.pdf_path:
            self.status.set("Please choose a PDF first.")
            return
        dpi = int(self.dpi_slider.get())
        q = int(self.q_slider.get())
        gray = bool(self.gray_flag.get())

        out_path = est_output_name(self.pdf_path, dpi)
        self.out_var.set(out_path)
        self.status.set("Compressing…")

        def progress_cb(done, total):
            self.status.set(f"Compressing… page {done}/{total}")

        def worker():
            try:
                before = os.path.getsize(self.pdf_path)
                compress_pdf_raster(self.pdf_path, out_path, dpi=dpi, jpeg_quality=q, grayscale=gray, progress_cb=progress_cb)
                after = os.path.getsize(out_path) if os.path.exists(out_path) else 0
                ratio = (after / before) if before else 1.0
                self.status.set(
                    f"Done!\nOriginal: {human_size(before)}\nCompressed: {human_size(after)}\n"
                    f"Ratio: {ratio:.2f}x ({(1-ratio)*100:.1f}% smaller)"
                )
            except Exception as e:
                self.status.set(f"Error: {e}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

def main():
    root = Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
