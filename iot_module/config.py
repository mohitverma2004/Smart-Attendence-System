"""
Configuration settings for IoT devices
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    # Camera settings
    "camera": {
        "enabled": True,
        "resolution": {
            "width": 640,
            "height": 480
        },
        "fps": 15,
        "quality": 90,
        "face_detection": True,
        "detection_interval": 1.0
    },
    
    # MQTT settings
    "mqtt": {
        "enabled": True,
        "broker": "localhost",
        "port": 1883,
        "use_tls": False,
        "username": "",
        "password": "",
        "client_id_prefix": "smart_attendance_"
    },
    
    # Network settings
    "network": {
        "reconnect_attempts": 5,
        "reconnect_delay": 5,
        "timeout": 10,
        "backend_url": "http://localhost:5000"
    },
    
    # Security settings
    "security": {
        "encryption_enabled": True,
        "secure_boot": True,
        "api_key_required": True
    },
    
    # Device settings
    "device": {
        "location": "",
        "name": "",
        "log_level": "INFO",
        "heartbeat_interval": 60
    },
    
    # Processing settings
    "processing": {
        "local_face_detection": True,
        "local_face_recognition": False,
        "queue_size": 100,
        "min_attendance_interval": 60
    }
}

class DeviceConfig:
    def __init__(self, device_id, config_dir=None):
        """Initialize device configuration"""
        self.device_id = device_id
        self.config_dir = config_dir or os.path.join(os.path.dirname(__file__), 'config')
        self.config_file = os.path.join(self.config_dir, f'device_{device_id}.json')
        self.config = DEFAULT_CONFIG.copy()
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load configuration from file
        self.load_config()
        
        logger.info(f"Configuration initialized for device {device_id}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                
                # Update config with file values
                self._update_dict(self.config, file_config)
                logger.info(f"Configuration loaded from {self.config_file}")
            else:
                # Save default config
                self.save_config()
                logger.info(f"Default configuration saved to {self.config_file}")
                
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get(self, key, default=None):
        """Get a configuration value by key path"""
        try:
            # Split key path
            parts = key.split('.')
            
            # Navigate to the nested value
            value = self.config
            for part in parts:
                value = value.get(part)
                if value is None:
                    return default
            
            return value
        except Exception as e:
            logger.error(f"Error getting configuration value for {key}: {str(e)}")
            return default
    
    def set(self, key, value):
        """Set a configuration value by key path"""
        try:
            # Split key path
            parts = key.split('.')
            
            # Navigate to the parent object
            config = self.config
            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                config = config[part]
            
            # Set the value
            config[parts[-1]] = value
            
            # Save the updated configuration
            self.save_config()
            
            logger.info(f"Configuration updated: {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"Error setting configuration value {key}: {str(e)}")
            return False
    
    def update(self, config_dict):
        """Update configuration with a dictionary"""
        try:
            self._update_dict(self.config, config_dict)
            self.save_config()
            
            logger.info(f"Configuration updated with dictionary")
            return True
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            return False
    
    def _update_dict(self, target, source):
        """Recursively update a dictionary"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._update_dict(target[key], value)
            else:
                target[key] = value
    
    def get_mqtt_config(self):
        """Get MQTT configuration"""
        return self.get('mqtt', {})
    
    def get_camera_config(self):
        """Get camera configuration"""
        return self.get('camera', {})
    
    def get_network_config(self):
        """Get network configuration"""
        return self.get('network', {})
    
    def get_device_info(self):
        """Get device information"""
        device_config = self.get('device', {})
        return {
            'device_id': self.device_id,
            'name': device_config.get('name', f"Device-{self.device_id}"),
            'location': device_config.get('location', ''),
            'heartbeat_interval': device_config.get('heartbeat_interval', 60)
        }
    
    def get_processing_config(self):
        """Get processing configuration"""
        return self.get('processing', {})
