from picamera2 import Picamera2
import cv2
import numpy as np
from PIL import Image
import time
import os

class SimpleDocumentScanner:
    def __init__(self):
        # Initialize camera
        self.picam2 = Picamera2()
        
        # Create configuration with high resolution
        preview_config = self.picam2.create_video_configuration(
            main={"size": (1920, 1080), "format": "RGB888"},  # Higher res for capture
            lores={"size": (640, 480), "format": "RGB888"},   # Lower res for preview
            controls={"FrameDurationLimits": (33333, 33333)}  # 30fps
        )
        
        # Configure and start camera
        self.picam2.configure(preview_config)
        self.picam2.start()
        
        # Initialize variables
        self.current_doc_name = "Document"
        self.mouse_x = 0
        self.mouse_y = 0
        self.create_new_document()
    
    def create_new_document(self):
        """Create a new document (new folder and reset page count)"""
        self.output_dir = f"document_scan_{int(time.time())}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.page_count = 0
        print(f"[INFO] New document started: {self.output_dir}")
    
    def process_and_save(self, frame):
        """Process captured frame and save as PDF"""
        # Get high-res frame for the actual capture
        high_res_frame = self.picam2.capture_array("main")
        
        # Just use the raw frame without processing
        self.page_count += 1
        file_path = f"{self.output_dir}/{self.current_doc_name}_{self.page_count:03d}.pdf"
        self.save_as_pdf(high_res_frame, file_path)
        print(f"[INFO] Saved page {self.page_count}")
            
        # Display the captured page
        resized = cv2.resize(high_res_frame, (800, 600))
        cv2.imshow("Captured Page", resized)
        cv2.waitKey(1000)  # Show for 1 second
    
    def save_as_pdf(self, image_array, filename):
        """Save image as PDF"""
        image = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB))
        image.save(filename, "PDF", resolution=300.0)
    
    def merge_pdfs(self):
        """Merge PDFs for current document"""
        try:
            # Try to import PyPDF2
            import importlib.util
            spec = importlib.util.find_spec('PyPDF2')
            if spec is None:
                # If PyPDF2 is not installed, try to install it
                print("[INFO] PyPDF2 not installed. Attempting to install...")
                import subprocess
                subprocess.check_call(['pip', 'install', 'PyPDF2'])
                print("[INFO] PyPDF2 installed successfully.")
            
            # Now import and use PyPDF2
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            pdf_files = sorted([f for f in os.listdir(self.output_dir) if f.endswith('.pdf')])
            
            if not pdf_files:
                print("[INFO] No PDF files found to merge.")
                return
                
            for pdf in pdf_files:
                merger.append(f"{self.output_dir}/{pdf}")
                
            merger.write(f"{self.output_dir}/{self.current_doc_name}_complete.pdf")
            merger.close()
            print(f"[INFO] Combined PDF saved as {self.output_dir}/{self.current_doc_name}_complete.pdf")
            return True
        
        except Exception as e:
            print(f"[ERROR] Failed to merge PDFs: {str(e)}")
            print("[INFO] To manually install PyPDF2, run: pip install PyPDF2")
            return False
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for UI buttons"""
        self.mouse_x = x
        self.mouse_y = y
        
        if event == cv2.EVENT_LBUTTONDOWN:
            # Capture button
            if 50 <= x <= 200 and 380 <= y <= 430:
                self.process_and_save(None)
            
            # New Document button
            elif 250 <= x <= 400 and 380 <= y <= 430:
                if self.page_count > 0:
                    print(f"[INFO] Completed document with {self.page_count} pages")
                    self.show_merge_dialog()
                self.create_new_document()
            
            # Set Name button
            elif 450 <= x <= 600 and 380 <= y <= 430:
                cv2.destroyWindow("Document Scanner")
                name = input("Enter document name: ")
                if name:
                    self.current_doc_name = name
                    print(f"[INFO] Document name set to '{name}'")
    
    def show_merge_dialog(self):
        """Show dialog asking to merge PDFs"""
        # Create a dialog window
        dialog = np.ones((200, 400, 3), dtype=np.uint8) * 50  # Dark gray background
        
        # Add text
        cv2.putText(dialog, "Merge pages into single PDF?", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add Yes button
        cv2.rectangle(dialog, (50, 100), (150, 150), (0, 200, 0), -1)
        cv2.putText(dialog, "Yes", (85, 135), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add No button
        cv2.rectangle(dialog, (250, 100), (350, 150), (0, 0, 200), -1)
        cv2.putText(dialog, "No", (285, 135), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow("Merge Dialog", dialog)
        
        # Wait for user input
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                cv2.destroyWindow("Merge Dialog")
                return
            
            # Check for mouse clicks
            mouse_events = cv2.getWindowProperty("Merge Dialog", cv2.WND_PROP_AUTOSIZE)
            if mouse_events == -1:
                # Window closed
                return
            
            # Get mouse position and check for clicks
            x, y = -1, -1
            def dialog_mouse_callback(event, mouse_x, mouse_y, flags, param):
                nonlocal x, y
                if event == cv2.EVENT_LBUTTONDOWN:
                    x, y = mouse_x, mouse_y
            
            cv2.setMouseCallback("Merge Dialog", dialog_mouse_callback)
            
            # Check if buttons were clicked
            if x != -1 and y != -1:
                if 50 <= x <= 150 and 100 <= y <= 150:  # Yes button
                    success = self.merge_pdfs()
                    cv2.destroyWindow("Merge Dialog")
                    return
                elif 250 <= x <= 350 and 100 <= y <= 150:  # No button
                    cv2.destroyWindow("Merge Dialog")
                    return
    
    def draw_ui(self, frame):
        """Draw the UI elements on the frame"""
        display = frame.copy()
        
        # Add text info
        cv2.putText(display, "Document Scanner", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display, f"Document: {self.current_doc_name}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display, f"Pages: {self.page_count}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display, f"Folder: {self.output_dir}", (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Add UI buttons
        # Capture button
        button_color = (0, 200, 0) if 50 <= self.mouse_x <= 200 and 380 <= self.mouse_y <= 430 else (0, 150, 0)
        cv2.rectangle(display, (50, 380), (200, 430), button_color, -1)
        cv2.putText(display, "Capture", (90, 415), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # New Document button
        button_color = (0, 0, 200) if 250 <= self.mouse_x <= 400 and 380 <= self.mouse_y <= 430 else (0, 0, 150)
        cv2.rectangle(display, (250, 380), (400, 430), button_color, -1)
        cv2.putText(display, "New Doc", (290, 415), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Set Name button
        button_color = (200, 0, 200) if 450 <= self.mouse_x <= 600 and 380 <= self.mouse_y <= 430 else (150, 0, 150)
        cv2.rectangle(display, (450, 380), (600, 430), button_color, -1)
        cv2.putText(display, "Set Name", (480, 415), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return display
    
    def run(self):
        """Main scanner loop"""
        print("[INFO] Starting Document Scanner with UI")
        print("[INFO] Controls:")
        print("  - UI Buttons: Capture, New Document, Set Name")
        print("  - SPACE: Capture page")
        print("  - D: Start new document")
        print("  - N: Set document name")
        print("  - ESC: Quit")
        
        # Set up mouse callback
        cv2.namedWindow("Document Scanner")
        cv2.setMouseCallback("Document Scanner", self.mouse_callback)
        
        # Uncomment the GPIO setup when implementing hardware button
        # import RPi.GPIO as GPIO
        # CAPTURE_PIN = 17  # Change to your preferred GPIO pin
        # NEW_DOC_PIN = 27  # Change to your preferred GPIO pin
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setup(CAPTURE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # GPIO.setup(NEW_DOC_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # last_capture_state = GPIO.input(CAPTURE_PIN)
        # last_newdoc_state = GPIO.input(NEW_DOC_PIN)
        # debounce_time = 0.3
        # last_button_time = time.time()
        
        while True:
            # Get frame from camera
            frame = self.picam2.capture_array("lores")
            
            # Draw UI on the frame
            display = self.draw_ui(frame)
            
            # Show the frame
            cv2.imshow("Document Scanner", display)
            
            # Handle key presses for computer control
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27:  # ESC
                break
            elif key == 32:  # SPACE - Capture page
                self.process_and_save(frame)
            elif key == ord('d'):  # Start new document
                if self.page_count > 0:
                    print(f"[INFO] Completed document with {self.page_count} pages")
                    self.show_merge_dialog()
                self.create_new_document()
            elif key == ord('n'):  # Set document name
                cv2.destroyWindow("Document Scanner")
                name = input("Enter document name: ")
                if name:
                    self.current_doc_name = name
                    print(f"[INFO] Document name set to '{name}'")
            
            # Uncomment this block when implementing hardware buttons
            # # Check for hardware button press with debounce
            # current_time = time.time()
            # capture_state = GPIO.input(CAPTURE_PIN)
            # newdoc_state = GPIO.input(NEW_DOC_PIN)
            # 
            # # Check capture button
            # if capture_state != last_capture_state and current_time - last_button_time > debounce_time:
            #     last_button_time = current_time
            #     last_capture_state = capture_state
            #     # Button press detected (assuming active low with pull-up)
            #     if capture_state == GPIO.LOW:
            #         self.process_and_save(frame)
            # 
            # # Check new document button
            # if newdoc_state != last_newdoc_state and current_time - last_button_time > debounce_time:
            #     last_button_time = current_time
            #     last_newdoc_state = newdoc_state
            #     # Button press detected (assuming active low with pull-up)
            #     if newdoc_state == GPIO.LOW:
            #         if self.page_count > 0:
            #             print(f"[INFO] Completed document with {self.page_count} pages")
            #             self.show_merge_dialog()
            #         self.create_new_document()
        
        # Clean up
        cv2.destroyAllWindows()
        self.picam2.stop()
        
        # Uncomment when implementing hardware button
        # GPIO.cleanup()
        
        print(f"[INFO] Scanning complete. {self.page_count} pages saved to {self.output_dir}/")
        
        # Ask if user wants to merge the last document
        if self.page_count > 0:
            merge = input("Merge pages of last document into single PDF? (y/n): ")
            if merge.lower() == 'y':
                self.merge_pdfs()

# Run the document scanner
if __name__ == "__main__":
    scanner = SimpleDocumentScanner()
    scanner.run()
