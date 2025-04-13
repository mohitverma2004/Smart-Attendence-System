import logging
import threading
import time
import os
import json
from datetime import datetime
import requests

from iot_module.mqtt_client import MQTTClient
from iot_module.camera_service import CameraService
from iot_module.data_processor import DataProcessor
from iot_module.config import DeviceConfig

logger = logging.getLogger(__name__)

class DeviceClient:
    def __init__(self, device_id, config_dir=None):
        """Initialize the IoT device client"""
        self.device_id = device_id
        
        # Initialize configuration
        self.config = DeviceConfig(device_id, config_dir)
        
        # Initialize services
        self._init_services()
        
        # Status variables
        self.is_running = False
        self.backend_connected = False
        self.last_backend_check = 0
        self.backend_check_interval = 60  # seconds
        
        logger.info(f"Device client initialized with ID: {device_id}")
    
    def _init_services(self):
        """Initialize device services based on configuration"""
        # Get configurations
        mqtt_config = self.config.get_mqtt_config()
        camera_config = self.config.get_camera_config()
        
        # Initialize MQTT client if enabled
        if mqtt_config.get('enabled', True):
            self.mqtt_client = MQTTClient(
                self.device_id,
                mqtt_config.get('broker', 'localhost'),
                mqtt_config.get('port', 1883),
                mqtt_config.get('use_tls', False)
            )
        else:
            self.mqtt_client = None
        
        # Initialize camera service if enabled
        if camera_config.get('enabled', True):
            resolution = camera_config.get('resolution', {'width': 640, 'height': 480})
            self.camera_service = CameraService(
                self.device_id,
                camera_url=None,  # Local camera
                camera_id=0
            )
            # Configure camera
            self.camera_service.frame_width = resolution.get('width', 640)
            self.camera_service.frame_height = resolution.get('height', 480)
            self.camera_service.frame_rate = camera_config.get('fps', 15)
            self.camera_service.quality = camera_config.get('quality', 90)
        else:
            self.camera_service = None
        
        # Initialize data processor
        self.data_processor = DataProcessor(self.device_id)
        
        # Get backend URL
        network_config = self.config.get_network_config()
        self.backend_url = network_config.get('backend_url', 'http://localhost:5000')
    
    def start(self):
        """Start the device client and all enabled services"""
        if self.is_running:
            logger.warning(f"Device client {self.device_id} is already running")
            return False
        
        logger.info(f"Starting device client {self.device_id}")
        self.is_running = True
        
        # Connect to MQTT broker if enabled
        if self.mqtt_client:
            self.mqtt_client.connect()
            
            # Register command handlers
            self._register_mqtt_handlers()
        
        # Start camera service if enabled
        if self.camera_service:
            self.camera_service.start()
            
            # Enable face detection if configured
            camera_config = self.config.get_camera_config()
            if camera_config.get('face_detection', True):
                self.camera_service.enable_face_detection(True)
                self.camera_service.set_detection_interval(
                    camera_config.get('detection_interval', 1.0)
                )
        
        # Start data processor
        self.data_processor.start_processing()
        
        # Register with backend
        self._register_with_backend()
        
        # Start main processing loop
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()
        
        logger.info(f"Device client {self.device_id} started successfully")
        return True
    
    def stop(self):
        """Stop the device client and all services"""
        if not self.is_running:
            logger.warning(f"Device client {self.device_id} is not running")
            return False
        
        logger.info(f"Stopping device client {self.device_id}")
        self.is_running = False
        
        # Disconnect MQTT
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        # Stop camera service
        if self.camera_service:
            self.camera_service.stop()
        
        # Stop data processor
        self.data_processor.stop_processing()
        
        # Wait for main thread to exit
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=3.0)
        
        logger.info(f"Device client {self.device_id} stopped")
        return True
    
    def _register_mqtt_handlers(self):
        """Register MQTT message handlers"""
        if not self.mqtt_client:
            return
        
        # Subscribe to control topic
        self.mqtt_client.subscribe(
            f"devices/{self.device_id}/control",
            self._handle_control_message
        )
        
        # Subscribe to broadcast messages
        self.mqtt_client.subscribe(
            "devices/broadcast",
            self._handle_broadcast_message
        )
    
    def _handle_control_message(self, topic, payload):
        """Handle control messages"""
        try:
            data = json.loads(payload)
            command = data.get('command')
            
            logger.info(f"Received control command: {command}")
            
            if command == 'restart':
                # Schedule restart in a separate thread
                threading.Thread(target=self._handle_restart_command, daemon=True).start()
            
            elif command == 'config_update':
                # Handle configuration update
                config = data.get('config', {})
                self._handle_config_update(config)
            
            elif command == 'capture_image':
                # Capture and send an image
                self._handle_capture_command()
            
            elif command == 'status_report':
                # Send a status report
                self._send_status_report()
            
            else:
                logger.warning(f"Unknown command: {command}")
                
        except Exception as e:
            logger.error(f"Error handling MQTT control message: {str(e)}")
    
    def _handle_broadcast_message(self, topic, payload):
        """Handle broadcast messages"""
        try:
            data = json.loads(payload)
            message_type = data.get('type')
            
            logger.info(f"Received broadcast message: {message_type}")
            
            if message_type == 'backend_update':
                # Backend URL has changed
                new_url = data.get('backend_url')
                if new_url:
                    self.backend_url = new_url
                    self.config.set('network.backend_url', new_url)
                    logger.info(f"Backend URL updated to {new_url}")
            
            elif message_type == 'time_sync':
                # Time synchronization message
                # In a real device, this would adjust the system clock
                logger.info("Received time synchronization message")
            
            elif message_type == 'status_check':
                # Reply with device status
                self._send_status_report()
                
        except Exception as e:
            logger.error(f"Error handling broadcast message: {str(e)}")
    
    def _handle_restart_command(self):
        """Handle restart command"""
        logger.info("Preparing to restart device")
        
        # Send acknowledgment
        if self.mqtt_client:
            self.mqtt_client.publish(
                f"devices/{self.device_id}/status",
                json.dumps({
                    "status": "restarting",
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
        
        # Stop and restart services
        self.stop()
        time.sleep(2)
        self.start()
    
    def _handle_config_update(self, config):
        """Handle configuration update"""
        logger.info(f"Applying configuration update: {config}")
        
        # Update configuration
        self.config.update(config)
        
        # Apply changes that require service restart
        restart_required = False
        
        # Check if MQTT configuration changed
        if 'mqtt' in config and self.mqtt_client:
            mqtt_config = config.get('mqtt', {})
            if 'broker' in mqtt_config or 'port' in mqtt_config or 'use_tls' in mqtt_config:
                restart_required = True
        
        # Check if camera configuration changed
        if 'camera' in config and self.camera_service:
            camera_config = config.get('camera', {})
            
            # Update camera quality if changed
            if 'quality' in camera_config:
                self.camera_service.set_camera_quality(camera_config.get('quality', 90))
            
            # Update face detection settings
            if 'face_detection' in camera_config:
                self.camera_service.enable_face_detection(camera_config.get('face_detection', True))
            
            if 'detection_interval' in camera_config:
                self.camera_service.set_detection_interval(camera_config.get('detection_interval', 1.0))
            
            # Check if restart is required
            if 'resolution' in camera_config or 'fps' in camera_config:
                restart_required = True
        
        # Restart if required
        if restart_required:
            logger.info("Configuration changes require restart, restarting device...")
            threading.Thread(target=self._handle_restart_command, daemon=True).start()
        else:
            logger.info("Configuration updated without requiring restart")
    
    def _handle_capture_command(self):
        """Handle image capture command"""
        if not self.camera_service:
            logger.warning("Cannot capture image, camera service is not enabled")
            return
        
        try:
            # Capture image
            image_base64 = self.camera_service.get_frame_base64()
            
            if not image_base64:
                logger.warning("Failed to capture image")
                return
            
            # Publish image if MQTT is available
            if self.mqtt_client:
                self.mqtt_client.publish(
                    f"devices/{self.device_id}/image",
                    json.dumps({
                        "image": image_base64,
                        "timestamp": datetime.utcnow().isoformat(),
                        "device_id": self.device_id
                    })
                )
                logger.info("Image captured and published to MQTT")
            
            # Process image with data processor
            self.data_processor.process_image(
                image_base64,
                {
                    "source": "manual_capture",
                    "location": self.config.get('device.location', '')
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling capture command: {str(e)}")
    
    def _send_status_report(self):
        """Send device status report"""
        try:
            # Gather status information
            status = {
                "device_id": self.device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "name": self.config.get('device.name', f"Device-{self.device_id}"),
                "location": self.config.
