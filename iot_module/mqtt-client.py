import logging
import paho.mqtt.client as mqtt
import json
import threading
import time
import os
import ssl
from datetime import datetime

logger = logging.getLogger(__name__)

class MQTTClient:
    def __init__(self, device_id, broker="localhost", port=1883, use_tls=False):
        """Initialize MQTT client for IoT device communication"""
        self.device_id = device_id
        self.broker = broker
        self.port = port
        self.use_tls = use_tls
        self.client = mqtt.Client(client_id=f"device_{device_id}")
        self.is_connected = False
        self.message_callbacks = {}
        self.reconnect_delay = 5  # seconds
        self.reconnect_max_delay = 60  # seconds
        self.last_ping = 0
        self.ping_interval = 30  # seconds
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Set TLS if needed
        if use_tls:
            self.client.tls_set(
                ca_certs=os.path.join(os.path.dirname(__file__), 'certs', 'ca.crt'),
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
        
        # Set authentication if configured
        username = os.environ.get('MQTT_USERNAME')
        password = os.environ.get('MQTT_PASSWORD')
        if username and password:
            self.client.username_pw_set(username, password)
        
        logger.info(f"MQTT Client initialized for device {device_id} to broker {broker}:{port}")
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, keepalive=60)
            
            # Start the client loop in a separate thread
            self.client.loop_start()
            
            # Start the heartbeat thread
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self.is_connected:
                self.client.publish(f"devices/{self.device_id}/status", json.dumps({
                    "status": "offline",
                    "timestamp": datetime.utcnow().isoformat()
                }), qos=1, retain=True)
                
            self.client.loop_stop()
            self.client.disconnect()
            logger.info(f"Disconnected from MQTT broker for device {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT broker: {str(e)}")
            return False
    
    def publish(self, topic, message, qos=0, retain=False):
        """Publish a message to a topic"""
        if not self.is_connected:
            logger.warning(f"Cannot publish, not connected to broker for device {self.device_id}")
            return False
        
        try:
            # If message is a dict, convert to JSON
            if isinstance(message, dict):
                message = json.dumps(message)
            
            # Publish the message
            result = self.client.publish(topic, message, qos, retain)
            
            # Check if the message was published
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish to {topic} for device {self.device_id}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {str(e)}")
            return False
    
    def subscribe(self, topic, callback, qos=0):
        """Subscribe to a topic with a callback"""
        if not self.is_connected:
            logger.warning(f"Cannot subscribe, not connected to broker for device {self.device_id}")
            return False
        
        try:
            result, _ = self.client.subscribe(topic, qos)
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to subscribe to {topic} for device {self.device_id}")
                return False
            
            # Register the callback for this topic
            self.message_callbacks[topic] = callback
            logger.info(f"Subscribed to {topic} for device {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to {topic}: {str(e)}")
            return False
    
    def unsubscribe(self, topic):
        """Unsubscribe from a topic"""
        if not self.is_connected:
            logger.warning(f"Cannot unsubscribe, not connected to broker for device {self.device_id}")
            return False
        
        try:
            result, _ = self.client.unsubscribe(topic)
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to unsubscribe from {topic} for device {self.device_id}")
                return False
            
            # Remove the callback for this topic
            if topic in self.message_callbacks:
                del self.message_callbacks[topic]
            
            logger.info(f"Unsubscribed from {topic} for device {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"Error unsubscribing from {topic}: {str(e)}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.is_connected = True
            logger.info(f"Connected to MQTT broker for device {self.device_id}")
            
            # Subscribe to device control topic
            self.client.subscribe(f"devices/{self.device_id}/control", qos=1)
            
            # Publish online status
            self.client.publish(f"devices/{self.device_id}/status", json.dumps({
                "status": "online",
                "timestamp": datetime.utcnow().isoformat()
            }), qos=1, retain=True)
        else:
            self.is_connected = False
            logger.error(f"Failed to connect to MQTT broker for device {self.device_id}, rc={rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker for device {self.device_id}, rc={rc}")
            threading.Thread(target=self._reconnect_loop, daemon=True).start()
        else:
            logger.info(f"Disconnected from MQTT broker for device {self.device_id}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Handle device control messages
            if topic == f"devices/{self.device_id}/control":
                self._handle_control_message(payload)
                return
            
            # Check if we have a callback for this topic
            if topic in self.message_callbacks:
                callback = self.message_callbacks[topic]
                callback(topic, payload)
            else:
                # Try to match with wildcards
                for registered_topic, callback in self.message_callbacks.items():
                    if self._topic_matches(registered_topic, topic):
                        callback(topic, payload)
                        return
                
                logger.debug(f"Received message on topic {topic} with no handler for device {self.device_id}")
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {str(e)}")
    
    def _handle_control_message(self, payload):
        """Handle control messages for this device"""
        try:
            data = json.loads(payload)
            command = data.get('command')
            
            if not command:
                logger.warning(f"Received control message without command for device {self.device_id}")
                return
            
            logger.info(f"Received control command: {command} for device {self.device_id}")
            
            # Handle common commands
            if command == 'restart':
                # Publish acknowledgment
                self.publish(f"devices/{self.device_id}/control/ack", {
                    "command": command,
                    "status": "received",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Schedule restart
                threading.Thread(target=self._handle_restart, daemon=True).start()
            
            elif command == 'config':
                # Handle configuration update
                config = data.get('config', {})
                self._handle_config_update(config)
                
                # Publish acknowledgment
                self.publish(f"devices/{self.device_id}/control/ack", {
                    "command": command,
                    "status": "applied",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif command == 'ping':
                # Respond to ping
                self.publish(f"devices/{self.device_id}/control/ack", {
                    "command": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            else:
                logger.warning(f"Unknown command: {command} for device {self.device_id}")
                
        except Exception as e:
            logger.error(f"Error handling control message: {str(e)}")
    
    def _handle_restart(self):
        """Handle device restart command"""
        logger.info(f"Restarting device {self.device_id} as requested")
        time.sleep(1)
        # In a real device, this would restart the physical hardware
        # For this simulation, we'll just disconnect and reconnect
        self.disconnect()
        time.sleep(2)
        self.connect()
    
    def _handle_config_update(self, config):
        """Handle configuration update"""
        logger.info(f"Applying configuration update for device {self.device_id}: {config}")
        # In a real device, this would update device configuration
        # For this simulation, we'll just log it
    
    def _reconnect_loop(self):
        """Loop to handle reconnection attempts"""
        delay = self.reconnect_delay
        
        while not self.is_connected:
            logger.info(f"Attempting to reconnect to MQTT broker in {delay} seconds for device {self.device_id}")
            time.sleep(delay)
            
            try:
                self.client.reconnect()
                break
            except Exception as e:
                logger.error(f"Reconnection failed: {str(e)}")
                
                # Increase delay with exponential backoff, up to max
                delay = min(delay * 1.5, self.reconnect_max_delay)
    
    def _heartbeat_loop(self):
        """Loop to send periodic heartbeats"""
        while self.is_connected:
            current_time = time.time()
            
            if current_time - self.last_ping >= self.ping_interval:
                self.last_ping = current_time
                
                # Send heartbeat
                self.publish(f"devices/{self.device_id}/heartbeat", {
                    "timestamp": datetime.utcnow().isoformat(),
                    "uptime": self._get_uptime()
                })
            
            time.sleep(1)
    
    def _get_uptime(self):
        """Get device uptime in seconds"""
        # In a real device, this would get the system uptime
        # For this simulation, we'll just return a placeholder
        return 3600  # 1 hour
    
    def _topic_matches(self, subscription, topic):
        """Check if a topic matches a subscription with wildcards"""
        # Split both into parts
        sub_parts = subscription.split('/')
        topic_parts = topic.split('/')
        
        # If lengths don't match and there's no wildcard, they don't match
        if len(sub_parts) != len(topic_parts) and '#' not in sub_parts:
            return False
        
        # Check each part
        for i, sub_part in enumerate(sub_parts):
            # Check for multi-level wildcard
            if sub_part == '#':
                return True
            
            # Check for single-level wildcard
            if sub_part == '+':
                continue
            
            # Check if we've gone beyond the topic parts
            if i >= len(topic_parts):
                return False
            
            # Check if parts match
            if sub_part != topic_parts[i]:
                return False
        
        return True
