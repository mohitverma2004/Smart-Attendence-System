import sqlite3
import datetime
from pymongo import MongoClient
import os

class Database:
    def __init__(self, db_type="sqlite"):
        """Initialize database connection
        
        Args:
            db_type: Type of database to use ('sqlite' or 'mongodb')
        """
        self.db_type = db_type
        
        if db_type == "sqlite":
            # SQLite setup
            self.conn = sqlite3.connect('attendance.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._init_sqlite_db()
        else:
            # MongoDB setup
            mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
            self.client = MongoClient(mongo_uri)
            self.db = self.client['attendance_system']
            self.persons_collection = self.db['persons']
            self.attendance_collection = self.db['attendance']
    
    def _init_sqlite_db(self):
        """Initialize SQLite database tables if they don't exist"""
        # Create persons table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS persons (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create attendance table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES persons (id)
        )
        ''')
        
        self.conn.commit()
    
    def add_person(self, person_id, name):
        """Add a new person to the database"""
        if self.db_type == "sqlite":
            try:
                self.cursor.execute(
                    "INSERT INTO persons (id, name) VALUES (?, ?)",
                    (person_id, name)
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Person already exists
                return False
        else:
            # MongoDB
            try:
                result = self.persons_collection.update_one(
                    {"_id": person_id},
                    {"$set": {"name": name, "created_at": datetime.datetime.utcnow()}},
                    upsert=True
                )
                return result.acknowledged
            except Exception as e:
                print(f"Error adding person: {e}")
                return False
    
    def record_attendance(self, person_id, camera_id):
        """Record attendance for a person"""
        timestamp = datetime.datetime.now()
        
        if self.db_type == "sqlite":
            try:
                self.cursor.execute(
                    "INSERT INTO attendance (person_id, camera_id, timestamp) VALUES (?, ?, ?)",
                    (person_id, camera_id, timestamp)
                )
                self.conn.commit()
                return True
            except Exception as e:
                print(f"Error recording attendance: {e}")
                return False
        else:
            # MongoDB
            try:
                result = self.attendance_collection.insert_one({
                    "person_id": person_id,
                    "camera_id": camera_id,
                    "timestamp": timestamp
                })
                return result.acknowledged
            except Exception as e:
                print(f"Error recording attendance: {e}")
                return False
    
    def get_attendance_by_date(self, date):
        """Get attendance records for a specific date"""
        if self.db_type == "sqlite":
            self.cursor.execute(
                """
                SELECT a.id, p.id, p.name, a.camera_id, a.timestamp 
                FROM attendance a
                JOIN persons p ON a.person_id = p.id
                WHERE date(a.timestamp) = date(?)
                ORDER BY a.timestamp DESC
                """,
                (date,)
            )
            
            columns = ["id", "person_id", "person_name", "camera_id", "timestamp"]
            results = self.cursor.fetchall()
            
            attendance_list = []
            for row in results:
                attendance_list.append(dict(zip(columns, row)))
            
            return attendance_list
        else:
            # MongoDB
            start_date = datetime.datetime.strptime(date, "%Y-%m-%d")
            end_date = start_date + datetime.timedelta(days=1)
            
            pipeline = [
                {
                    "$match": {
                        "timestamp": {
                            "$gte": start_date,
                            "$lt": end_date
                        }
                    }
                },
                {
                    "$lookup": {
                        "from": "persons",
                        "localField": "person_id",
                        "foreignField": "_id",
                        "as": "person"
                    }
                },
                {
                    "$unwind": "$person"
                },
                {
                    "$project": {
                        "_id": 1,
                        "person_id": 1,
                        "person_name": "$person.name",
                        "camera_id": 1,
                        "timestamp": 1
                    }
                },
                {
                    "$sort": {"timestamp": -1}
                }
            ]
            
            results = list(self.attendance_collection.aggregate(pipeline))
            return results
    
    def get_attendance_by_date_range(self, start_date, end_date):
        """Get attendance records for a date range"""
        if self.db_type == "sqlite":
            self.cursor.execute(
                """
                SELECT a.id, p.id, p.name, a.camera_id, a.timestamp 
                FROM attendance a
                JOIN persons p ON a.person_id = p.id
                WHERE date(a.timestamp) BETWEEN date(?) AND date(?)
                ORDER BY a.timestamp DESC
                """,
                (start_date, end_date)
            )
            
            columns = ["id", "person_id", "person_name", "camera_id", "timestamp"]
            results = self.cursor.fetchall()
            
            attendance_list = []
            for row in results:
                attendance_list.append(dict(zip(columns, row)))
            
            return attendance_list
        else:
            # MongoDB
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            
            pipeline = [
                {
                    "$match": {
                        "timestamp": {
                            "$gte": start,
                            "$lt": end
                        }
                    }
                },
                {
                    "$lookup": {
                        "from": "persons",
                        "localField": "person_id",
                        "foreignField": "_id",
                        "as": "person"
                    }
                },
                {
                    "$unwind": "$person"
                },
                {
                    "$project": {
                        "_id": 1,
                        "person_id": 1,
                        "person_name": "$person.name",
                        "camera_id": 1,
                        "timestamp": 1
                    }
                },
                {
                    "$sort": {"timestamp": -1}
                }
            ]
            
            results = list(self.attendance_collection.aggregate(pipeline))
            return results
            
    def __del__(self):
        """Clean up database connections"""
        if self.db_type == "sqlite":
            self.conn.close()
        else:
            self.client.close()
