import os
import cv2
import torch
import numpy as np
from flask import Flask, redirect, url_for, request, render_template, Response, send_from_directory, send_file
from werkzeug.utils import secure_filename
from ultralytics import YOLO
from io import BytesIO


app = Flask(__name__)

# YOLO model path (update this to your model's path)
model = YOLO('weed_detect.pt')

# Define upload folder and allowed extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Function to check if the uploaded file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Reusable weed detection function for both video frames and uploaded images
def detect_weeds(input_data):
    if isinstance(input_data, str):
        # If the input is a file path (image upload)
        img = cv2.imread(input_data)
    else:
        # If the input is a frame from a video
        img = input_data
    
    # Convert to RGB as required by the YOLO model
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Run inference using YOLO model
    results = model(img_rgb)

    # Plot detections on the image/frame
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = result.names[int(box.cls[0])]  # Get label name
            confidence = box.conf[0].item()
            # Draw bounding box and label
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f'{label} {confidence:.2f}', (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    return img

# Route for video feed (uses webcam frames)
def generate_frames(camera_type='back'):
    # Select the camera based on the camera type
    camera_index = 0 if camera_type == 'back' else 1  # Assume 0 is back camera and 1 is front camera
    cap = cv2.VideoCapture(camera_index)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # Detect weeds in the frame
            frame = detect_weeds(frame)
            
            # Encode the frame to JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield the frame to be displayed on the frontend
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

@app.route('/video_feed/<camera_type>')
def video_feed(camera_type):
    return Response(generate_frames(camera_type), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route to handle the image upload
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    
    if file and allowed_file(file.filename):
        # Read the image file into memory (as a NumPy array)
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        # Run weed detection on the uploaded image
        output_image = detect_weeds(img)
        
        # Encode the output image to JPEG format
        _, buffer = cv2.imencode('.jpg', output_image)
        io_buf = BytesIO(buffer)
        
        # Return the processed image as a response without saving
        return send_file(io_buf, mimetype='image/jpeg')

    return redirect(request.url)


# Main page route (index)
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
