#!/usr/bin/env python3
"""
Main entry point for IoT device application
"""
import os
import sys
import time
import signal
import logging
import argparse
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from iot_module.device_client import DeviceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("device.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

# Global variables
device_client = None
running = True

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    global running
    logger.info("Shutdown signal received")
    running = False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='IoT Device Client for Smart Attendance System')
    parser.add_argument('--device-id', type=str, default=os.environ.get('DEVICE_ID', 'dev001'),
                        help='Device ID (default: dev001)')
    parser.add_argument('--config-dir', type=str, default=os.environ.get('CONFIG_DIR', None),
                        help='Configuration directory (default: None)')
    parser.add_argument('--backend-url', type=str, default=os.environ.get('BACKEND_URL', 'http://localhost:5000'),
                        help='Backend server URL (default: http://localhost:5000)')
    parser.add_argument('--mqtt-broker', type=str, default=os.environ.get('MQTT_BROKER', 'localhost'),
                        help='MQTT broker address (default: localhost)')
    parser.add_argument('--mqtt-port', type=int, default=int(os.environ.get('MQTT_PORT', '1883')),
                        help='MQTT broker port (default: 1883)')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Enable debug logging')
    
    return parser.parse_args()

def main():
    """Main entry point"""
    global device_client
    
    # Parse arguments
    args = parse_arguments()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("iot_module").setLevel(logging.DEBUG)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Log startup information
        logger.info(f"Starting IoT device client with ID: {args.device_id}")
        logger.info(f"Backend URL: {args.backend_url}")
        logger.info(f"MQTT Broker: {args.mqtt_broker}:{args.mqtt_port}")
        
        # Initialize device client
        device_client = DeviceClient(args.device_id, args.config_dir)
        
        # Update configuration if provided in arguments
        if args.backend_url:
            device_client.config.set('network.backend_url', args.backend_url)
        
        if args.mqtt_broker:
            device_client.config.set('mqtt.broker', args.mqtt_broker)
        
        if args.mqtt_port:
            device_client.config.set('mqtt.port', args.mqtt_port)
        
        # Start the device client
        if not device_client.start():
            logger.error("Failed to start device client")
            return 1
        
        # Main loop
        logger.info("Device client running. Press CTRL+C to exit.")
        while running:
            time.sleep(1)
        
        # Clean shutdown
        logger.info("Shutting down device client...")
        device_client.stop()
        logger.info("Device client stopped")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        
        if device_client:
            try:
                device_client.stop()
            except:
                pass
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
