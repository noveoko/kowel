import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
from pathlib import Path
import threading
import re
import tempfile
import queue
import time

class PhotoStackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Focus Stacker")
        self.root.geometry("800x600")
        
        # Variables
        self.input_files = []
        self.output_file = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.process_queue = queue.Queue()
        
        # Tool paths
        self.align_tool = r"C:\Program Files\Hugin\bin\align_image_stack.exe"
        self.enfuse_tool = r"C:\Program Files\Hugin\bin\enfuse.exe"
        
        # Verify tools exist
        missing_tools = []
        if not os.path.exists(self.align_tool):
            missing_tools.append("align_image_stack.exe")
        if not os.path.exists(self.enfuse_tool):
            missing_tools.append("enfuse.exe")
            
        if missing_tools:
            messagebox.showerror("Error", 
                f"Required tools not found: {', '.join(missing_tools)}\n"
                "Please install Hugin first.")
            root.quit()
            return
            
        # Create GUI elements
        self.create_widgets()
        
        # Start progress monitor
        self.monitor_progress()
        
    def create_widgets(self):
        # Input file selection
        input_frame = ttk.LabelFrame(self.root, text="Input Images", padding=10)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Add Files", command=self.add_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Add Folder", command=self.add_folder).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_files).pack(side="left", padx=5)
        
        # File list
        self.file_list = tk.Listbox(input_frame, height=6, selectmode="extended")
        self.file_list.pack(fill="both", expand=True, pady=5)
        
        # Add scrollbar to file list
        list_scroll = ttk.Scrollbar(input_frame, command=self.file_list.yview)
        list_scroll.pack(side="right", fill="y")
        self.file_list.config(yscrollcommand=list_scroll.set)
        
        # Output file selection
        output_frame = ttk.LabelFrame(self.root, text="Output Image", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(output_frame, textvariable=self.output_file, width=70).pack(side="left", padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side="left")
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(progress_frame, textvariable=self.status_var).pack()
        
        # Control buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Start Processing", command=self.start_processing).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_processing).pack(side="left")
        
        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, width=70)
        self.log_text.pack(fill="both", expand=True)
        
        # Add scrollbar to log
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

    def add_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[
                ('Image files', '*.jpg;*.jpeg;*.png;*.tif;*.tiff'),
                ('All files', '*.*')
            ]
        )
        if files:
            self.input_files.extend(files)
            self.update_file_list()
    
    def add_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            path = Path(directory)
            files = [str(f) for f in path.glob("*") 
                    if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff')]
            self.input_files.extend(files)
            self.update_file_list()
    
    def clear_files(self):
        self.input_files.clear()
        self.update_file_list()
    
    def update_file_list(self):
        self.file_list.delete(0, tk.END)
        for file in self.input_files:
            self.file_list.insert(tk.END, os.path.basename(file))
    
    def browse_output(self):
        file_types = [
            ('TIFF files', '*.tiff;*.tif'),
            ('JPEG files', '*.jpg;*.jpeg'),
            ('PNG files', '*.png'),
            ('All files', '*.*')
        ]
        filename = filedialog.asksaveasfilename(
            defaultextension=".tif",
            filetypes=file_types
        )
        if filename:
            self.output_file.set(filename)
    
    def log(self, message):
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
    
    def monitor_progress(self):
        """Monitor progress messages from the processing thread"""
        try:
            while True:
                try:
                    message = self.process_queue.get_nowait()
                    if isinstance(message, tuple):
                        command, value = message
                        if command == "progress":
                            self.progress_var.set(value)
                        elif command == "status":
                            self.status_var.set(value)
                        elif command == "log":
                            self.log(value)
                    self.process_queue.task_done()
                except queue.Empty:
                    break
        finally:
            self.root.after(100, self.monitor_progress)
    
    def start_processing(self):
        if not self.input_files:
            messagebox.showerror("Error", "Please add input images!")
            return
            
        if not self.output_file.get():
            messagebox.showerror("Error", "Please select output file!")
            return
            
        # Start processing in a separate thread
        self.processing_thread = threading.Thread(target=self.process_images)
        self.processing_thread.start()
    
    def cancel_processing(self):
        if hasattr(self, 'current_process'):
            self.current_process.terminate()
        self.process_queue.put(("status", "Cancelled"))
        self.process_queue.put(("progress", 0))
    
    def run_process(self, cmd, desc):
        """Run a process and monitor its output"""
        try:
            self.process_queue.put(("log", f"Running {desc}..."))
            self.process_queue.put(("log", f"Command: {' '.join(cmd)}"))
            
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            while True:
                output = self.current_process.stdout.readline()
                if output == '' and self.current_process.poll() is not None:
                    break
                if output:
                    self.process_queue.put(("log", output.strip()))
                    # Try to parse progress information
                    if "%" in output:
                        try:
                            progress = float(re.search(r'(\d+)%', output).group(1))
                            self.process_queue.put(("progress", progress))
                        except:
                            pass
            
            rc = self.current_process.poll()
            if rc != 0:
                error = self.current_process.stderr.read()
                raise subprocess.CalledProcessError(rc, cmd, error)
                
            return True
            
        except subprocess.CalledProcessError as e:
            self.process_queue.put(("log", f"Error: {e.stderr}"))
            raise
            
        except Exception as e:
            self.process_queue.put(("log", f"Error: {str(e)}"))
            raise
    
    def process_images(self):
        """Main processing function that handles both alignment and stacking"""
        try:
            # Create temp directory for aligned images
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Align images
                self.process_queue.put(("status", "Aligning images..."))
                self.process_queue.put(("progress", 0))
                
                align_cmd = [
                    self.align_tool,
                    '-a', str(temp_path / 'aligned_'),
                    '-C',  # auto crop
                    '--gpu',  # use GPU if available
                ]
                align_cmd.extend(self.input_files)
                
                self.run_process(align_cmd, "image alignment")
                
                # Find aligned images
                aligned_files = sorted(temp_path.glob("aligned_*.tif"))
                if not aligned_files:
                    raise Exception("No aligned images found!")
                
                # Step 2: Focus stack
                self.process_queue.put(("status", "Focus stacking..."))
                self.process_queue.put(("progress", 50))
                
                stack_cmd = [
                    self.enfuse_tool,
                    '--output', self.output_file.get(),
                    '--exposure-weight=0',
                    '--saturation-weight=0',
                    '--contrast-weight=1',
                    '--contrast-window-size=5',
                    '--contrast-edge-scale=0.3',
                    '--hard-mask',
                ]
                stack_cmd.extend(str(f) for f in aligned_files)
                
                self.run_process(stack_cmd, "focus stacking")
                
                self.process_queue.put(("status", "Processing complete!"))
                self.process_queue.put(("progress", 100))
                messagebox.showinfo("Success", "Focus stacking completed successfully!")
                
        except Exception as e:
            self.process_queue.put(("status", "Error during processing"))
            self.process_queue.put(("progress", 0))
            messagebox.showerror("Error", str(e))
        
        finally:
            self.process_queue.put(("progress", 0))

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoStackerGUI(root)
    root.mainloop()