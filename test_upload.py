import os
import json
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Load environment variables from .env
load_dotenv()

def test_drive_upload():
    print("Testing Google Drive Upload...")
    
    creds_json = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')
    folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
    
    if not creds_json or not folder_id:
        print("ERROR: GOOGLE_DRIVE_CREDENTIALS or GOOGLE_DRIVE_FOLDER_ID is missing from .env")
        return
        
    try:
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        drive_service = build('drive', 'v3', credentials=creds)
        print("SUCCESS: Authenticated with Google Drive API successfully.")
    except Exception as e:
        print(f"ERROR: Authentication Failed: {e}")
        return

    # Image path in Downloads
    image_path = r"c:\Users\tapes\Downloads\ChatGPT Image May 10, 2026, 02_09_06 AM.png"
    
    if not os.path.exists(image_path):
        print(f"ERROR: Cannot find the image file at {image_path}")
        return
        
    print(f"Found image: {os.path.basename(image_path)}")
    
    try:
        file_metadata = {
            'name': 'test_upload_scooter.png',
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(image_path, mimetype='image/png', resumable=True)
        
        print(f"Uploading to folder ID: {folder_id} ...")
        uploaded_file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id', 
            supportsAllDrives=True
        ).execute()
        
        file_id = uploaded_file.get('id')
        print(f"SUCCESS: File uploaded successfully! File ID: {file_id}")
        
        # Set permissions to anyone with link can view
        drive_service.permissions().create(
            fileId=file_id, 
            body={'type': 'anyone', 'role': 'reader'},
            supportsAllDrives=True
        ).execute()
        
        print(f"SUCCESS: Permissions updated. Image is publicly viewable.")
        print(f"\nIMAGE URL: https://drive.google.com/uc?id={file_id}")
        
    except Exception as e:
        print(f"ERROR: Upload Failed: {e}")

if __name__ == "__main__":
    test_drive_upload()
