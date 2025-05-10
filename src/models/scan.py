class Scan:
    """Model representing a scan job"""
    
    def __init__(self, id, directory, content_type, status, start_time, 
                 end_time=None, total_files=0, processed_files=0, 
                 error_message=None):
        self.id = id
        self.directory = directory
        self.content_type = content_type
        self.status = status
        self.start_time = start_time
        self.end_time = end_time
        self.total_files = total_files
        self.processed_files = processed_files
        self.error_message = error_message
    
    def to_dict(self):
        """Convert scan to dictionary"""
        return {
            'id': self.id,
            'directory': self.directory,
            'content_type': self.content_type,
            'status': self.status,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'progress': self.processed_files / self.total_files if self.total_files > 0 else 0,
            'error_message': self.error_message
        }