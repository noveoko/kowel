import tkinter as tk
from tkinter import filedialog
import cv2
from inference import get_model
from inference.core.utils.image_utils import load_image_bgr
import supervision as sv

class VideoStabilizer:
    def __init__(self, master):
        self.master = master
        master.title("Video Stabilizer")

        # Create the main container
        self.container = tk.Frame(master)
        self.container.pack(fill="both", expand=True)

        # Create the video preview canvas
        self.canvas = tk.Canvas(self.container, width=640, height=480)
        self.canvas.pack(padx=20, pady=20)

        # Create the "Select Video" button
        self.select_button = tk.Button(self.container, text="Select Video", command=self.select_video)
        self.select_button.pack(pady=10)

        # Initialize the video and ML model
        self.video = None
        self.model = get_model(model_id="yolov8n-640")

    def select_video(self):
        # Open a file dialog to select the video
        self.video_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.avi;*.mov")])
        if self.video_path:
            self.video = cv2.VideoCapture(self.video_path)
            self.stabilize_video()

    def stabilize_video(self):
        # Get the first frame and process it with the ML model
        ret, frame = self.video.read()
        image = load_image_bgr(frame)
        results = self.model.infer(image)[0]
        results = sv.Detections.from_inference(results)

        # Find the largest object (likely the reference point)
        if len(results) > 0:
            reference_box = max(results, key=lambda x: x.confidence)

            # Stabilize the video using the reference box
            while True:
                ret, frame = self.video.read()
                if not ret:
                    break

                image = load_image_bgr(frame)
                results = self.model.infer(image)[0]
                results = sv.Detections.from_inference(results)

                # Find the current position of the reference box
                for result in results:
                    if result.class_id == reference_box.class_id and result.confidence > reference_box.confidence:
                        reference_box = result
                        break

                # Calculate the offset and apply it to the frame
                offset_x = reference_box.x - image.shape[1] // 2
                offset_y = reference_box.y - image.shape[0] // 2
                stabilized_frame = cv2.warpAffine(frame, np.float32([[1, 0, -offset_x], [0, 1, -offset_y]]), (image.shape[1], image.shape[0]))

                # Display the stabilized frame on the canvas
                stabilized_image = cv2.cvtColor(stabilized_frame, cv2.COLOR_BGR2RGB)
                self.photo = tk.PhotoImage(width=640, height=480)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
                self.photo.put(stabilized_image.tobytes(), to=(0, 0))
                self.canvas.update()

        self.video.release()

root = tk.Tk()
app = VideoStabilizer(root)
root.mainloop()