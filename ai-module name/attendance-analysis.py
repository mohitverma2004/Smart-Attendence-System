import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from database.db import Attendance, User, Device

logger = logging.getLogger(__name__)

class AttendanceAnalytics:
    def __init__(self):
        logger.info("Attendance Analytics Service initialized")
    
    def generate_attendance_report(self, start_date, end_date, department=None):
        """Generate attendance report for given period"""
        try:
            # Convert string dates to datetime if needed
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                # Include the entire end day
                end_date = end_date.replace(hour=23, minute=59, second=59)
            
            # Query parameters
            query = {
                'timestamp__gte': start_date,
                'timestamp__lte': end_date
            }
            
            if department:
                query['department'] = department
            
            # Get all attendance records in the range
            attendance_records = Attendance.objects(**query)
            
            # Get all users
            if department:
                users = User.objects(department=department)
            else:
                users = User.objects()
            
            # Calculate working days in the period
            working_days = self._calculate_working_days(start_date, end_date)
            
            # Create a report for each user
            report = []
            for user in users:
                user_records = [record for record in attendance_records if record.user_id == str(user.id)]
                
                # Get unique dates where the user was present
                present_days = set([record.timestamp.date() for record in user_records])
                
                # Calculate metrics
                attendance_rate = len(present_days) / working_days if working_days > 0 else 0
                absent_days = working_days - len(present_days)
                
                # Calculate average arrival time
                arrival_times = []
                for day in present_days:
                    day_records = [r for r in user_records if r.timestamp.date() == day]
                    if day_records:
                        first_record = min(day_records, key=lambda x: x.timestamp)
                        arrival_times.append(first_record.timestamp.time())
                
                avg_arrival_hour = None
                avg_arrival_minute = None
                if arrival_times:
                
