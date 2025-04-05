import requests
import os
import tempfile

#--- Helper functions for OneDrive operations ---

def recursive_list_files(access_token, drive_id, folder_id):
    """
    Recursively list all audio files (.mp3, .mp4, .m4a) found in folders named 'binaries'
    within a OneDrive folder.
    Returns a flat list of file items.
    """
    all_files = []
    items = list_online_files(access_token, drive_id, folder_id)
    for item in items:
        is_binaries = item.get("name", "").lower() == "binaries"
        if is_binaries:
            # Get the subfolder's id and drive id.
            sub_folder_id = item.get("id")
            print(f"Binaries subfolder ID: {sub_folder_id}")
            # List the immediate files in this "binaries" folder.
            sub_files = list_online_files(access_token, drive_id, sub_folder_id)
            for sub_file in sub_files:
                if sub_file.get("name", "").lower().endswith(('.mp3', '.mp4', '.m4a')):
                    all_files.append(sub_file)
    return all_files


def list_online_files(access_token, drive_id, folder_id):
    """
    List files in a OneDrive folder (online).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        print("Network error in list_online_files: " + str(e))
        return []
    if response.ok:
        return response.json().get("value", [])
    else:
        print("Error listing online files: " + response.text)
        return []
    

def download_file_to_temp(access_token, drive_id, file_id, suffix=""):
    """
    Download a file from OneDrive to a temporary file.
    Returns the path to the temporary file.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/content"
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=10)
    except requests.RequestException as e:
        raise Exception("Network error while downloading file: " + str(e))
    if not response.ok:
        raise Exception("Error downloading file: " + response.text)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        temp_file.close()
        os.remove(temp_file.name)
        raise e

def upload_file_to_onedrive(access_token, drive_id, parent_item_id, file_path, file_name):
    """
    Upload a file to OneDrive under the specified parent folder.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{parent_item_id}:/{file_name}:/content"
    with open(file_path, 'rb') as file_stream:
        response = requests.put(upload_url, headers=headers, data=file_stream)
    if response.ok:
        print("File uploaded successfully.")
    else:
        print("Error uploading file: " + response.text)



