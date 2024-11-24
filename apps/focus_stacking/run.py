# run.py
import tkinter as tk
from focus_stacking.main import PhotoStackerGUI


def main():
    root = tk.Tk()
    root.title("Focus Stacking Tool")

    # Optional: Set a minimum window size
    root.minsize(800, 600)

    # Optional: Center the window on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 800
    window_height = 600
    center_x = int(screen_width / 2 - window_width / 2)
    center_y = int(screen_height / 2 - window_height / 2)
    root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    # Create the application
    app = PhotoStackerGUI(root, testing_mode=False)

    # Start the application
    root.mainloop()


if __name__ == "__main__":
    main()
