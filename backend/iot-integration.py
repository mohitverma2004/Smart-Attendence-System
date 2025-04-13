import requests
import cv2
import numpy as np
import base64
import time
import threading
import queue
from datetime import datetime
import json
import os

class IoTCamera:
    def __init__(self, server_url=None):
        """Initialize IoT camera integration
        
        Args:
            server_url: URL of the attendance server
        """
        self.server_url = server_url or os.environ.get('SERVER_URL', 'http://localhost:5000/api/capture')
        self.camera_id = os.environ.get('CAMERA_ID', 'cam001')
        self.api_key = os.environ.get('API_KEY', 'default_api_key')
        self.frame_queue = queue.Queue(maxsize=10)
        self.processing = False
        self.process_interval = 3  # Process a frame every 3 seconds
        self.last_process_time = 0
        
    def start_camera(self, camera_index=0):
        
