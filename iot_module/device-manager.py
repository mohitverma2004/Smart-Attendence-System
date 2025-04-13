import logging
import json
import time
import threading
import socket
import requests
from datetime import datetime
import os
from database.db import Device

logger = logging.getLogger(__name__)

class DeviceManager:
    def __init__(self):
        """Initialize the device manager"""
        self.devices = {}  # Dictionary to store device information
        self.active_devices = set()  # Set of active device IDs
        self.lock = threading.Lock()  # Lock for thread safety
        self.heartbeat_interval = 60  # Seconds between heartbeat checks
        self.heartbeat_timeout = 300  # Seconds to consider a device offline
        self.backend_url = os.environ.get('BACKEND_URL', 'http://localhost:5000')
        
        # Start the heartbeat monitoring thread
        self.heartbeat_thread = threading.Thread(target=self._monitor_heartbeats, daemon=True)
        self.heartbeat_thread.start()
        
        logger.info("Device Manager initialized")
        
    def register_device(self, device_id, ip_address):
        """Register a new IoT device"""
        with self.lock:
            if device_id in self.devices:
                logger.info(f"Device {device_id} already registered, updating information")
            
            self.devices[device_id] = {
                'device_id': device_id,
                'ip_address': ip_address,
                'status': 'active',
                'last_heartbeat': datetime.utcnow(),
                'connection_info': {
                    'connected_at': datetime.utcnow(),
                    'protocol': 'mqtt',
                }
            }
            
            self.active_devices.add(device_id)
            logger.info(f"Device {device_id} registered with IP {ip_address}")
            
            return True
    
    def unregister_device(self, device_id):
        """Unregister a device"""
        with self.lock:
            if device_id in self.devices:
                del self.devices[device_id]
                self.active_devices.discard(device_id)
                logger.info(f"Device {device_id} unregistered")
                return True
            return False
    
    def get_device_status(self, device_id):
        """Get the status of a specific device"""
        with self.lock:
            if device_id in self.devices:
                return self.devices[device_id]['status']
            return 'unknown'
    
    def get_active_devices(self):
        """Get a list of active devices"""
        with self.lock:
            return list(self.active_devices)
    
    def update_device_heartbeat(self, device_id):
        """Update the heartbeat timestamp for a device"""
        with self.lock:
            if device_id in self.devices:
                self.devices[device_id]['last_heartbeat'] = datetime.utcnow()
                self.devices[device_id]['status'] = 'active'
                self.active_devices.add(device_id)
                
                # Update device status in database
                try:
                    device = Device.objects(device_id=device_id).first()
                    if device:
                        device.status = 'active'
                        device.last_online = datetime.utcnow()
                        device.save()
                except Exception as e:
                    logger.error(f"Error updating device status in database: {str(e)}")
                
                return True
            return False
    
    def configure_device(self, device_id, config):
        """Send configuration to a device"""
        with self.lock:
            if device_id not in self.devices:
                logger.error(f"Device {device_id} not registered")
                return False
            
            device_ip = self.devices[device_id]['ip_address']
            
            try:
                # Send configuration via HTTP
                url = f"http://{device_ip}/api/configure"
                response = requests.post(
                    url,
                    json=config,
                    timeout=5
                )
                
                if response.status_code == 200:
                    logger.info(f"Configuration sent to device {device_id}")
                    return True
                else:
                    logger.error(f"Failed to configure device {device_id}: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Error configuring device {device_id}: {str(e)}")
                return False
    
    def restart_device(self, device_id):
        """Send restart command to a device"""
        with self.lock:
            if device_id not in self.devices:
                logger.error(f"Device {device_id} not registered")
                return False
            
            device_ip = self.devices[device_id]['ip_address']
            
            try:
                # Send restart command via HTTP
                url = f"http://{device_ip}/api/restart"
                response = requests.post(url, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"Restart command sent to device {device_id}")
                    return True
                else:
                    logger.error(f"Failed to restart device {device_id}: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Error restarting device {device_id}: {str(e)}")
                return False
    
    def _monitor_heartbeats(self):
        """Thread function to monitor device heartbeats"""
        while True:
            try:
                current_time = datetime.utcnow()
                devices_to_mark_offline = []
                
                with self.lock:
                    for device_id, device_info in self.devices.items():
                        last_heartbeat = device_info['last_heartbeat']
                        time_diff = (current_time - last_heartbeat).total_seconds()
                        
                        if time_diff > self.heartbeat_timeout and device_info['status'] == 'active':
                            logger.warning(f"Device {device_id} missed heartbeat, marking as offline")
                            device_info['status'] = 'offline'
                            self.active_devices.discard(device_id)
                            devices_to_mark_offline.append(device_id)
                
                # Update database outside of the lock
                for device_id in devices_to_mark_offline:
                    try:
                        device = Device.objects(device_id=device_id).first()
                        if device:
                            device.status = 'offline'
                            device.save()
                    except Exception as e:
                        logger.error(f"Error updating device status in database: {str(e)}")
                
                # Sleep for the heartbeat interval
                time.sleep(self.heartbeat_interval)
            
            except Exception as e:
                logger.error(f"Error in heartbeat monitoring: {str(e)}")
                time.sleep(10)  # Sleep a bit before retrying
    
    def get_device_info(self, device_id):
        """Get detailed information about a device"""
        with self.lock:
            if device_id in self.devices:
                return self.devices[device_id]
            return None
    
    def broadcast_message(self, message):
        """Broadcast a message to all active devices"""
        sent_count = 0
        failed_count = 0
        
        with self.lock:
            active_devices = list(self.active_devices)
        
        for device_id in active_devices:
            try:
                device_info = self.get_device_info(device_id)
                if not device_info:
                    continue
                
                device_ip = device_info['ip_address']
                
                # Send message via HTTP
                url = f"http://{device_ip}/api/message"
                response = requests.post(
                    url,
                    json={"message": message},
                    timeout=2
                )
                
                if response.status_code == 200:
                    sent_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Failed to send message to device {device_id}")
            
            except Exception as e:
                failed_count += 1
                logger.error(f"Error sending message to device {device_id}: {str(e)}")
        
        logger.info(f"Broadcast complete: {sent_count} successful, {failed_count} failed")
        return sent_count, failed_count
