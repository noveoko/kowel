import tkinter as tk
from tkinter import ttk, messagebox
import os
import replicate
import requests
from pathlib import Path
from dotenv import load_dotenv
import json

class TextureGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Brush Texture Generator")
        
        # Load environment variables
        load_dotenv()
        
        # Create config directory if it doesn't exist
        self.config_dir = Path.home() / '.texture_generator'
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / '.env'
        
        # Load API key if exists
        self.api_key = os.getenv('REPLICATE_API_TOKEN', '')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # API Key Section
        api_frame = ttk.LabelFrame(main_frame, text="API Configuration", padding="5")
        api_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(api_frame, text="Replicate API Key:").grid(row=0, column=0, pady=5)
        self.api_entry = ttk.Entry(api_frame, show="*", width=40)
        self.api_entry.grid(row=0, column=1, padx=5)
        self.api_entry.insert(0, self.api_key)
        
        ttk.Button(api_frame, text="Save API Key", command=self.save_api_key).grid(row=0, column=2, padx=5)
        
        # Texture Generation Section
        gen_frame = ttk.LabelFrame(main_frame, text="Texture Generation", padding="5")
        gen_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(gen_frame, text="Texture Description:").grid(row=0, column=0, pady=5)
        self.texture_entry = ttk.Entry(gen_frame, width=40)
        self.texture_entry.grid(row=0, column=1, padx=5)
        
        # Output Directory Section
        out_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="5")
        out_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(out_frame, text="Output Directory:").grid(row=0, column=0, pady=5)
        self.output_dir = tk.StringVar(value=str(Path.home() / "TextureOutput"))
        self.output_entry = ttk.Entry(out_frame, textvariable=self.output_dir, width=40)
        self.output_entry.grid(row=0, column=1, padx=5)
        
        # Generation Button
        ttk.Button(main_frame, text="Generate Texture", command=self.generate_texture).grid(row=3, column=0, columnspan=2, pady=10)
        
        # Progress Bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Status Label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=5, column=0, columnspan=2)

    def save_api_key(self):
        api_key = self.api_entry.get().strip()
        if api_key:
            # Save to .env file
            with open(self.config_file, 'w') as f:
                f.write(f'REPLICATE_API_TOKEN={api_key}')
            os.environ['REPLICATE_API_TOKEN'] = api_key
            messagebox.showinfo("Success", "API key saved successfully!")
        else:
            messagebox.showerror("Error", "Please enter an API key")

    def download_image(self, url, save_path):
        response = requests.get(url)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return save_path

    def generate_texture(self):
        # Check API key
        if not os.getenv('REPLICATE_API_TOKEN'):
            messagebox.showerror("Error", "Please set and save your API key first")
            return
            
        texture_type = self.texture_entry.get().strip()
        if not texture_type:
            messagebox.showerror("Error", "Please enter a texture description")
            return
            
        # Create output directory if it doesn't exist
        output_dir = Path(self.output_dir.get())
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Start progress bar
        self.progress.start()
        self.status_var.set("Generating texture...")
        self.root.update()
        
        try:
            # Generate the complete prompt
            base_prompt = """Studio overhead shot of {texture} surface in perfect 8K monochrome, captured with professional ring light creating circular gradient falloff. Central 70% shows crystal-clear {texture} detail with 10x10 visible pattern elements. Outer edges fade to pure black through professional light falloff. Museum-grade material photography, extreme detail preservation"""
            prompt = base_prompt.format(texture=texture_type)
            
            # Run the model
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "go_fast": True,
                    "megapixels": "1",
                    "num_outputs": 1,
                    "aspect_ratio": "1:1",
                    "output_format": "webp",
                    "output_quality": 80,
                    "num_inference_steps": 4
                }
            )
            
            if not output:
                raise Exception("No output received from API")
                
            # Get the image URL from the output
            image_url = output[0]
            
            # Download the image
            texture_name = f"brush_texture_{texture_type.replace(' ', '_')}.webp"
            save_path = output_dir / texture_name
            
            self.status_var.set("Downloading texture...")
            self.root.update()
            
            self.download_image(image_url, str(save_path))
            
            self.status_var.set(f"Texture saved to: {save_path}")
            messagebox.showinfo("Success", f"Texture generated and saved to:\n{save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate texture: {str(e)}")
            self.status_var.set("Error generating texture")
        
        finally:
            # Stop progress bar
            self.progress.stop()

def main():
    root = tk.Tk()
    app = TextureGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
