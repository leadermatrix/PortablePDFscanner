import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import os
import time
from PIL import Image, ImageTk
from datetime import datetime
import threading
import queue
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Import Raspberry Pi camera library
try:
    from picamera2 import Picamera2
    USING_PICAMERA = True
except ImportError:
    USING_PICAMERA = False
    print("Warning: picamera2 not found. Using OpenCV camera fallback.")

class PDFScannerApp:
    def __init__(self, window, window_title):
        # Main window setup
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1200x700")
        self.window.configure(bg="#f0f0f0")
        
        # Variables
        self.camera_active = False
        self.camera = None
        self.picam2 = None
        self.camera_thread = None
        self.frame_queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.captured_images = []
        self.current_image = None
        self.pages_scanned = 0
        self.capturing = False
        self.auto_mode = False
        self.auto_capture_thread = None
        self.current_doc_name = "Document"
        self.output_dir = f"scanned_document_{int(time.time())}"
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Status bar at the top
        self.status_frame = tk.Frame(self.window, bg="#e0e0e0", height=40)
        self.status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.pages_label = tk.Label(self.status_frame, text="Pages Scanned: 0", bg="#e0e0e0", font=("Arial", 12))
        self.pages_label.pack(side=tk.LEFT, padx=10)
        
        self.doc_name_label = tk.Label(self.status_frame, text=f"Document: {self.current_doc_name}", bg="#e0e0e0", font=("Arial", 12))
        self.doc_name_label.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(self.status_frame, text="Status: Ready", bg="#e0e0e0", font=("Arial", 12))
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # Main content frame
        self.content_frame = tk.Frame(self.window, bg="#f0f0f0")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left frame for camera feed
        self.camera_frame = tk.Frame(self.content_frame, bg="#f0f0f0", width=600)
        self.camera_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Camera canvas
        self.camera_canvas = tk.Canvas(self.camera_frame, bg="black", width=580, height=450)
        self.camera_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Camera control buttons
        self.camera_btn_frame = tk.Frame(self.camera_frame, bg="#f0f0f0")
        self.camera_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.capture_btn = ttk.Button(self.camera_btn_frame, text="Capture", command=self.capture_image)
        self.capture_btn.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.X, expand=True)
        
        self.auto_btn = ttk.Button(self.camera_btn_frame, text="Auto", command=self.toggle_auto_mode)
        self.auto_btn.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.X, expand=True)
        
        # Right frame for preview
        self.preview_frame = tk.Frame(self.content_frame, bg="#f0f0f0", width=600)
        self.preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Preview canvas
        self.preview_canvas = tk.Canvas(self.preview_frame, bg="white", width=580, height=450)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Preview control buttons
        self.preview_btn_frame = tk.Frame(self.preview_frame, bg="#f0f0f0")
        self.preview_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.cancel_btn = ttk.Button(self.preview_btn_frame, text="Cancel", command=self.cancel_capture)
        self.cancel_btn.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.X, expand=True)
        
        self.save_btn = ttk.Button(self.preview_btn_frame, text="Save", command=self.save_image)
        self.save_btn.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.X, expand=True)
        
        # Menu
        self.menu_bar = tk.Menu(window)
        self.window.config(menu=self.menu_bar)
        
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Start Camera", command=self.start_camera)
        self.file_menu.add_command(label="Stop Camera", command=self.stop_camera)
        self.file_menu.add_command(label="Set Document Name", command=self.set_document_name)
        self.file_menu.add_command(label="New Document", command=self.new_document)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Export PDF", command=self.export_pdf)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_close)
        
        # Initialize
        self.update_buttons_state()
        
        # Set the close handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start camera on init
        self.start_camera()
    
    def start_camera(self):
        """Start the camera feed"""
        if self.camera_active:
            return
        
        self.set_status("Starting camera...")
        
        try:
            if USING_PICAMERA:
                # Use Raspberry Pi camera
                self.picam2 = Picamera2()
                
                # Create configuration with high resolution for capture and lower for preview
                preview_config = self.picam2.create_video_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},  # Higher res for capture
                    lores={"size": (640, 480), "format": "RGB888"},   # Lower res for preview
                    controls={"FrameDurationLimits": (33333, 33333)}  # 30fps
                )
                
                # Configure and start camera
                self.picam2.configure(preview_config)
                self.picam2.start()
            else:
                # Fallback to OpenCV camera
                self.camera = cv2.VideoCapture(0)
                
                if not self.camera.isOpened():
                    raise Exception("Could not open camera")
            
            self.camera_active = True
            self.stop_event.clear()
            
            # Start camera thread
            self.camera_thread = threading.Thread(target=self.camera_stream)
            self.camera_thread.daemon = True
            self.camera_thread.start()
            
            self.set_status("Camera started")
            self.update_buttons_state()
        except Exception as e:
            messagebox.showerror("Camera Error", f"Could not start camera: {str(e)}")
            self.set_status("Camera error")
    
    def camera_stream(self):
        """Camera streaming thread function"""
        while self.camera_active and not self.stop_event.is_set():
            try:
                if USING_PICAMERA and self.picam2:
                    # Get frame from PiCamera2
                    frame = self.picam2.capture_array("lores")
                    # Convert BGR to RGB if needed (PiCamera2 already provides RGB)
                elif self.camera:
                    # Get frame from OpenCV camera
                    ret, frame = self.camera.read()
                    if not ret:
                        continue
                    # Convert from BGR (OpenCV) to RGB (Tkinter)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Put the frame in the queue
                if not self.frame_queue.full():
                    self.frame_queue.put(frame)
                
                # Update the GUI from the main thread
                self.window.after(1, self.update_camera_canvas)
                
                # Check for auto-capture
                if self.auto_mode and not self.capturing:
                    self.capturing = True
                    self.window.after(100, self.auto_capture)
            except Exception as e:
                print(f"Error in camera stream: {e}")
            
            # Small delay to reduce CPU usage
            time.sleep(0.01)
    
    def update_camera_canvas(self):
        """Update the camera canvas with the latest frame"""
        try:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get(False)
                
                # Resize the frame to fit the canvas
                canvas_width = self.camera_canvas.winfo_width()
                canvas_height = self.camera_canvas.winfo_height()
                
                if canvas_width > 1 and canvas_height > 1:
                    frame = cv2.resize(frame, (canvas_width, canvas_height))
                
                # Convert to PhotoImage
                img = Image.fromarray(frame)
                img_tk = ImageTk.PhotoImage(image=img)
                
                # Update canvas
                self.camera_canvas.config(width=canvas_width, height=canvas_height)
                self.camera_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.camera_canvas.image = img_tk  # Keep a reference
        except Exception as e:
            print(f"Error updating camera canvas: {e}")
    
    def stop_camera(self):
        """Stop the camera feed"""
        if not self.camera_active:
            return
        
        self.set_status("Stopping camera...")
        self.camera_active = False
        self.stop_event.set()
        
        # Clean up camera resources
        if USING_PICAMERA and self.picam2:
            self.picam2.stop()
            self.picam2 = None
        elif self.camera:
            self.camera.release()
            self.camera = None
        
        # Clear the camera display
        self.camera_canvas.delete("all")
        
        self.set_status("Camera stopped")
        self.update_buttons_state()
    
    def capture_image(self):
        """Capture an image from the camera feed"""
        if not self.camera_active:
            messagebox.showinfo("Info", "Camera is not active")
            return
        
        self.set_status("Capturing image...")
        
        try:
            if USING_PICAMERA and self.picam2:
                # Get high-res frame for the actual capture
                high_res_frame = self.picam2.capture_array("main")
                
                # For consistency with the OpenCV path, convert to RGB if needed
                # (PiCamera2 already provides RGB, so may not be necessary)
                frame = high_res_frame
            elif not self.frame_queue.empty():
                # Get the latest frame from OpenCV
                frame = self.frame_queue.get(False)
            else:
                raise Exception("No frame available")
            
            self.current_image = frame.copy()
            
            # Display in preview
            self.display_preview(self.current_image)
            
            self.set_status("Image captured")
        except Exception as e:
            self.set_status(f"Capture error: {str(e)}")
    
    def display_preview(self, image):
        """Display the captured image in the preview canvas"""
        try:
            # Resize the image to fit the canvas
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                image = cv2.resize(image, (canvas_width, canvas_height))
            
            # Convert to PhotoImage
            img = Image.fromarray(image)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Update canvas
            self.preview_canvas.config(width=canvas_width, height=canvas_height)
            self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
            self.preview_canvas.image = img_tk  # Keep a reference
        except Exception as e:
            print(f"Error displaying preview: {e}")
    
    def save_image(self):
        """Save the captured image"""
        if self.current_image is None:
            messagebox.showinfo("Info", "No image to save")
            return
        
        self.set_status("Saving image...")
        
        try:
            # Add to captured images list
            self.captured_images.append(self.current_image.copy())
            
            # Save as PDF directly
            self.pages_scanned += 1
            file_path = f"{self.output_dir}/{self.current_doc_name}_{self.pages_scanned:03d}.pdf"
            self.save_as_pdf(self.current_image, file_path)
            
            # Update the page count display
            self.pages_label.config(text=f"Pages Scanned: {self.pages_scanned}")
            
            # Clear the preview
            self.preview_canvas.delete("all")
            self.current_image = None
            
            self.set_status(f"Image saved as {os.path.basename(file_path)}")
            
            # If in auto mode, resume capturing
            if self.auto_mode:
                self.capturing = False
        except Exception as e:
            self.set_status(f"Save error: {str(e)}")
    
    def save_as_pdf(self, image_array, filename):
        """Save image as PDF using PIL"""
        # Convert to RGB if needed (in case it's BGR from OpenCV)
        if image_array.shape[2] == 3:  # If it has 3 color channels
            # Check if first pixel has blue dominant (likely BGR)
            if image_array[0, 0, 0] > image_array[0, 0, 2]:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
                
        image = Image.fromarray(image_array)
        image.save(filename, "PDF", resolution=300.0)
    
    def cancel_capture(self):
        """Cancel the current capture"""
        if self.current_image is None:
            return
        
        self.set_status("Cancelling...")
        
        # Clear the preview
        self.preview_canvas.delete("all")
        self.current_image = None
        
        self.set_status("Capture cancelled")
        
        # If in auto mode, resume capturing
        if self.auto_mode:
            self.capturing = False
    
    def toggle_auto_mode(self):
        """Toggle automatic capturing mode"""
        self.auto_mode = not self.auto_mode
        
        if self.auto_mode:
            self.auto_btn.config(text="Stop Auto")
            self.set_status("Auto mode: ON")
            self.capturing = False  # Reset capturing flag
        else:
            self.auto_btn.config(text="Auto")
            self.set_status("Auto mode: OFF")
    
    def auto_capture(self):
        """Perform automatic image capture"""
        if not self.auto_mode or not self.camera_active:
            self.capturing = False
            return
        
        # Capture the image
        try:
            if USING_PICAMERA and self.picam2:
                frame = self.picam2.capture_array("main")
            elif not self.frame_queue.empty():
                frame = self.frame_queue.get(False)
            else:
                self.capturing = False
                return
                
            self.current_image = frame.copy()
            self.display_preview(self.current_image)
            
            # Auto-save after a delay
            self.window.after(2000, self.auto_save)
        except Exception as e:
            print(f"Error in auto capture: {e}")
            self.capturing = False
    
    def auto_save(self):
        """Auto-save the captured image after a delay"""
        if self.current_image is not None:
            self.save_image()
    
    def set_document_name(self):
        """Set the document name"""
        name = simpledialog.askstring("Document Name", "Enter document name:", 
                                      parent=self.window, initialvalue=self.current_doc_name)
        if name:
            self.current_doc_name = name
            self.doc_name_label.config(text=f"Document: {self.current_doc_name}")
            self.set_status(f"Document name set to '{name}'")
    
    def new_document(self):
        """Start a new document"""
        if self.pages_scanned > 0:
            if messagebox.askyesno("Merge PDF", "Create PDF from scanned pages?"):
                self.export_pdf()
                
        # Create new document
        self.output_dir = f"scanned_document_{int(time.time())}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.pages_scanned = 0
        self.pages_label.config(text=f"Pages Scanned: {self.pages_scanned}")
        self.captured_images = []
        
        self.set_status(f"New document started: {self.output_dir}")
    
    def export_pdf(self):
        """Export captured images as a PDF file"""
        if not self.captured_images and self.pages_scanned == 0:
            messagebox.showinfo("Info", "No images to export")
            return
        
        try:
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{self.current_doc_name}_complete.pdf"
            )
            
            if not filename:
                return
            
            self.set_status("Exporting PDF...")
            
            # Try to use PyPDF2 to merge existing PDFs if we have scanned pages
            if self.pages_scanned > 0:
                try:
                    # Try to import PyPDF2
                    import importlib.util
                    spec = importlib.util.find_spec('PyPDF2')
                    if spec is None:
                        # If PyPDF2 is not installed, show warning but continue
                        print("PyPDF2 not installed. Using alternative PDF creation method.")
                        raise ImportError("PyPDF2 not installed")
                    
                    # Import and use PyPDF2
                    from PyPDF2 import PdfMerger
                    merger = PdfMerger()
                    pdf_files = sorted([f for f in os.listdir(self.output_dir) if f.endswith('.pdf')])
                    
                    for pdf in pdf_files:
                        merger.append(f"{self.output_dir}/{pdf}")
                        
                    merger.write(filename)
                    merger.close()
                    
                    self.set_status(f"PDF exported to {os.path.basename(filename)}")
                    messagebox.showinfo("Success", f"PDF exported successfully to {filename}")
                    return
                except Exception as e:
                    print(f"Error using PyPDF2: {e}")
                    print("Falling back to reportlab...")
            
            # Fallback: Create PDF using reportlab
            c = canvas.Canvas(filename, pagesize=letter)
            
            # Use captured images if available, otherwise find PDFs and convert
            if self.captured_images:
                image_list = self.captured_images
            else:
                # We have PDFs but no captured images in memory, so load them
                from PIL import Image as PILImage
                image_list = []
                pdf_files = sorted([f for f in os.listdir(self.output_dir) if f.endswith('.pdf')])
                for pdf in pdf_files:
                    try:
                        # Convert PDF to image using PIL
                        pdf_path = f"{self.output_dir}/{pdf}"
                        img = PILImage.open(pdf_path)
                        img_np = np.array(img)
                        image_list.append(img_np)
                    except Exception as e:
                        print(f"Error loading PDF {pdf}: {e}")
            
            for img in image_list:
                # Convert from numpy array to PIL Image
                pil_img = Image.fromarray(img)
                
                # Get the size of the page
                width, height = letter
                
                # Resize the image to fit the page (if needed)
                img_width, img_height = pil_img.size
                ratio = min(width / img_width, height / img_height)
                new_width = int(img_width * ratio)
                new_height = int(img_height * ratio)
                
                pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                
                # Save the image to a buffer
                img_buffer = io.BytesIO()
                pil_img.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                
                # Add the image to the PDF
                c.drawImage(img_buffer, (width - new_width) / 2, (height - new_height) / 2, 
                           width=new_width, height=new_height)
                c.showPage()
            
            c.save()
            self.set_status(f"PDF exported to {os.path.basename(filename)}")
            messagebox.showinfo("Success", f"PDF exported successfully to {filename}")
        except Exception as e:
            self.set_status(f"Export error: {str(e)}")
            messagebox.showerror("Export Error", f"Could not export PDF: {str(e)}")
    
    def set_status(self, message):
        """Update the status message"""
        self.status_label.config(text=f"Status: {message}")
        self.window.update_idletasks()
    
    def update_buttons_state(self):
        """Update the state of buttons based on the current application state"""
        if self.camera_active:
            self.capture_btn.config(state=tk.NORMAL)
            self.auto_btn.config(state=tk.NORMAL)
            self.file_menu.entryconfig("Start Camera", state=tk.DISABLED)
            self.file_menu.entryconfig("Stop Camera", state=tk.NORMAL)
        else:
            self.capture_btn.config(state=tk.DISABLED)
            self.auto_btn.config(state=tk.DISABLED)
            self.file_menu.entryconfig("Start Camera", state=tk.NORMAL)
            self.file_menu.entryconfig("Stop Camera", state=tk.DISABLED)
    
    def on_close(self):
        """Handle window close event"""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.stop_camera()
            self.window.destroy()

# Import missing module
from tkinter import simpledialog

def main():
    root = tk.Tk()
    app = PDFScannerApp(root, "Raspberry Pi PDF Scanner")
    root.mainloop()

if __name__ == "__main__":
    main()
