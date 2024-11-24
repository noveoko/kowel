import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk


class ImagePreviewWindow:
    def __init__(self, image_path):
        self.window = tk.Toplevel()
        self.window.title("Result Preview")
        self.current_image_path = image_path

        # Load and resize image to fit screen
        image = Image.open(image_path)

        # Get screen dimensions with some padding
        screen_width = self.window.winfo_screenwidth() - 100
        screen_height = self.window.winfo_screenheight() - 100

        # Calculate resize ratio while maintaining aspect ratio
        width_ratio = screen_width / image.width
        height_ratio = screen_height / image.height
        ratio = min(width_ratio, height_ratio)

        new_width = int(image.width * ratio)
        new_height = int(image.height * ratio)

        # Resize image
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(image)

        # Create canvas for image display with scrollbars
        self.canvas = tk.Canvas(
            self.window,
            width=min(new_width, screen_width),
            height=min(new_height, screen_height),
        )

        # Add scrollbars
        h_scroll = ttk.Scrollbar(
            self.window, orient="horizontal", command=self.canvas.xview
        )
        v_scroll = ttk.Scrollbar(
            self.window, orient="vertical", command=self.canvas.yview
        )

        # Configure canvas scrolling
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Grid layout
        self.canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        # Configure grid weights
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)

        # Create image on canvas
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Add button frame
        button_frame = ttk.Frame(self.window)
        button_frame.grid(row=2, column=0, columnspan=2, pady=5)

        # Add buttons
        ttk.Button(
            button_frame,
            text="Open in Default Viewer",
            command=lambda: os.startfile(image_path),
        ).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(
            side="left", padx=5
        )

        # Bind mousewheel for zooming
        self.canvas.bind("<Control-MouseWheel>", self.zoom)
        self.zoom_level = 1.0

        # Center window on screen
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.window.geometry(f"+{x}+{y}")

    def zoom(self, event):
        # Handle zoom with ctrl + mousewheel
        if event.delta > 0:
            # Zoom in
            self.zoom_level *= 1.1
        else:
            # Zoom out
            self.zoom_level /= 1.1

        # Get current image
        image = Image.open(self.current_image_path)

        # Calculate new size
        new_width = int(image.width * self.zoom_level)
        new_height = int(image.height * self.zoom_level)

        # Resize image
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Update PhotoImage
        self.photo = ImageTk.PhotoImage(image)

        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
