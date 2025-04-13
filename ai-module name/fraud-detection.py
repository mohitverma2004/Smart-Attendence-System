import logging
import numpy as np
from datetime import datetime, timedelta
from database.db import Attendance, User

logger = logging.getLogger(__name__)

class FraudDetectionService:
    def __init__(self):
        self.time_threshold = 120  # seconds between consecutive attendance marks
        self.distance_threshold = 100  # meters between consecutive attendance locations
        logger.info("Fraud Detection Service initialized")
    
    def check_attendance_fraud(self, user_id, timestamp, location, device_id):
        """
        Check for potential fraudulent attendance
        Returns (is_fraud, reason) tuple
        """
        try:
            # Get the user's last attendance record
            last_attendance = Attendance.objects(user_id=user_id).order_by('-timestamp').first()
            
            if not last_attendance:
                # First attendance, no fraud check needed
                return False, None
            
            # Check time proximity
            time_diff = (timestamp - last_attendance.timestamp).total_seconds()
            if time_diff < self.time_threshold:
                logger.warning(f"Suspicious attendance timing for user {user_id}: {time_diff} seconds since last attendance")
                return True, "Too frequent attendance"
            
            # Check location proximity if location data is available
            if location and last_attendance.location:
                distance = self._calculate_distance(location, last_attendance.location)
                if time_diff < 300 and distance > self.distance_threshold:  # 5 minutes
                    logger.warning(f"Suspicious location change for user {user_id}: {distance:.2f}m in {time_diff:.2f} seconds")
                    return True, "Impossible location change"
            
            # Check for repeated device usage in short time by different users
            recent_device_usage = Attendance.objects(
                device_id=device_id,
                timestamp__gte=timestamp - timedelta(seconds=30),
                user_id__ne=user_id
            )
            
            if recent_device_usage:
                different_users = set([record.user_id for record in recent_device_usage])
                if different_users:
                    logger.warning(f"Multiple users using same device ({device_id}) within short time frame")
                    return True, "Shared device usage detected"
            
            # More sophisticated checks could be added here
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            return False, None
    
    def _calculate_distance(self, loc1, loc2):
        """Calculate approximate distance between two locations in meters"""
        try:
            # Parse location strings in format "lat,long"
            lat1, lon1 = map(float, loc1.split(','))
            lat2, lon2 = map(float, loc2.split(','))
            
            # Convert latitude and longitude to radians
            lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formula
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            r = 6371000  # Radius of earth in meters
            
            return c * r
        except Exception as e:
            logger.error(f"Error calculating distance: {str(e)}")
            return 0  # Default to 0 if calculation fails
    
    def analyze_attendance_patterns(self, user_id, date_range=30):
        """Analyze attendance patterns to detect anomalies"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=date_range)
            
            # Get attendance records for this user
            attendance_records = Attendance.objects(
                user_id=user_id,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not attendance_records:
                return {}
            
            # Extract attendance times
            weekdays = [[] for _ in range(7)]
            
            for record in attendance_records:
                weekday = record.timestamp.weekday()
                time_of_day = record.timestamp.hour * 60 + record.timestamp.minute  # minutes since midnight
                weekdays[weekday].append(time_of_day)
            
            # Calculate mean and standard deviation for each weekday
            patterns = {}
            for i in range(7):
                if weekdays[i]:
                    mean_time = np.mean(weekdays[i])
                    std_time = np.std(weekdays[i])
                    patterns[i] = {
                        'mean_time_minutes': mean_time,
                        'std_time_minutes': std_time,
                        'sample_size': len(weekdays[i])
                    }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing attendance patterns: {str(e)}")
            return {}
