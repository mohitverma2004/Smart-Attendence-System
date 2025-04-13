import os
import cv2
import numpy as np
import face_recognition
import logging
import pickle
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime
from database.db import FaceData, User

logger = logging.getLogger(__name__)

class FaceRecognitionService:
    def __init__(self):
        self.model_path = os.path.join(os.getcwd(), 'ai_module', 'models')
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()
        logger.info("Face Recognition Service initialized")
        
    def load_known_faces(self):
        """Load all known faces from database"""
        try:
            # Get all face data from database
            face_data_records = FaceData.objects()
            
            self.known_face_encodings = []
            self.known_face_names = []
            
            for record in face_data_records:
                # Load the encoding
                encoding = pickle.loads(record.face_encoding)
                self.known_face_encodings.append(encoding)
                self.known_face_names.append(record.user_id)
                
            logger.info(f"Loaded {len(self.known_face_encodings)} faces from database")
        except Exception as e:
            logger.error(f"Error loading known faces: {str(e)}")
    
    def register_face(self, user_id, face_data):
        """Register a new face for a user"""
        try:
            # Check if user exists
            user = User.objects(id=user_id).first()
            if not user:
                logger.error(f"User ID {user_id} not found for face registration")
                return False
            
            # Decode base64 image
            image = self._decode_image(face_data)
            if image is None:
                return False
            
            # Detect faces in the image
            face_locations = face_recognition.face_locations(image)
            if not face_locations:
                logger.error("No face detected in the provided image")
                return False
            
            # Use the first face found
            face_encoding = face_recognition.face_encodings(image, [face_locations[0]])[0]
            
            # Check if this face already exists
            existing_face = FaceData.objects(user_id=user_id).first()
            if existing_face:
                # Update existing face data
                existing_face.face_encoding = pickle.dumps(face_encoding)
                existing_face.last_updated = datetime.utcnow()
                existing_face.save()
                logger.info(f"Updated face data for user {user_id}")
            else:
                # Create new face data
                new_face = FaceData(
                    user_id=user_id,
                    user_name=user.name,
                    face_encoding=pickle.dumps(face_encoding),
                    registered_at=datetime.utcnow(),
                    last_updated=datetime.utcnow()
                )
                new_face.save()
                logger.info(f"Registered new face for user {user_id}")
            
            # Reload known faces
            self.load_known_faces()
            
            return True
            
        except Exception as e:
            logger.error(f"Face registration error: {str(e)}")
            return False
    
    def identify_face(self, face_data):
        """Identify a face from image data"""
        try:
            # Decode base64 image
            image = self._decode_image(face_data)
            if image is None:
                return None
            
            # Detect faces in the image
            face_locations = face_recognition.face_locations(image)
            if not face_locations:
                logger.error("No face detected in the provided image")
                return None
            
            # Get encodings for detected faces
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            # Check if we have any known faces to compare with
            if not self.known_face_encodings:
                logger.warning("No known faces available for comparison")
                return None
            
            # Compare with known faces
            for face_encoding in face_encodings:
                # Compare face with all known faces
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.6)
                
                # Use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        user_id = self.known_face_names[best_match_index]
                        logger.info(f"Face identified as user {user_id}")
                        
                        # Log recognition confidence
                        confidence = 1 - face_distances[best_match_index]
                        logger.info(f"Recognition confidence: {confidence:.2f}")
                        
                        # Check for spoofing (simple check)
                        if self._check_for_spoofing(image, face_locations[0]):
                            logger.warning(f"Possible spoofing detected for user {user_id}")
                            return None
                        
                        return user_id
            
            logger.warning("Face not recognized in known faces")
            return None
            
        except Exception as e:
            logger.error(f"Face identification error: {str(e)}")
            return None
    
    def _decode_image(self, base64_image):
        """Decode base64 image to numpy array"""
        try:
            # Check if the string starts with data:image prefix and remove it if needed
            if ',' in base64_image:
                base64_image = base64_image.split(',')[1]
            
            # Decode base64
            image_data = base64.b64decode(base64_image)
            
            # Convert to image
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            return np.array(image)
            
        except Exception as e:
            logger.error(f"Error decoding image: {str(e)}")
            return None
    
    def _check_for_spoofing(self, image, face_location):
        """Basic check for photo spoofing attempts"""
        try:
            # Extract the face region
            top, right, bottom, left = face_location
            face_image = image[top:bottom, left:right]
            
            # Convert to grayscale
            gray = cv2.cvtColor(face_image, cv2.COLOR_RGB2GRAY)
            
            # Calculate Laplacian variance - blurry images (like printed photos) have low variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Check texture variance
            if laplacian_var < 10:  # Threshold determined empirically
                logger.warning(f"Possible printed photo detected: Laplacian variance = {laplacian_var}")
                return True
            
            # More advanced checks could be added here
            
            return False
            
        except Exception as e:
            logger.error(f"Error in spoofing check: {str(e)}")
            return False
    
    def update_model(self):
        """Update the face recognition model with new data"""
        # This would be used for periodic model updates or fine-tuning
        pass
