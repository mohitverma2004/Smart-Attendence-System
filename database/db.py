import logging
from flask import Flask
from mongoengine import Document, StringField, DateTimeField, IntField, BooleanField, ReferenceField, BinaryField, connect, ListField, FloatField

logger = logging.getLogger(__name__)

def initialize_db(app):
    """Initialize database connection"""
    try:
        connect(
            host=app.config['MONGODB_SETTINGS']['host'],
            alias='default'
        )
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

class User(Document):
    """User model for authentication and identification"""
    name = StringField(required=True)
    email = StringField(required=True, unique=True)
    password = StringField(required=True)
    role = StringField(default='user')  # admin, user
    department = StringField()
    employee_id = StringField()
    created_at = DateTimeField()
    last_login = DateTimeField()
    active = BooleanField(default=True)
    meta = {'collection': 'users'}

class Attendance(Document):
    """Attendance record model"""
    user_id = StringField(required=True)
    user_name = StringField(required=True)
    timestamp = DateTimeField(required=True)
    status = StringField(default='present')  # present, absent, late
    device_id = StringField()
    location = StringField()
    department = StringField()
    verification_method = StringField()  # face_recognition, manual, etc.
    notes = StringField()
    meta = {'collection': 'attendance'}

class Device(Document):
    """IoT device model"""
    device_id = StringField(required=True, unique=True)
    name = StringField()
    location = StringField()
    status = StringField(default='active')  # active, inactive, maintenance
    last_online = DateTimeField()
    ip_address = StringField()
    model = StringField()
    firmware_version = StringField()
    meta = {'collection': 'devices'}

class FaceData(Document):
    """Face recognition data model"""
    user_id = StringField(required=True)
    user_name = StringField()
    face_encoding = BinaryField(required=True)  # Pickled face encoding
    registered_at = DateTimeField()
    last_updated = DateTimeField()
    meta = {'collection': 'face_data'}

class AttendancePolicy(Document):
    """Attendance policy model"""
    name = StringField(required=True)
    department = StringField()
    start_time = StringField()  # HH:MM format
    end_time = StringField()  # HH:MM format
    grace_period_minutes = IntField(default=15)
    weekend_days = ListField(IntField())  # 0=Monday, 6=Sunday
    holidays = ListField(DateTimeField())
    created_by = StringField()
    created_at = DateTimeField()
    active = BooleanField(default=True)
    meta = {'collection': 'attendance_policies'}

class SensorData(Document):
    """Sensor data model for IoT devices"""
    device_id = StringField(required=True)
    sensor_type = StringField(required=True)
    timestamp = DateTimeField(required=True)
    value = FloatField()
    unit = StringField()
    meta = {'collection': 'sensor_data'}

class SystemLog(Document):
    """System log model"""
    timestamp = DateTimeField(required=True)
    level = StringField(required=True)  # info, warning, error
    source = StringField()  # component that generated the log
    message = StringField(required=True)
    details = StringField()
    meta = {'collection': 'system_logs'}
