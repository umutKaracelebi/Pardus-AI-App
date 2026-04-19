import os
import shutil
import datetime

class DocumentEditor:
    def __init__(self):
        pass

    def read_file(self, file_path):
        """Reads the content of a file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def backup_file(self, file_path):
        """Creates a backup of the file before modification."""
        if os.path.exists(file_path):
            directory = os.path.dirname(os.path.abspath(file_path))
            filename = os.path.basename(file_path)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{filename}.{timestamp}.bak"
            backup_path = os.path.join(directory, backup_filename)
            shutil.copy2(file_path, backup_path)
            return backup_path
        return None

    def write_file(self, file_path, content, create_backup=True):
        """Writes content to a file, optionally creating a backup."""
        if create_backup:
            self.backup_file(file_path)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
