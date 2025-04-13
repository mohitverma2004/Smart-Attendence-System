import logging
import threading
import base64
import json
import cv2
import numpy as np
import time
import os
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

logger = logging.getLogger(__name__)

class CameraService:
    def __init__(self, device_id, camera_url=None, camera_id=0):
        """
        Initialize the camera service
        
        Args:
            device_id: Unique ID for this device
            camera_url: URL for IP camera (rtsp, http) or None for local camera
            camera_id: Camera ID for local camera (usually 0)
        """
        self.device_id = device_id
        self.camera_url = camera_url
        self.camera_id = camera_id
        self.is_running = False
        self.capture = None
        self.frame_lock = threading.Lock()
        self.current_frame = None
        self.frame_width = 640
        self.frame_height = 480
        self.frame_rate = 15
        self.quality = 90  # JPEG quality
        self.detection_active = False
        self.backend_url = os.environ.get('BACKEND_URL', 'http://localhost:5000')
        self.detection_interval = 1.0  # seconds between face detections
        self.last_detection_time = 0
        self.face_cascade = None
        
        # Initialize face detection if OpenCV is available
        try:
            # Load the face detector
            face_cascade_path = os.path.join(
                os.path.dirname(__file__), 
                'models', 
                'haarcascade_frontalface_default.xml'
            )
            if os.path.exists(face_cascade_path):
                self.face_cascade = cv2.CascadeClassifier(face_cascade_path)
                logger.info("Face detection model loaded")
            else:
                logger.warning(f"Face detection model not found at {face_cascade_path}")
        except Exception as e:
            logger.error(f"Error initializing face detection: {str(e)}")
        
        logger.info(f"Camera Service initialized for device {device_id}")
    
    def start(self):
        """Start the camera service"""
        if self.is_running:
            logger.warning("Camera service is already running")
            return False
        
        try:
            # Initialize camera
            if self.camera_url:
                self.capture = cv2.VideoCapture(self.camera_url)
            else:
                self.capture = cv2.VideoCapture(self.camera_id)
            
            # Set camera parameters
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            # Check if camera opened successfully
            if not self.capture.isOpened():
                logger.error("Failed to open camera")
                return False
            
            # Start capture thread
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            logger.info(f"Camera service started for device {self.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting camera service: {str(e)}")
            return False
    
    def stop(self):
        """Stop the camera service"""
        if not self.is_running:
            logger.warning("Camera service is not running")
            return False
        
        self.is_running = False
        if self.capture_thread.is_alive():
            self.capture_thread.join(timeout=3.0)
        
        if self.capture:
            self.capture.release()
        
        logger.info(f"Camera service stopped for device {self.device_id}")
        return True
    
    def get_frame(self):
        """Get the current frame as JPEG bytes"""
        with self.frame_lock:
            if self.current_frame is None:
                return None
            
            _, jpeg = cv2.imencode('.jpg', self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            return jpeg.tobytes()
    
    def get_frame_base64(self):
        """Get the current frame as base64 encoded JPEG"""
        jpeg_bytes = self.get_frame()
        if jpeg_bytes:
            return base64.b64encode(jpeg_bytes).decode('utf-8')
        return None
    
    def _capture_loop(self):
        """Main loop for capturing frames"""
        while self.is_running:
            try:
                ret, frame = self.capture.read()
                if not ret:
                    logger.warning("Failed to capture frame, retrying...")
                    time.sleep(0.5)
                    continue
                
                # Process the frame
                frame = self._process_frame(frame)
                
                # Update current frame
                with self.frame_lock:
                    self.current_frame = frame
                
                # Face detection if enabled
                current_time = time.time()
                if self.detection_active and current_time - self.last_detection_time >= self.detection_interval:
                    self.last_detection_time = current_time
                    self._detect_faces(frame)
                
                # Maintain frame rate
                time.sleep(1.0 / self.frame_rate)
                
            except Exception as e:
                logger.error(f"Error in capture loop: {str(e)}")
                time.sleep(1.0)
    
    def _process_frame(self, frame):
        """Process the captured frame"""
        # Resize if needed
        if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame, timestamp, (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )
        
        # Add device ID
        cv2.putText(
            frame, f"Device: {self.device_id}", (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )
        
        return frame
    
    def _detect_faces(self, frame):
        """Detect faces in the frame and send to backend"""
        if self.face_cascade is None:
            return
        
        try:
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            
            if len(faces) == 0:
                return
            
            # For each face found
            for (x, y, w, h) in faces:
                # Expand the face region slightly
                face_region = frame[
                    max(0, y-20):min(frame.shape[0], y+h+20),
                    max(0, x-20):min(frame.shape[1], x+w+20)
                ]
                
                if face_region.size == 0:
                    continue
                
                # Convert to JPEG and base64
                _, face_jpeg = cv2.imencode('.jpg', face_region, [cv2.IMWRITE_JPEG_QUALITY, 90])
                face_base64 = base64.b64encode(face_jpeg).decode('utf-8')
                
                # Send to backend for identification
                self._send_face_for_identification(face_base64)
                
                # Only process one face per interval to avoid overloading
                break
                
        except Exception as e:
            logger.error(f"Error in face detection: {str(e)}")
    
    def _send_face_for_identification(self, face_base64):
        """Send face data to backend for identification"""
        try:
            # Prepare the data
            data = {
                "face_data": face_base64,
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "verification_method": "face_recognition"
            }
            
            # Send to backend in a separate thread to avoid blocking
            threading.Thread(
                target=self._send_attendance_request,
                args=(data,),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error preparing face data: {str(e)}")
    
    def _send_attendance_request(self, data):
        """Send attendance request to backend"""
        try:
            # Send the request
            url = f"{self.backend_url}/api/attendance/mark"
            response = requests.post(
                url,
                json=data,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"Attendance marked for {result.get('user_name', 'unknown user')}")
            else:
                logger.warning(f"Failed to mark attendance: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending attendance request: {str(e)}")
    
    def enable_face_detection(self, enabled=True):
        """Enable or disable face detection"""
        self.detection_active = enabled
        logger.info(f"Face detection {'enabled' if enabled else 'disabled'} for device {self.device_id}")
        return True
    
    def set_detection_interval(self, interval):
        """Set the interval between face detections in seconds"""
        if interval < 0.1:
            interval = 0.1
        self.detection_interval = interval
        logger.info(f"Detection interval set to {interval} seconds for device {self.device_id}")
        return True
    
    def set_camera_quality(self, quality):
        """Set camera quality (1-100)"""
        if quality < 1:
            quality = 1
        elif quality > 100:
            quality = 100
        
        self.quality = quality
        logger.info(f"Camera quality set to {quality} for device {self.device_id}")
        return True
