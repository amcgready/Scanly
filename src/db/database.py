# Assuming this file already exists, add these methods:

def add_scan(self, scan):
    """Add a new scan to the database"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scans (
                id, directory, content_type, status, start_time, 
                end_time, total_files, processed_files, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan.id, scan.directory, scan.content_type, scan.status, 
            scan.start_time, scan.end_time, scan.total_files, 
            scan.processed_files, scan.error_message
        ))
        conn.commit()

def get_scan(self, scan_id):
    """Get scan information by ID"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM scans WHERE id = ?', (scan_id,))
        row = cursor.fetchone()
        
        if row:
            from models.scan import Scan
            return Scan(
                id=row['id'],
                directory=row['directory'],
                content_type=row['content_type'],
                status=row['status'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                total_files=row['total_files'],
                processed_files=row['processed_files'],
                error_message=row['error_message']
            )
        return None

def update_scan_status(self, scan_id, status, error_message=None):
    """Update scan status"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        if error_message:
            cursor.execute(
                'UPDATE scans SET status = ?, error_message = ? WHERE id = ?', 
                (status, error_message, scan_id)
            )
        else:
            cursor.execute(
                'UPDATE scans SET status = ? WHERE id = ?', 
                (status, scan_id)
            )
        conn.commit()

def update_scan_progress(self, scan_id, processed_files, total_files):
    """Update scan progress"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE scans SET processed_files = ?, total_files = ? WHERE id = ?', 
            (processed_files, total_files, scan_id)
        )
        conn.commit()

def update_scan_end_time(self, scan_id, end_time):
    """Update scan end time"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE scans SET end_time = ? WHERE id = ?', 
            (end_time, scan_id)
        )
        conn.commit()

def get_scan_results(self, scan_id):
    """Get results for a scan"""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM processed_files
            WHERE scan_id = ?
            ORDER BY processed_at DESC
        ''', (scan_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'path': row['file_path'],
                'title': row['title'],
                'year': row['year'],
                'success': row['status'] == 'success',
                'message': row['message']
            })
        return results