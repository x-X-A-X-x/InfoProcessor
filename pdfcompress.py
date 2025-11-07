import os
import shutil
import subprocess
import sys
import threading
from tkinter import Tk, Label, Button, Scale, HORIZONTAL, filedialog, StringVar, Entry, IntVar, Checkbutton

# ---------- Ghostscript helper ----------
def find_ghostscript():
    # Try common executable names
    candidates = ["gs", "gswin64c", "gswin32c"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None

# Build Ghostscript command
def build_gs_cmd(gs_path, input_pdf, output_pdf, dpi, jpeg_quality, use_pdfsettings):
    """
    dpi: target DPI for downsampling images
    jpeg_quality: 30..95 (JPEG Q factor)
    use_pdfsettings: if True, map a few presets for convenience (ignored here but kept for expansion)
    """
    # Core downsampling options for color/gray/mono images
    # -dJPEGQ applies to DCTEncode (JPEG) compression
    # We force downsample + JPEG where possible, keeping vector text/shapes intact.
    cmd = [
        gs_path,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",

        # Enable downsampling
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",

        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={dpi}",

        # Choose thresholds where downsampling applies
        f"-dColorImageDownsampleThreshold=1.0",
        f"-dGrayImageDownsampleThreshold=1.0",
        f"-dMonoImageDownsampleThreshold=1.0",

        # Use bicubic / average for decent quality; "Subsample" is fastest/smallest but more lossy
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",

        # JPEG quality for images (where applicable)
        f"-dJPEGQ={jpeg_quality}",

        # Try to recompress embedded images with JPEG when possible
        "-dAutoFilterColorImages=true",
        "-dAutoFilterGrayImages=true",
        "-dEncodeColorImages=true",
        "-dEncodeGrayImages=true",
        "-dEncodeMonoImages=true",

        # Output file
        f"-sOutputFile={output_pdf}",
        input_pdf
    ]
    return cmd

# ---------- UI logic ----------
class PDFCompressorApp:
    def __init__(self, master):
        self.master = master
        master.title("PDF Compressor (Ghostscript)")

        # Paths / status
        self.pdf_path = None
        self.gs_path = find_ghostscript()

        self.status_var = StringVar(value="Select a PDF to start.")
        self.selected_pdf_var = StringVar(value="No file selected")
        self.gs_var = StringVar(value=self.gs_path or "Not found (click 'Locate Ghostscript')")
        self.outfile_var = StringVar(value="-")

        # DPI slider
        Label(master, text="Target DPI (lower = smaller):").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        self.dpi_slider = Scale(master, from_=72, to=300, orient=HORIZONTAL, length=300)
        self.dpi_slider.set(150)
        self.dpi_slider.grid(row=0, column=1, padx=10, pady=(10, 0))

        # JPEG quality slider
        Label(master, text="JPEG Quality (30–95):").grid(row=1, column=0, sticky="w", padx=10)
        self.quality_slider = Scale(master, from_=30, to=95, orient=HORIZONTAL, length=300)
        self.quality_slider.set(70)
        self.quality_slider.grid(row=1, column=1, padx=10)

        # Use preset toggle (reserved for future use)
        self.use_preset = IntVar(value=0)
        self.preset_chk = Checkbutton(master, text="(Optional) Use preset tuning", variable=self.use_preset)
        self.preset_chk.grid(row=2, column=1, sticky="w", padx=10)

        # PDF selection
        Button(master, text="Choose PDF…", command=self.choose_pdf).grid(row=3, column=0, padx=10, pady=(10, 0), sticky="w")
        Label(master, textvariable=self.selected_pdf_var, wraplength=420).grid(row=3, column=1, padx=10, pady=(10, 0), sticky="w")

        # Ghostscript detection / selection
        Button(master, text="Locate Ghostscript…", command=self.choose_gs).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        Label(master, textvariable=self.gs_var, wraplength=420, fg="#444").grid(row=4, column=1, padx=10, pady=5, sticky="w")

        # Compress button
        Button(master, text="Compress PDF", command=self.compress_clicked).grid(row=5, column=0, padx=10, pady=10, sticky="w")

        # Output path
        Label(master, text="Output file:").grid(row=6, column=0, padx=10, sticky="w")
        Label(master, textvariable=self.outfile_var, wraplength=420).grid(row=6, column=1, padx=10, sticky="w")

        # Status
        Label(master, textvariable=self.status_var, fg="#006400", wraplength=520, justify="left").grid(row=7, column=0, columnspan=2, padx=10, pady=(5, 12), sticky="w")

        # Make UI tidy
        for i in range(2):
            master.grid_columnconfigure(i, weight=1)

    def choose_pdf(self):
        filetypes = [("PDF files", "*.pdf")]
        path = filedialog.askopenfilename(title="Select PDF", filetypes=filetypes)
        if path:
            self.pdf_path = path
            self.selected_pdf_var.set(path)
            self.status_var.set("Ready to compress.")

    def choose_gs(self):
        title = "Locate Ghostscript executable (gs / gswin64c.exe / gswin32c.exe)"
        path = filedialog.askopenfilename(title=title)
        if path:
            self.gs_path = path
            self.gs_var.set(path)
            self.status_var.set("Ghostscript set.")

    def compress_clicked(self):
        if not self.pdf_path:
            self.status_var.set("Please choose a PDF first.")
            return
        if not self.gs_path or not os.path.isfile(self.gs_path):
            # try again to find it automatically
            self.gs_path = find_ghostscript()
            if not self.gs_path:
                self.status_var.set("Ghostscript not found. Click 'Locate Ghostscript…' and select it.")
                self.gs_var.set("Not found")
                return
            self.gs_var.set(self.gs_path)

        dpi = int(self.dpi_slider.get())
        jpeg_q = int(self.quality_slider.get())

        in_path = self.pdf_path
        base, ext = os.path.splitext(in_path)
        out_path = f"{base}_compressed_{dpi}dpi.pdf"

        self.outfile_var.set(out_path)
        self.status_var.set("Compressing… this may take a moment.")

        # Run in background thread to keep UI responsive
        t = threading.Thread(target=self._compress_worker, args=(self.gs_path, in_path, out_path, dpi, jpeg_q))
        t.daemon = True
        t.start()

    def _compress_worker(self, gs, in_path, out_path, dpi, jpeg_q):
        try:
            # Build and run
            cmd = build_gs_cmd(gs, in_path, out_path, dpi, jpeg_q, use_pdfsettings=False)
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if proc.returncode != 0 or not os.path.exists(out_path):
                err = proc.stderr.decode(errors="ignore").strip()
                self.status_var.set(f"Compression failed.\n{err[:500]}")
                return

            # Report sizes
            before = os.path.getsize(in_path)
            after = os.path.getsize(out_path)
            ratio = (after / before) if before > 0 else 0
            human_before = self._format_size(before)
            human_after = self._format_size(after)

            self.status_var.set(
                f"Done!\n"
                f"Original: {human_before}\n"
                f"Compressed: {human_after}\n"
                f"Ratio: {ratio:.2f}x ({(1-ratio)*100:.1f}% smaller)"
            )
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    @staticmethod
    def _format_size(num_bytes):
        for unit in ["B", "KB", "MB", "GB"]:
            if num_bytes < 1024.0:
                return f"{num_bytes:.2f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.2f} TB"

def main():
    root = Tk()
    app = PDFCompressorApp(root)
    root.resizable(False, False)
    root.mainloop()

if __name__ == "__main__":
    main()
