import os
import requests
import base64

def list_session_children(share_link: str, token: str):
    """
    Helper for the online worker: list all Session_* folders under a OneDrive share link.
    """
    share_id = base64.urlsafe_b64encode(share_link.encode()).decode().rstrip("=")
    url = f"https://graph.microsoft.com/v1.0/shares/u!{share_id}/driveItem/children"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    entries = resp.json().get("value", [])
    return [
        entry
        for entry in entries
        if entry.get("folder") and entry["name"].startswith("Session_")
    ]

def encode_share_link(link):
    encoded_url = base64.urlsafe_b64encode(link.encode()).decode().rstrip("=")
    return f"u!{encoded_url}"

def download_sharepoint_folder(share_link, temp_dir, access_token, file_suffix: list = None):
    headers = {"Authorization": f"Bearer {access_token}"}
    share_id = encode_share_link(share_link)
    root_url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"

    root_response = requests.get(root_url, headers=headers)
    root_response.raise_for_status()
    root_item = root_response.json()

    drive_id = root_item['parentReference']['driveId']
    parent_folder_id = root_item['id']
    session_folder_id_map = {}

    def recursive_collect_files(item, relative_path):
        # If this item is a folder, recurse into it
        if "folder" in item:
            folder_path = os.path.join(temp_dir, relative_path, item['name'])
            os.makedirs(folder_path, exist_ok=True)

            if item['name'].startswith("Session_"):
                session_folder_id_map[item['name']] = item['id']

            children_url = (
                f"https://graph.microsoft.com/v1.0/drives/"
                f"{item['parentReference']['driveId']}/items/{item['id']}/children"
            )
            resp = requests.get(children_url, headers=headers)
            resp.raise_for_status()
            for child in resp.json().get('value', []):
                recursive_collect_files(child, os.path.join(relative_path, item['name']))

        # Otherwise, it's a file—check suffix and download if allowed
        else:
            name = item['name']
            # if no suffix filter given, or name ends with any of the allowed suffixes
            if file_suffix is None or any(name.lower().endswith(s.lower()) for s in file_suffix):
                file_folder = os.path.join(temp_dir, relative_path)
                os.makedirs(file_folder, exist_ok=True)
                file_path = os.path.join(file_folder, name)

                download_url = item.get("@microsoft.graph.downloadUrl")
                if download_url:
                    r = requests.get(download_url, stream=True)
                    r.raise_for_status()
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

    recursive_collect_files(root_item, relative_path="")
    return temp_dir, drive_id, parent_folder_id, session_folder_id_map


def upload_file_replace_in_onedrive(local_file_path, target_drive_id, parent_folder_id, file_name_in_folder, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream"
    }

    upload_url = f"https://graph.microsoft.com/v1.0/drives/{target_drive_id}/items/{parent_folder_id}:/{file_name_in_folder}:/content"

    with open(local_file_path, 'rb') as f:
        response = requests.put(upload_url, headers=headers, data=f)

    if response.status_code not in (200, 201):
        raise Exception(f"Failed to upload/replace file: {response.text}")

    return response.json()
