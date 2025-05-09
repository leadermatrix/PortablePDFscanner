# test_picamera2.py

from picamera2 import Picamera2
import time

# Initialize the camera
picam2 = Picamera2()

# Configure preview (640x480)
preview_config = picam2.create_still_configuration(main={"size": (640, 480)})
picam2.configure(preview_config)

# Start the camera
picam2.start()
print("Camera started. Capturing image in 3 seconds...")

# Wait for camera to warm up
time.sleep(3)

# Capture and save image
picam2.capture_file("test_image.jpg")
print("Image saved as test_image.jpg")

# Stop the camera
picam2.close()
