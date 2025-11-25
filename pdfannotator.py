#pip install pymupdf pillow
import tkinter as tk
from tkinter import filedialog, messagebox
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import json
import os

class PDFAnnotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Annotator - Canva-style Text Boxes")

        # PDF-related
        self.doc = None
        self.pdf_path = None
        self.page_index = 0
        self.page_width = None
        self.page_height = None
        self.display_width = None
        self.display_height = None
        self.scale_x = 1.0  # PDF -> display
        self.scale_y = 1.0

        # Annotation management
        self.annotations = []  # list of dicts
        self.next_ann_id = 1   # unique id per annotation

        # Drag/resize state
        self.dragging = False
        self.drag_mode = None    # "move" or "resize"
        self.drag_ann_id = None
        self.drag_handle = None  # which handle name
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_orig_box = None  # (x1,y1,x2,y2) in display coords

        # ---- UI ----
        self.create_menu()
        self.create_toolbar()
        self.create_canvas()

    # ---------- UI ----------
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

        # Text content
        tk.Label(toolbar, text="Text:").pack(side=tk.LEFT, padx=2)
        self.text_entry = tk.Entry(toolbar, width=30)
        self.text_entry.pack(side=tk.LEFT, padx=2)

        # Initial font size
        tk.Label(toolbar, text="Start Size:").pack(side=tk.LEFT, padx=2)
        self.size_spin = tk.Spinbox(toolbar, from_=6, to=72, width=5)
        self.size_spin.delete(0, tk.END)
        self.size_spin.insert(0, "18")
        self.size_spin.pack(side=tk.LEFT, padx=2)

        # Color
        tk.Label(toolbar, text="Color:").pack(side=tk.LEFT, padx=2)
        self.color_var = tk.StringVar(value="black")
        colors = ["black", "red", "blue", "green", "orange", "purple"]
        tk.OptionMenu(toolbar, self.color_var, *colors).pack(side=tk.LEFT, padx=2)

        # Page navigation
        self.prev_btn = tk.Button(toolbar, text="<< Prev Page", command=self.prev_page)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = tk.Button(toolbar, text="Next Page >>", command=self.next_page)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        self.page_label = tk.Label(toolbar, text="Page: - / -")
        self.page_label.pack(side=tk.LEFT, padx=10)

    def create_canvas(self):
        self.canvas = tk.Canvas(self, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Mouse bindings
        self.canvas.bind("<Button-1>", self.on_left_button_down)
        self.canvas.bind("<B1-Motion>", self.on_left_button_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_button_up)
        self.canvas.bind("<Button-3>", self.on_right_button_down)

    # ---------- PDF HANDLING ----------
    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
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
        self.next_ann_id = 1
        self.render_page()
        self.update_page_label()

    def render_page(self):
        if not self.doc:
            return

        page = self.doc[self.page_index]
        self.page_width = page.rect.width
        self.page_height = page.rect.height

        # render with zoom for better quality
        zoom = 1.5
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        self.display_width = pix.width
        self.display_height = pix.height

        # PDF -> display scale
        self.scale_x = self.display_width / self.page_width
        self.scale_y = self.display_height / self.page_height

        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.page_photo = ImageTk.PhotoImage(image)

        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.page_photo, tags=("page_img",))

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

    # ---------- ANNOTATION HELPERS ----------
    def color_name_to_rgb(self, name):
        mapping = {
            "black": (0, 0, 0),
            "red": (1, 0, 0),
            "blue": (0, 0, 1),
            "green": (0, 1, 0),
            "orange": (1, 0.5, 0),
            "purple": (0.5, 0, 0.5),
        }
        return mapping.get(name, (0, 0, 0))

    def get_annotation_by_id(self, ann_id):
        for ann in self.annotations:
            if ann["id"] == ann_id:
                return ann
        return None

    def get_ann_id_from_item(self, item_id):
        tags = self.canvas.gettags(item_id)
        for t in tags:
            if t.startswith("ann_"):
                try:
                    return int(t.split("_", 1)[1])
                except ValueError:
                    pass
        return None

    def get_handle_from_item(self, item_id):
        tags = self.canvas.gettags(item_id)
        for t in tags:
            if t.startswith("handle_"):
                return t.split("_", 1)[1]
        return None

    # Create new annotation (click on blank area)
    def create_annotation(self, x_disp, y_disp):
        if not self.doc:
            return

        text = self.text_entry.get().strip()
        if not text:
            messagebox.showinfo("Info", "Enter text in the Text field first.")
            return

        try:
            base_font_size = int(self.size_spin.get())
        except ValueError:
            base_font_size = 18

        # default box size based on font size
        default_height_disp = max(20, int(base_font_size * 1.5))
        default_width_disp = 200

        x1 = x_disp
        y1 = y_disp
        x2 = x1 + default_width_disp
        y2 = y1 + default_height_disp

        # display -> PDF coords
        x_pdf = x1 / self.scale_x
        y_pdf = y1 / self.scale_y
        w_pdf = (x2 - x1) / self.scale_x
        h_pdf = (y2 - y1) / self.scale_y

        color_name = self.color_var.get()
        color_rgb = self.color_name_to_rgb(color_name)

        ann = {
            "id": self.next_ann_id,
            "page": self.page_index,
            "x_pdf": x_pdf,
            "y_pdf": y_pdf,
            "w_pdf": w_pdf,
            "h_pdf": h_pdf,
            "text": text,
            "font_size": base_font_size,
            "color_name": color_name,
            "color_rgb": color_rgb,
        }
        self.next_ann_id += 1
        self.annotations.append(ann)
        self.create_canvas_items_for_ann(ann)

    def draw_annotations_for_current_page(self):
        for ann in self.annotations:
            if ann["page"] == self.page_index:
                self.create_canvas_items_for_ann(ann)

    def create_canvas_items_for_ann(self, ann):
        tag_ann = f"ann_{ann['id']}"

        # PDF -> display box
        x1 = ann["x_pdf"] * self.scale_x
        y1 = ann["y_pdf"] * self.scale_y
        x2 = x1 + ann["w_pdf"] * self.scale_x
        y2 = y1 + ann["h_pdf"] * self.scale_y

        # dynamic font size from box height (Canva-style)
        box_height = max(10, y2 - y1)
        ann["font_size"] = max(6, int(box_height / 1.5))

        # color
        r, g, b = ann["color_rgb"]
        color_hex = "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

        # outer rectangle
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline=color_hex,
            width=1,
            tags=(tag_ann, "textbox_rect", "ann_item")
        )

        # text inside with padding
        pad = 4
        self.canvas.create_text(
            x1 + pad, y1 + pad,
            text=ann["text"],
            fill=color_hex,
            font=("Helvetica", ann["font_size"]),
            anchor=tk.NW,
            tags=(tag_ann, "textbox_text", "ann_item")
        )

        # 6 resize handles: tl, tc, tr, bl, bc, br
        handles = {
            "tl": (x1, y1),
            "tc": ((x1 + x2) / 2, y1),
            "tr": (x2, y1),
            "bl": (x1, y2),
            "bc": ((x1 + x2) / 2, y2),
            "br": (x2, y2),
        }
        size = 5
        for name, (hx, hy) in handles.items():
            self.canvas.create_rectangle(
                hx - size, hy - size, hx + size, hy + size,
                outline=color_hex,
                fill=color_hex,
                tags=(tag_ann, "textbox_handle", "ann_item", f"handle_{name}")
            )

    # ---------- MOUSE EVENTS ----------
    def on_left_button_down(self, event):
        if not self.doc:
            return

        item = self.canvas.find_withtag("current")
        if item:
            item = item[0]
            tags = self.canvas.gettags(item)
            if "ann_item" in tags:
                # Clicked on existing annotation -> move or resize
                ann_id = self.get_ann_id_from_item(item)
                ann = self.get_annotation_by_id(ann_id)
                if not ann:
                    return

                handle = self.get_handle_from_item(item)
                if handle:
                    self.drag_mode = "resize"
                    self.drag_handle = handle
                else:
                    self.drag_mode = "move"
                    self.drag_handle = None

                self.dragging = True
                self.drag_ann_id = ann_id
                self.drag_start_x = event.x
                self.drag_start_y = event.y

                # current box in display coords
                x1 = ann["x_pdf"] * self.scale_x
                y1 = ann["y_pdf"] * self.scale_y
                x2 = x1 + ann["w_pdf"] * self.scale_x
                y2 = y1 + ann["h_pdf"] * self.scale_y
                self.drag_orig_box = (x1, y1, x2, y2)
                return

        # Clicked on empty space -> create new text box
        self.create_annotation(event.x, event.y)

    def on_left_button_drag(self, event):
        if not self.dragging or not self.doc:
            return

        ann = self.get_annotation_by_id(self.drag_ann_id)
        if not ann:
            return

        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        x1, y1, x2, y2 = self.drag_orig_box

        if self.drag_mode == "move":
            new_x1 = x1 + dx
            new_y1 = y1 + dy
            new_x2 = x2 + dx
            new_y2 = y2 + dy
        elif self.drag_mode == "resize":
            new_x1, new_y1, new_x2, new_y2 = x1, y1, x2, y2
            handle = self.drag_handle
            # change sides depending on which handle
            if handle == "tl":
                new_x1 = x1 + dx
                new_y1 = y1 + dy
            elif handle == "tc":
                new_y1 = y1 + dy
            elif handle == "tr":
                new_x2 = x2 + dx
                new_y1 = y1 + dy
            elif handle == "bl":
                new_x1 = x1 + dx
                new_y2 = y2 + dy
            elif handle == "bc":
                new_y2 = y2 + dy
            elif handle == "br":
                new_x2 = x2 + dx
                new_y2 = y2 + dy
        else:
            return

        # Minimum size
        min_w = 30
        min_h = 15
        if new_x2 - new_x1 < min_w:
            if self.drag_mode == "resize":
                if self.drag_handle in ("tl", "bl"):
                    new_x1 = new_x2 - min_w
                else:
                    new_x2 = new_x1 + min_w
        if new_y2 - new_y1 < min_h:
            if self.drag_mode == "resize":
                if self.drag_handle in ("tl", "tc", "tr"):
                    new_y1 = new_y2 - min_h
                else:
                    new_y2 = new_y1 + min_h

        # Update annotation (PDF coords + font size)
        self.update_annotation_from_display_box(ann, new_x1, new_y1, new_x2, new_y2)

        # Redraw that annotation only
        tag_ann = f"ann_{ann['id']}"
        self.canvas.delete(tag_ann)
        self.create_canvas_items_for_ann(ann)

    def on_left_button_up(self, event):
        self.dragging = False
        self.drag_mode = None
        self.drag_ann_id = None
        self.drag_handle = None
        self.drag_orig_box = None

    def on_right_button_down(self, event):
        if not self.doc:
            return
        item = self.canvas.find_withtag("current")
        if not item:
            return
        item = item[0]
        tags = self.canvas.gettags(item)
        if "ann_item" not in tags:
            return

        ann_id = self.get_ann_id_from_item(item)
        ann = self.get_annotation_by_id(ann_id)
        if not ann:
            return

        # Right-click delete
        tag_ann = f"ann_{ann_id}"
        self.canvas.delete(tag_ann)
        self.annotations = [a for a in self.annotations if a["id"] != ann_id]

    def update_annotation_from_display_box(self, ann, x1, y1, x2, y2):
        # display -> PDF
        ann["x_pdf"] = x1 / self.scale_x
        ann["y_pdf"] = y1 / self.scale_y
        ann["w_pdf"] = (x2 - x1) / self.scale_x
        ann["h_pdf"] = (y2 - y1) / self.scale_y

        # dynamic font size from height
        height = max(10, y2 - y1)
        ann["font_size"] = max(6, int(height / 1.5))

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
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
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
            messagebox.showerror("Error", "Original PDF not found.")
            return

        try:
            self.doc = fitz.open(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PDF:\n{e}")
            return

        self.pdf_path = pdf_path
        self.annotations = project_data.get("annotations", [])

        # Restore next_ann_id
        max_id = 0
        for ann in self.annotations:
            if "id" in ann and isinstance(ann["id"], int):
                max_id = max(max_id, ann["id"])
        self.next_ann_id = max_id + 1 if max_id > 0 else 1

        self.page_index = 0
        self.render_page()
        self.update_page_label()
        messagebox.showinfo("Loaded", "Project loaded successfully.")

    # ---------- EXPORT TO REAL PDF ----------
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

        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open original PDF:\n{e}")
            return

        try:
            for ann in self.annotations:
                page = doc[ann["page"]]
                x = ann["x_pdf"]
                y = ann["y_pdf"]
                fontsize = ann.get("font_size", 12)
                r, g, b = ann["color_rgb"]
                page.insert_text(
                    fitz.Point(x, y),
                    ann["text"],
                    fontsize=fontsize,
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
