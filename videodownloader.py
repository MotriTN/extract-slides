from pytubefix import YouTube
from pytubefix.cli import on_progress
import subprocess
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
from datetime import datetime, timedelta

class YouTubeDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Mediocre YouTube Downloader")
        self.root.geometry("500x350")  # Slightly taller for time estimate
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("Arial", 10))
        self.style.configure("TButton", font=("Arial", 10))
        
        # Track download stats
        self.start_time = None
        self.last_bytes = 0
        
        # Create widgets
        self.create_widgets()
        
    def create_widgets(self):
        # URL Entry
        ttk.Label(self.root, text="YouTube URL:").pack(pady=(20, 5))
        self.url_entry = ttk.Entry(self.root, width=50)
        self.url_entry.pack()
        
        # Download Button
        self.download_btn = ttk.Button(
            self.root, 
            text="Download", 
            command=self.download_video
        )
        self.download_btn.pack(pady=20)
        
        # Progress Bar
        self.progress = ttk.Progressbar(
            self.root, 
            orient="horizontal", 
            length=300, 
            mode="determinate"
        )
        self.progress.pack()
        
        # Time remaining label
        self.time_label = ttk.Label(self.root, text="Estimated time: --")
        self.time_label.pack(pady=5)
        
        # Status Label
        self.status_label = ttk.Label(self.root, text="")
        self.status_label.pack(pady=5)
        
    def download_video(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
            
        try:
            self.download_btn.config(state="disabled")
            self.status_label.config(text="Connecting...")
            self.time_label.config(text="Estimated time: --")
            self.root.update()
            
            yt = YouTube(url, on_progress_callback=self.update_progress)
            self.status_label.config(text=f"Downloading: {yt.title[:50]}...")
            
            # Get video stream
            video_stream = (
                yt.streams.filter(progressive=False, file_extension='mp4', res="1080p").first() or
                yt.streams.filter(progressive=False, file_extension='mp4').order_by('resolution').desc().first()
            )
            
            if not video_stream:
                raise Exception("No suitable video stream found")
            
            # Get audio stream
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not audio_stream:
                raise Exception("No audio stream found")
            
            # Ask for save location
            save_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("MP4 files", "*.mp4")],
                initialfile=f"{yt.title[:30]}.mp4".replace("/", "-")
            )
            if not save_path:
                return
                
            # Reset progress tracking
            self.start_time = time.time()
            self.last_bytes = 0
            
            # Download video and audio
            self.status_label.config(text="Downloading video...")
            video_file = video_stream.download(filename="video.mp4")
            
            self.status_label.config(text="Downloading audio...")
            self.start_time = time.time()  # Reset timer for audio download
            self.last_bytes = 0
            audio_file = audio_stream.download(filename="audio_temp.mp4")
            
            # Combine streams
            self.status_label.config(text="Combining video and audio...")
            self.time_label.config(text="Estimated time: merging...")
            subprocess.run([
                'ffmpeg', '-i', video_file, '-i', audio_file,
                '-c:v', 'copy', '-c:a', 'aac',
                '-strict', 'experimental', save_path
            ], check=True)
            
            # Clean up
            os.remove(video_file)
            os.remove(audio_file)
            
            messagebox.showinfo("Success", f"Video saved as:\n{save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
        finally:
            self.download_btn.config(state="normal")
            self.progress["value"] = 0
            self.status_label.config(text="")
            self.time_label.config(text="Estimated time: --")
            
    def update_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size) * 100
        self.progress["value"] = percentage
        
        # Calculate download speed and time remaining
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        
        if elapsed_time > 0:
            download_speed = bytes_downloaded / elapsed_time  # bytes per second
            remaining_bytes = total_size - bytes_downloaded
            if download_speed > 0:
                remaining_time = remaining_bytes / download_speed
                # Format as HH:MM:SS or MM:SS
                if remaining_time > 3600:
                    time_str = str(timedelta(seconds=int(remaining_time)))
                else:
                    time_str = time.strftime("%M:%S", time.gmtime(remaining_time))
                self.time_label.config(text=f"Estimated time: {time_str}")
        
        self.root.update()

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()
