import logging
import json
import base64
import threading
import time
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta
import os
import requests

logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, device_id):
        """Initialize the data processor"""
        self.device_id = device_id
        self.backend_url = os.environ.get('BACKEND_URL', 'http://localhost:5000')
        self.processing_queue = []
        self.queue_lock = threading.Lock()
        self.max_queue_size = 100
        self.is_processing = False
        self.last_attendance_time = {}  # Track last attendance per user
        self.min_attendance_interval = 60  # seconds between attendance marks
        
        # Load face recognition module if available
        self.face_detector = None
        try:
            # Try to load face detector
            face_cascade_path = os.path.join(
                os.path.dirname(__file__), 
                'models', 
                'haarcascade_frontalface_default.xml'
            )
            if os.path.exists(face_cascade_path):
                self.face_detector = cv2.CascadeClassifier(face_cascade_path)
                logger.info("Face detector loaded for preprocessing")
        except Exception as e:
            logger.error(f"Error loading face detector: {str(e)}")
        
        logger.info(f"Data Processor initialized for device {device_id}")
    
    def start_processing(self):
        """Start the processing thread"""
        if self.is_processing:
            logger.warning("Data processor is already running")
            return False
        
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info(f"Data processor started for device {self.device_id}")
        return True
    
    def stop_processing(self):
        """Stop the processing thread"""
        if not self.is_processing:
            logger.warning("Data processor is not running")
            return False
        
        self.is_processing = False
        if self.processing_thread.is_alive():
            self.processing_thread.join(timeout=3.0)
        
        logger.info(f"Data processor stopped for device {self.device_id}")
        return True
    
    def process_image(self, image_data, metadata=None):
        """Process an image and add it to the processing queue"""
        try:
            with self.queue_lock:
                # Check if queue is full
                if len(self.processing_queue) >= self.max_queue_size:
                    logger.warning(f"Processing queue full for device {self.device_id}, dropping image")
                    return False
                
                # Add to queue
                self.processing_queue.append({
                    'type': 'image',
                    'data': image_data,
                    'metadata': metadata or {},
                    'timestamp': datetime.utcnow()
                })
            
            return True
        except Exception as e:
            logger.error(f"Error adding image to processing queue: {str(e)}")
            return False
    
    def process_data(self, data, data_type, metadata=None):
        """Process other data types and add to the processing queue"""
        try:
            with self.queue_lock:
                # Check if queue is full
                if len(self.processing_queue) >= self.max_queue_size:
                    logger.warning(f"Processing queue full for device {self.device_id}, dropping data")
                    return False
                
                # Add to queue
                self.processing_queue.append({
                    'type': data_type,
                    'data': data,
                    'metadata': metadata or {},
                    'timestamp': datetime.utcnow()
                })
            
            return True
        except Exception as e:
            logger.error(f"Error adding data to processing queue: {str(e)}")
            return False
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.is_processing:
            try:
                # Get next item from queue
                item = None
                with self.queue_lock:
                    if self.processing_queue:
                        item = self.processing_queue.pop(0)
                
                if item:
                    self._process_item(item)
                else:
                    # No items to process, sleep a bit
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}")
                time.sleep(1.0)
    
    def _process_item(self, item):
        """Process a single item from the queue"""
        try:
            item_type = item['type']
            data = item['data']
            metadata = item['metadata']
            timestamp = item['timestamp']
            
            if item_type == 'image':
                self._process_image_data(data, metadata, timestamp)
            elif item_type == 'attendance':
                self._process_attendance_data(data, metadata, timestamp)
            elif item_type == 'sensor':
                self._process_sensor_data(data, metadata, timestamp)
            else:
                logger.warning(f"Unknown item type: {item_type}")
                
        except Exception as e:
            logger.error(f"Error processing item: {str(e)}")
    
    def _process_image_data(self, image_data, metadata, timestamp):
        """Process image data for face detection"""
        try:
            # Skip processing if no face detector available
            if self.face_detector is None:
                return
            
            # Decode image data
            if isinstance(image_data, str):
                # Handle base64 encoded data
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                image = Image.open(BytesIO(image_bytes))
                image_np = np.array(image)
                if image_np.shape[2] == 4:  # RGBA
                    image_np = image_np[:, :, :3]  # Convert to RGB
            elif isinstance(image_data, np.ndarray):
                # Already a numpy array
                image_np = image_data
            else:
                logger.error("Unsupported image format")
                return
            
            # Convert to grayscale for face detection
            if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = image_np
            
            # Detect faces
            faces = self.face_detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            
            if len(faces) == 0:
                return
            
            # Extract face regions and process
            for (x, y, w, h) in faces:
                # Expand the face region slightly
                face_region = image_np[
                    max(0, y-20):min(image_np.shape[0], y+h+20),
                    max(0, x-20):min(image_np.shape[1], x+w+20)
                ]
                
                if face_region.size == 0:
                    continue
                
                # Convert to JPEG and base64
                face_image = Image.fromarray(face_region)
                buffer = BytesIO()
                face_image.save(buffer, format="JPEG", quality=90)
                face_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Send to backend for identification
                self._send_face_for_identification(face_base64, metadata)
                
                # Only process the first face to avoid overloading
                break
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
    
    def _process_attendance_data(self, data, metadata, timestamp):
        """Process attendance data"""
        try:
            # Check if we have user ID
            user_id = data.get('user_id')
            if not user_id:
                logger.warning("Attendance data missing user ID")
                return
            
            # Check for duplicate attendance
            if user_id in self.last_attendance_time:
                last_time = self.last_attendance_time[user_id]
                time_diff = (timestamp - last_time).total_seconds()
                
                if time_diff < self.min_attendance_interval:
                    logger.info(f"Ignoring duplicate attendance for user {user_id} ({time_diff:.1f}s interval)")
                    return
            
            # Update last attendance time
            self.last_attendance_time[user_id] = timestamp
            
            # Send attendance to backend
            attendance_data = {
                "user_id": user_id,
                "device_id": self.device_id,
                "timestamp": timestamp.isoformat(),
                "verification_method": data.get('verification_method', 'manual'),
                "location": metadata.get('location', ''),
                "status": data.get('status', 'present')
            }
            
            self._send_attendance_data(attendance_data)
            
        except Exception as e:
            logger.error(f"Error processing attendance data: {str(e)}")
    
    def _process_sensor_data(self, data, metadata, timestamp):
        """Process sensor data"""
        try:
            # Log sensor data
            logger.debug(f"Received sensor data: {data}")
            
            # Send sensor data to backend if needed
            if metadata.get('report_to_backend', False):
                sensor_data = {
                    "device_id": self.device_id,
                    "timestamp": timestamp.isoformat(),
                    "sensor_type": metadata.get('sensor_type', 'unknown'),
                    "data": data
                }
                
                # Send to backend in a separate thread
                threading.Thread(
                    target=self._send_sensor_data,
                    args=(sensor_data,),
                    daemon=True
                ).start()
                
        except Exception as e:
            logger.error(f"Error processing sensor data: {str(e)}")
    
    def _send_face_for_identification(self, face_base64, metadata):
        """Send face data to backend for identification"""
        try:
            # Prepare the data
            data = {
                "face_data": face_base64,
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "verification_method": "face_recognition",
                "location": metadata.get('location', '')
            }
            
            # Send to backend in a separate thread
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
    
    def _send_attendance_data(self, data):
        """Send attendance data to backend"""
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
                logger.info(f"Attendance data sent successfully for user {data.get('user_id')}")
            else:
                logger.warning(f"Failed to send attendance data: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending attendance data: {str(e)}")
    
    def _send_sensor_data(self, data):
        """Send sensor data to backend"""
        try:
            # Send the request
            url = f"{self.backend_url}/api/sensors/data"
            response = requests.post(
                url,
                json=data,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in (200, 201):
                logger.debug(f"Sensor data sent successfully")
            else:
                logger.warning(f"Failed to send sensor data: {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending sensor data: {str(e)}")
