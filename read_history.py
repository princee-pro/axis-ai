import os
import sqlite3
import shutil

def main():
    history_path = os.path.expanduser(r'~\AppData\Local\Google\Chrome\User Data\Default\History')
    temp_history = 'chrome_history_copy'
    
    if not os.path.exists(history_path):
        print(f"History not found at {history_path}")
        return

    try:
        shutil.copy2(history_path, temp_history)
        conn = sqlite3.connect(temp_history)
        cursor = conn.cursor()
        
        # Look for the redirect URL
        cursor.execute("SELECT url, last_visit_time FROM urls WHERE url LIKE '%localhost:60022%' ORDER BY last_visit_time DESC LIMIT 5")
        rows = cursor.fetchall()
        
        for row in rows:
            print(f"Found URL: {row[0]}")
            
        conn.close()
        os.remove(temp_history)
    except Exception as e:
        print(f"Error reading history: {e}")

if __name__ == "__main__":
    main()
