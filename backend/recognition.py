import cv2
import numpy as np
import face_recognition
import os
import pickle
from datetime import datetime
import threading

class FaceRecognition:
    def __init__(self, model_path="face_encodings.pkl", tolerance=0.6):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.model_path = model_path
        self.tolerance = tolerance
        self.lock = threading.Lock()
        
        # Load existing face encodings if available
        self.load_encodings()
    
    def load_encodings(self):
        """Load saved face encodings from file if available"""
        if os.path.exists(self.model_path):
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.known_face_encodings = data.get('encodings', [])
                self.known_face_names = data.get('names', [])
                self.known_face_ids = data.get('ids', [])
                print(f"Loaded {len(self.known_face_encodings)} face encodings")
    
    def save_encodings(self):
        """Save face encodings to file"""
        with self.lock:
            data = {
                'encodings': self.known_face_encodings,
                'names': self.known_face_names,
                'ids': self.known_face_ids
            }
            with open(self.model_path, 'wb') as f:
                pickle.dump(data, f)
    
    def register_new_face(self, person_id, person_name, image_file):
        """Register a new face to the system"""
        try:
            # Read image file
            image_data = image_file.read()
            image_array = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            # Convert to RGB (face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Find face locations
            face_locations = face_recognition.face_locations(rgb_image)
            
            if not face_locations:
                print("No face detected in the image")
                return False
            
            # Compute face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            if not face_encodings:
                print("Failed to compute face encoding")
                return False
            
            # Add to known faces
            with self.lock:
                self.known_face_encodings.append(face_encodings[0])
                self.known_face_names.append(person_name)
                self.known_face_ids.append(person_id)
            
            # Save updated encodings
            self.save_encodings()
            return True
            
        except Exception as e:
            print(f"Error registering face: {e}")
            return False
    
    def process_image(self, image_file):
        """Process an image to recognize faces and return recognized person IDs"""
        try:
            # Read image file
            image_data = image_file.read()
            image_array = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            # Convert to RGB (face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Find faces in the image
            face_locations = face_recognition.face_locations(rgb_image)
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            recognized_ids = []
            
            for face_encoding in face_encodings:
                # Compare with known faces
                with self.lock:
                    if not self.known_face_encodings:
                        continue
                    
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings, 
                        face_encoding, 
                        tolerance=self.tolerance
                    )
                    
                    if True in matches:
                        first_match_index = matches.index(True)
                        recognized_ids.append(self.known_face_ids[first_match_index])
            
            return recognized_ids
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return []
