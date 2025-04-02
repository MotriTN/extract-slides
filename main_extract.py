import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import deque
import time
import datetime
import sys
import os
import shutil

def hide_console():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

class UltimateSlideProcessor:
    def __init__(self, frame_skip=30, duplicate_threshold=0.98):
        # Get correct directory (works for both .exe and script)
        self.current_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        self.video_path = self.current_dir / "video.mp4"
        self.output_folder = self.current_dir / "unique_slides"
        self.trainer_folder = self.current_dir / "trainer"
        
        # Create folders if they don't exist
        self.output_folder.mkdir(exist_ok=True)
        self.trainer_folder.mkdir(exist_ok=True)
        
        # Initialize OpenCV objects
        self.orb = cv2.ORB_create(nfeatures=2000, fastThreshold=5)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.duplicate_threshold = duplicate_threshold
        self.min_keypoints = 50
        self.frame_history = deque(maxlen=5)
        self.frame_skip = frame_skip
        self.should_stop = False
        
        # Load trained images
        self.trained_descriptors = []
        self.load_trained_model()

    def load_trained_model(self):
        self.trained_descriptors = []
        for img_path in self.trainer_folder.glob('*'):
            if img_path.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                img = cv2.imread(str(img_path))
                if img is not None:
                    des = self.extract_features(img)
                    if des is not None:
                        self.trained_descriptors.append(des)

    def extract_features(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (800, 600))
        kp, des = self.orb.detectAndCompute(gray, None)
        return des if des is not None and len(des) >= self.min_keypoints else None

    def calculate_similarity(self, frame1, frame2):
        small_size = (256, 256)
        frame1_small = cv2.resize(frame1, small_size)
        frame2_small = cv2.resize(frame2, small_size)
        gray1 = cv2.cvtColor(frame1_small, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2_small, cv2.COLOR_BGR2GRAY)
        return cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)[0][0]

    def is_duplicate(self, frame):
        return any(
            self.calculate_similarity(prev_frame, frame) >= self.duplicate_threshold
            for prev_frame in self.frame_history
        )

    def matches_trained_model(self, frame):
        if not self.trained_descriptors:
            return False
            
        frame_des = self.extract_features(frame)
        if frame_des is None:
            return False
            
        for trained_des in self.trained_descriptors:
            try:
                matches = self.matcher.match(frame_des, trained_des)
                similarity = len(matches) / min(len(frame_des), len(trained_des))
                if similarity >= 0.25:
                    return True
            except:
                continue
        return False

    def stop_processing(self):
        self.should_stop = True
    
    def process_video(self, progress_callback=None):
        if not self.video_path.exists():
            if progress_callback:
                progress_callback(0, 1, 0, 0, 0, "video.mp4 not found!")
            return False

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            if progress_callback:
                progress_callback(0, 1, 0, 0, 0, "Couldn't open video file!")
            return False

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        saved_count = duplicates = trained_matches = frame_count = 0
        self.should_stop = False
        self.start_time = time.time()

        while not self.should_stop:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % self.frame_skip == 0:
                if self.is_duplicate(frame):
                    duplicates += 1
                elif self.matches_trained_model(frame):
                    trained_matches += 1
                else:
                    output_path = self.output_folder / f"slide_{saved_count:05d}.jpg"
                    cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
                    saved_count += 1
                    self.frame_history.append(frame.copy())

            frame_count += 1
            if progress_callback:
                # Calculate timing metrics
                current_time = time.time()
                elapsed_seconds = current_time - self.start_time
                elapsed_str = str(datetime.timedelta(seconds=int(elapsed_seconds)))
                
                # Calculate remaining time
                if frame_count > 0 and elapsed_seconds > 0:
                    frames_per_second = frame_count / elapsed_seconds
                    remaining_seconds = (total_frames - frame_count) / frames_per_second
                    remaining_str = str(datetime.timedelta(seconds=int(remaining_seconds)))
                    speed_str = f"{frames_per_second:.1f} fps"
                else:
                    remaining_str = "--:--:--"
                    speed_str = "0.0 fps"
                
                progress_callback(frame_count, total_frames, saved_count, duplicates, trained_matches, elapsed_str, remaining_str, speed_str)

        cap.release()
        return not self.should_stop

class SlideProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ultimate Slide Processor")
        self.frame_skip = tk.IntVar(value=30)
        self.duplicate_threshold = tk.DoubleVar(value=0.98)
        self.processor = None
        self.processing = False
        self.video_path = ""

        self.create_widgets()
        self.check_initial_video()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title Label
        title_label = ttk.Label(main_frame, text="Ultimate Slide Processor", font=("Helvetica", 16))
        title_label.pack(pady=10)

        # File selection
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=10)
        ttk.Button(file_frame, text="Browse Video", command=self.browse_video).pack(side=tk.LEFT)
        self.file_status = ttk.Label(file_frame, text="No video selected", foreground="red")
        self.file_status.pack(side=tk.LEFT, padx=10)

        # Parameters Frame
        params_frame = ttk.LabelFrame(main_frame, text="Processing Parameters", padding=10)
        params_frame.pack(fill=tk.X, pady=10)
        
        # Frame Skip
        frame_skip_frame = ttk.Frame(params_frame)
        frame_skip_frame.pack(fill=tk.X, pady=5)
        ttk.Label(frame_skip_frame, text="Frame Skip Frequency:").pack(side=tk.LEFT)
        self.frame_skip_spinbox = ttk.Spinbox(frame_skip_frame, from_=1, to=100, textvariable=self.frame_skip, width=5)
        self.frame_skip_spinbox.pack(side=tk.RIGHT)

        # Similarity Threshold
        similarity_frame = ttk.Frame(params_frame)
        similarity_frame.pack(fill=tk.X, pady=5)
        ttk.Label(similarity_frame, text="Similarity Threshold:").pack(side=tk.LEFT)
        self.similarity_slider = ttk.Scale(similarity_frame, from_=0, to=1, variable=self.duplicate_threshold, orient="horizontal")
        self.similarity_slider.set(0.98)
        self.similarity_slider.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Current values display
        values_frame = ttk.Frame(params_frame)
        values_frame.pack(fill=tk.X, pady=5)
        self.frame_skip_value = ttk.Label(values_frame, text=f"Current: {self.frame_skip.get()} frames")
        self.frame_skip_value.pack()
        self.similarity_value = ttk.Label(values_frame, text=f"Current: {self.duplicate_threshold.get():.2f}")
        self.similarity_value.pack()

        # Progress Frame
        progress_frame = ttk.LabelFrame(main_frame, text="Processing Progress", padding=10)
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Progress Bar
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Stats Frame
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(stats_frame, text="Ready to process")
        self.progress_label.pack()
        
        self.stats_label = ttk.Label(stats_frame, text="Unique: 0 | Duplicates: 0 | Matches: 0")
        self.stats_label.pack()
        
        self.time_label = ttk.Label(progress_frame, 
                                  text="Elapsed: 00:00:00 | Remaining: --:--:-- | Speed: 0.0 fps",
                                  font=('Helvetica', 9))
        self.time_label.pack(pady=5)

        # Button Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        self.start_button = ttk.Button(button_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Processing", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Update values when changed
        self.frame_skip.trace_add("write", self.update_values)
        self.duplicate_threshold.trace_add("write", self.update_values)

    def update_values(self, *args):
        self.frame_skip_value.config(text=f"Current: {self.frame_skip.get()} frames")
        self.similarity_value.config(text=f"Current: {self.duplicate_threshold.get():.2f}")

    def browse_video(self):
        if filename := filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov")]):
            self.video_path = Path(filename)
            self.file_status.config(text=f"Loaded: {filename}", foreground="green")

    def start_processing(self):
        if not self.video_path:
            messagebox.showwarning("Error", "Please select a video file first")
            return
            
        if self.processing:
            return
            
        self.processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Reset progress bar and timing displays
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Starting processing...")
        self.stats_label.config(text="Unique: 0 | Duplicates: 0 | Matches: 0")
        self.time_label.config(text="Elapsed: 00:00:00 | Remaining: --:--:-- | Speed: 0.0 fps")
        
        self.processor = UltimateSlideProcessor(
            frame_skip=self.frame_skip.get(),
            duplicate_threshold=self.duplicate_threshold.get()
        )
        self.processor.video_path = self.video_path
        
        # Run processing in a separate thread
        import threading
        processing_thread = threading.Thread(
            target=self.run_processing, 
            daemon=True
        )
        processing_thread.start()

    def run_processing(self):
        completed = self.processor.process_video(progress_callback=self.update_progress)
        self.root.after(0, self.processing_complete, completed)

    def update_progress(self, current, total, unique, duplicates, matches, elapsed_str, remaining_str, speed_str):
        progress = (current / total) * 100
        self.progress_bar["value"] = progress
        
        # Update all labels
        self.progress_label.config(text=f"Processing: {current}/{total} frames ({progress:.1f}%)")
        self.stats_label.config(text=f"Unique: {unique} | Duplicates: {duplicates} | Matches: {matches}")
        self.time_label.config(text=f"Elapsed: {elapsed_str} | Remaining: {remaining_str} | Speed: {speed_str}")
        
        # Force GUI update
        self.root.update_idletasks()

    def stop_processing(self):
        if self.processor and self.processing:
            self.processor.stop_processing()
            self.stop_button.config(state=tk.DISABLED)
            self.progress_label.config(text="Stopping...")

    def processing_complete(self, completed):
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if completed:
            self.progress_label.config(text="Processing completed successfully!")
            messagebox.showinfo("Processing Complete", "Video processing completed successfully!")
        else:
            self.progress_label.config(text="Processing stopped by user")
            messagebox.showinfo("Processing Stopped", "Video processing was stopped by user")

    def check_initial_video(self):
        default_path = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        if (default_path / "video.mp4").exists():
            self.video_path = default_path / "video.mp4"
            self.file_status.config(text="Found video.mp4", foreground="green")

if __name__ == "__main__":
    hide_console()
    root = tk.Tk()
    app = SlideProcessorApp(root)
    root.mainloop()
