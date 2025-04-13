from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
from database.db import initialize_db, User, Attendance, Device, FaceData
from ai_module.face_recognition_service import FaceRecognitionService
from iot_module.device_manager import DeviceManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/smart_attendance')
}

# Enable CORS
CORS(app)

# Initialize database
initialize_db(app)

# Initialize services
face_recognition_service = FaceRecognitionService()
device_manager = DeviceManager()

# JWT Auth Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            token = auth_header.split(" ")[1] if len(auth_header.split(" ")) > 1 else None
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.objects(id=data['user_id']).first()
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

# Routes

@app.route('/api/login', methods=['POST'])
def login():
    auth = request.json
    
    if not auth or not auth.get('email') or not auth.get('password'):
        return jsonify({'message': 'Could not verify', 'authenticated': False}), 401
    
    user = User.objects(email=auth.get('email')).first()
    
    if not user:
        return jsonify({'message': 'User not found', 'authenticated': False}), 401
    
    if check_password_hash(user.password, auth.get('password')):
        token = jwt.encode({
            'user_id': str(user.id),
            'email': user.email,
            'role': user.role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'message': 'Login successful',
            'authenticated': True,
            'token': token,
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        }), 200
    
    return jsonify({'message': 'Invalid credentials', 'authenticated': False}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    
    if User.objects(email=data.get('email')).first():
        return jsonify({'message': 'User already exists', 'registered': False}), 409
    
    hashed_password = generate_password_hash(data.get('password'))
    
    new_user = User(
        name=data.get('name'),
        email=data.get('email'),
        password=hashed_password,
        role=data.get('role', 'user'),
        department=data.get('department', ''),
        employee_id=data.get('employee_id', ''),
        created_at=datetime.datetime.utcnow()
    )
    
    try:
        new_user.save()
        logger.info(f"New user registered: {data.get('email')}")
        return jsonify({'message': 'User registered successfully', 'registered': True}), 201
    except Exception as e:
        logger.error(f"User registration failed: {str(e)}")
        return jsonify({'message': 'Registration failed', 'registered': False, 'error': str(e)}), 500

@app.route('/api/attendance', methods=['GET'])
@token_required
def get_attendance(current_user):
    try:
        if current_user.role == 'admin':
            # Admins can see all attendance records
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            department = request.args.get('department')
            user_id = request.args.get('user_id')
            
            query = {}
            
            if start_date and end_date:
                start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
                end = end.replace(hour=23, minute=59, second=59)
                query['timestamp'] = {'$gte': start, '$lte': end}
            
            if department:
                query['department'] = department
                
            if user_id:
                query['user_id'] = user_id
                
            attendance_records = Attendance.objects(**query).order_by('-timestamp')
        else:
            # Regular users can only see their own attendance
            attendance_records = Attendance.objects(user_id=str(current_user.id)).order_by('-timestamp')
        
        # Format the records for the response
        records = []
        for record in attendance_records:
            records.append({
                'id': str(record.id),
                'user_id': record.user_id,
                'user_name': record.user_name,
                'timestamp': record.timestamp.isoformat(),
                'status': record.status,
                'device_id': record.device_id,
                'location': record.location,
                'department': record.department,
                'verification_method': record.verification_method
            })
        
        return jsonify({'records': records, 'count': len(records)}), 200
    
    except Exception as e:
        logger.error(f"Error fetching attendance: {str(e)}")
        return jsonify({'message': 'Failed to fetch attendance records', 'error': str(e)}), 500

@app.route('/api/attendance/mark', methods=['POST'])
def mark_attendance():
    try:
        data = request.json
        
        # Verify face data if provided
        face_data = data.get('face_data')
        user_id = None
        
        if face_data:
            # Process face recognition
            user_id = face_recognition_service.identify_face(face_data)
            if not user_id:
                return jsonify({
                    'message': 'Face not recognized',
                    'status': 'failed'
                }), 400
        elif data.get('user_id'):
            # If no face data but user_id provided (for other authentication methods)
            user_id = data.get('user_id')
        else:
            return jsonify({
                'message': 'No identification method provided',
                'status': 'failed'
            }), 400
            
        # Get user info
        user = User.objects(id=user_id).first()
        if not user:
            return jsonify({
                'message': 'User not found',
                'status': 'failed'
            }), 404
            
        # Create attendance record
        new_attendance = Attendance(
            user_id=str(user.id),
            user_name=user.name,
            timestamp=datetime.datetime.utcnow(),
            status=data.get('status', 'present'),
            device_id=data.get('device_id'),
            location=data.get('location', ''),
            department=user.department,
            verification_method=data.get('verification_method', 'face_recognition')
        )
        
        new_attendance.save()
        logger.info(f"Attendance marked for user: {user.name} ({user.id})")
        
        return jsonify({
            'message': 'Attendance marked successfully',
            'status': 'success',
            'attendance_id': str(new_attendance.id),
            'user_name': user.name,
            'timestamp': new_attendance.timestamp.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error marking attendance: {str(e)}")
        return jsonify({
            'message': 'Failed to mark attendance',
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user):
    # Only admins can access user list
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        users = User.objects().exclude('password')
        user_list = []
        
        for user in users:
            user_list.append({
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'department': user.department,
                'employee_id': user.employee_id,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        return jsonify({'users': user_list, 'count': len(user_list)}), 200
    
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return jsonify({'message': 'Failed to fetch users', 'error': str(e)}), 500

@app.route('/api/devices', methods=['GET'])
@token_required
def get_devices(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        devices = Device.objects()
        device_list = []
        
        for device in devices:
            device_list.append({
                'id': str(device.id),
                'device_id': device.device_id,
                'name': device.name,
                'location': device.location,
                'status': device.status,
                'last_online': device.last_online.isoformat() if device.last_online else None,
                'ip_address': device.ip_address
            })
        
        return jsonify({'devices': device_list, 'count': len(device_list)}), 200
    
    except Exception as e:
        logger.error(f"Error fetching devices: {str(e)}")
        return jsonify({'message': 'Failed to fetch devices', 'error': str(e)}), 500

@app.route('/api/devices/register', methods=['POST'])
@token_required
def register_device(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        data = request.json
        
        # Check if device already exists
        existing_device = Device.objects(device_id=data.get('device_id')).first()
        if existing_device:
            return jsonify({'message': 'Device already registered', 'registered': False}), 409
        
        # Create new device
        new_device = Device(
            device_id=data.get('device_id'),
            name=data.get('name'),
            location=data.get('location', ''),
            status='active',
            last_online=datetime.datetime.utcnow(),
            ip_address=data.get('ip_address', '')
        )
        
        new_device.save()
        logger.info(f"New device registered: {data.get('device_id')}")
        
        # Register device with IoT module
        device_manager.register_device(data.get('device_id'), data.get('ip_address', ''))
        
        return jsonify({
            'message': 'Device registered successfully',
            'registered': True,
            'device_id': new_device.device_id
        }), 201
    
    except Exception as e:
        logger.error(f"Device registration failed: {str(e)}")
        return jsonify({'message': 'Device registration failed', 'registered': False, 'error': str(e)}), 500

@app.route('/api/face/register', methods=['POST'])
@token_required
def register_face(current_user):
    try:
        data = request.json
        
        if current_user.role != 'admin' and str(current_user.id) != data.get('user_id'):
            return jsonify({'message': 'Unauthorized access'}), 403
        
        user_id = data.get('user_id')
        face_data = data.get('face_data')
        
        if not face_data:
            return jsonify({'message': 'No face data provided', 'registered': False}), 400
        
        # Process and store face data
        result = face_recognition_service.register_face(user_id, face_data)
        
        if result:
            return jsonify({
                'message': 'Face registered successfully',
                'registered': True,
                'user_id': user_id
            }), 201
        else:
            return jsonify({
                'message': 'Face registration failed',
                'registered': False
            }), 500
    
    except Exception as e:
        logger.error(f"Face registration failed: {str(e)}")
        return jsonify({'message': 'Face registration failed', 'registered': False, 'error': str(e)}), 500

@app.route('/api/reports/summary', methods=['GET'])
@token_required
def get_attendance_summary(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        department = request.args.get('department')
        
        if not start_date or not end_date:
            return jsonify({'message': 'Start date and end date are required'}), 400
        
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        
        # Build the query
        query = {'timestamp': {'$gte': start, '$lte': end}}
        if department:
            query['department'] = department
            
        # Get all attendance records in the date range
        attendance_records = Attendance.objects(**query)
        
        # Get all users
        users = User.objects()
        user_dict = {str(user.id): user for user in users}
        
        # Prepare summary data
        summary = {
            'total_users': users.count(),
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'department': department if department else 'All',
            'attendance_rate': 0,
            'present_count': 0,
            'absent_count': 0,
            'users_summary': []
        }
        
        # Group attendance by user
        user_attendance = {}
        for record in attendance_records:
            if record.user_id not in user_attendance:
                user_attendance[record.user_id] = []
            user_attendance[record.user_id].append(record)
        
        # Calculate number of working days in the date range
        working_days = 0
        current_date = start
        while current_date <= end:
            if current_date.weekday() < 5:  # Monday to Friday
                working_days += 1
            current_date += datetime.timedelta(days=1)
        
        # Calculate attendance for each user
        total_expected = 0
        total_present = 0
        
        for user_id, user in user_dict.items():
            if department and user.department != department:
                continue
                
            user_records = user_attendance.get(user_id, [])
            present_days = len(set([record.timestamp.date() for record in user_records]))
            
            # Calculate attendance rate for this user
            expected_days = working_days
            total_expected += expected_days
            total_present += present_days
            
            attendance_rate = (present_days / expected_days * 100) if expected_days > 0 else 0
            
            # Add to users summary
            summary['users_summary'].append({
                'user_id': user_id,
                'name': user.name,
                'department': user.department,
                'present_days': present_days,
                'expected_days': expected_days,
                'attendance_rate': round(attendance_rate, 2)
            })
        
        # Calculate overall statistics
        if total_expected > 0:
            summary['attendance_rate'] = round(total_present / total_expected * 100, 2)
        summary['present_count'] = total_present
        summary['absent_count'] = total_expected - total_present
        
        return jsonify(summary), 200
    
    except Exception as e:
        logger.error(f"Error generating attendance summary: {str(e)}")
        return jsonify({'message': 'Failed to generate attendance summary', 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
