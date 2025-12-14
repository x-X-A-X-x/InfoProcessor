#pip install pymupdf pillow
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import json
import os

class PDFAnnotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple PDF Annotator")

        # PDF-related
        self.doc = None
        self.pdf_path = None
        self.page_index = 0
        self.page_image = None
        self.page_photo = None
        self.page_width = None
        self.page_height = None
        self.display_width = None
        self.display_height = None

        # List of annotations:
        # {page, x_pdf, y_pdf, text, font_size, color_name, color_rgb}
        self.annotations = []

        # ---- UI ----
        self.create_menu()
        self.create_toolbar()
        self.create_canvas()

    # ---------- UI SETUP ----------
    def create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open PDF", command=self.open_pdf)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Load Project", command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label="Export Annotated PDF", command=self.export_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.quit)

        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def create_toolbar(self):
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Text to place
        tk.Label(toolbar, text="Text:").pack(side=tk.LEFT, padx=2)
        self.text_entry = tk.Entry(toolbar, width=30)
        self.text_entry.pack(side=tk.LEFT, padx=2)

        # Font size
        tk.Label(toolbar, text="Size:").pack(side=tk.LEFT, padx=2)
        self.size_spin = tk.Spinbox(toolbar, from_=6, to=72, width=5)
        self.size_spin.delete(0, tk.END)
        self.size_spin.insert(0, "14")
        self.size_spin.pack(side=tk.LEFT, padx=2)

        # Color dropdown
        tk.Label(toolbar, text="Color:").pack(side=tk.LEFT, padx=2)
        self.color_var = tk.StringVar(value="black")
        colors = ["black", "red", "blue", "green", "orange", "purple"]
        self.color_menu = tk.OptionMenu(toolbar, self.color_var, *colors)
        self.color_menu.pack(side=tk.LEFT, padx=2)

        # Page navigation (prev/next)
        self.prev_btn = tk.Button(toolbar, text="<< Prev Page", command=self.prev_page)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = tk.Button(toolbar, text="Next Page >>", command=self.next_page)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # Current page label
        self.page_label = tk.Label(toolbar, text="Page: - / -")
        self.page_label.pack(side=tk.LEFT, padx=10)

    def create_canvas(self):
        self.canvas = tk.Canvas(self, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    # ---------- PDF HANDLING ----------
    def open_pdf(self):
        path = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf")]
        )
        if not path:
            return

        try:
            self.doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PDF:\n{e}")
            return

        self.pdf_path = path
        self.page_index = 0
        self.annotations = []
        self.render_page()
        self.update_page_label()

    def render_page(self):
        if not self.doc:
            return

        page = self.doc[self.page_index]
        self.page_width = page.rect.width
        self.page_height = page.rect.height

        # Zoom factor for better quality
        zoom = 1.5
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        self.display_width = pix.width
        self.display_height = pix.height

        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.page_image = image
        self.page_photo = ImageTk.PhotoImage(image)

        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.page_photo, tags="page_img")

        # Draw annotations for this page
        self.draw_annotations_for_current_page()

    def update_page_label(self):
        if not self.doc:
            self.page_label.config(text="Page: - / -")
        else:
            self.page_label.config(text=f"Page: {self.page_index + 1} / {len(self.doc)}")

    def prev_page(self):
        if not self.doc:
            return
        if self.page_index > 0:
            self.page_index -= 1
            self.render_page()
            self.update_page_label()

    def next_page(self):
        if not self.doc:
            return
        if self.page_index < len(self.doc) - 1:
            self.page_index += 1
            self.render_page()
            self.update_page_label()

    # ---------- ANNOTATIONS ----------
    def on_canvas_click(self, event):
        if not self.doc:
            return

        text = self.text_entry.get().strip()
        if not text:
            messagebox.showinfo("Info", "Enter text in the Text field first.")
            return

        try:
            font_size = int(self.size_spin.get())
        except ValueError:
            messagebox.showerror("Error", "Font size must be a number.")
            return

        color_name = self.color_var.get()
        color_rgb = self.color_name_to_rgb(color_name)

        # Convert canvas (display) coordinates to PDF coordinates
        x_display = event.x
        y_display = event.y

        # Protection if display sizes are None
        if not self.display_width or not self.display_height:
            return

        # Scale factors: PDF coords vs display coords
        scale_x = self.page_width / self.display_width
        scale_y = self.page_height / self.display_height

        x_pdf = x_display * scale_x
        y_pdf = y_display * scale_y

        ann = {
            "page": self.page_index,
            "x_pdf": x_pdf,
            "y_pdf": y_pdf,
            "text": text,
            "font_size": font_size,
            "color_name": color_name,
            "color_rgb": color_rgb,  # (r, g, b) in 0–1
        }
        self.annotations.append(ann)

        # Draw immediately on canvas
        self.draw_single_annotation(ann)

    def draw_annotations_for_current_page(self):
        for ann in self.annotations:
            if ann["page"] == self.page_index:
                self.draw_single_annotation(ann)

    def draw_single_annotation(self, ann):
        # Convert PDF coords to display coords
        scale_x = self.display_width / self.page_width
        scale_y = self.display_height / self.page_height

        x_display = ann["x_pdf"] * scale_x
        y_display = ann["y_pdf"] * scale_y

        r, g, b = ann["color_rgb"]
        # Convert 0–1 RGB to hex for Tkinter
        color_hex = "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )

        self.canvas.create_text(
            x_display,
            y_display,
            text=ann["text"],
            fill=color_hex,
            font=("Helvetica", ann["font_size"]),
            anchor=tk.NW,
            tags="annotation",
        )

    @staticmethod
    def color_name_to_rgb(name):
        # Return RGB in 0–1 for PyMuPDF
        mapping = {
            "black": (0, 0, 0),
            "red": (1, 0, 0),
            "blue": (0, 0, 1),
            "green": (0, 0, 1 * 0),  # (0,1,0) but keep pattern explicit
            "orange": (1, 0.5, 0),
            "purple": (0.5, 0, 0.5),
        }
        if name == "green":
            return (0, 1, 0)
        return mapping.get(name, (0, 0, 0))

    # ---------- SAVE / LOAD PROJECT ----------
    def save_project(self):
        if not self.pdf_path:
            messagebox.showerror("Error", "No PDF loaded.")
            return

        project_data = {
            "pdf_path": self.pdf_path,
            "annotations": self.annotations,
        }

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=2)
            messagebox.showinfo("Saved", "Project saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save project:\n{e}")

    def load_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                project_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load project:\n{e}")
            return

        pdf_path = project_data.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror(
                "Error",
                "Original PDF not found. Make sure the PDF path in the project file exists."
            )
            return

        try:
            self.doc = fitz.open(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PDF:\n{e}")
            return

        self.pdf_path = pdf_path
        self.annotations = project_data.get("annotations", [])
        self.page_index = 0
        self.render_page()
        self.update_page_label()
        messagebox.showinfo("Loaded", "Project loaded successfully.")

    # ---------- EXPORT TO PDF ----------
    def export_pdf(self):
        if not self.doc or not self.annotations:
            messagebox.showerror("Error", "No PDF or annotations to export.")
            return

        export_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not export_path:
            return

        # Open original PDF again to avoid modifying in-place
        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open original PDF:\n{e}")
            return

        try:
            for ann in self.annotations:
                page = doc[ann["page"]]
                point = fitz.Point(ann["x_pdf"], ann["y_pdf"])
                r, g, b = ann["color_rgb"]
                page.insert_text(
                    point,
                    ann["text"],
                    fontsize=ann["font_size"],
                    fontname="helv",
                    fill=(r, g, b),
                )

            doc.save(export_path)
            doc.close()
            messagebox.showinfo("Exported", "Annotated PDF exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF:\n{e}")

if __name__ == "__main__":
    app = PDFAnnotator()
    app.mainloop()
