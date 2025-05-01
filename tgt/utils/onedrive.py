# utils/onedrive.py

import os
import tempfile
import requests
import msal
import base64
import json

TENANT_ID = '7ef3035c-bf11-463a-ab3b-9a9a4ac82500'
CLIENT_ID = '58c0d230-141d-4a30-905e-fd63e331e5ea'

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Files.ReadWrite.All", "User.Read"]

TOKEN_CACHE_DIR = os.environ.get("TOKEN_CACHE_DIR", os.path.expanduser("~"))
TOKEN_CACHE_FILE = os.path.join(TOKEN_CACHE_DIR, ".onedrive_token_cache.json")

def clear_token_cache():
    if os.path.exists(TOKEN_CACHE_FILE):
        os.remove(TOKEN_CACHE_FILE)

def get_graph_token(force_reauth=False):
    if force_reauth:
        clear_token_cache()
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPES)
    uri = flow.get("verification_uri")
    code = flow.get("user_code")
    if "user_code" not in flow:
        raise Exception("Failed to create device flow")

    print(
    f'go to {uri} and insert code: {code}',
    flush=True
    )

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())
        return result["access_token"]
    else:
        raise Exception(f"Could not obtain access token: {result}")

def encode_share_link(link):
    encoded_url = base64.urlsafe_b64encode(link.encode()).decode().rstrip("=")
    return f"u!{encoded_url}"

def download_sharepoint_folder(share_link, temp_dir, force_reauth=False):
    access_token = get_graph_token(force_reauth)
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
        if "folder" in item:
            folder_path = os.path.join(temp_dir, relative_path, item['name'])
            os.makedirs(folder_path, exist_ok=True)

            drive_id_inner = item['parentReference']['driveId']
            item_id = item['id']
            children_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id_inner}/items/{item_id}/children"

            children_response = requests.get(children_url, headers=headers)
            children_response.raise_for_status()
            children = children_response.json().get('value', [])

            # If it's a session folder (e.g., Session_1237316), remember its ID
            if item['name'].startswith("Session_"):
                session_folder_id_map[item['name']] = item['id']

            for child in children:
                recursive_collect_files(child, os.path.join(relative_path, item['name']))

        else:
            file_folder = os.path.join(temp_dir, relative_path)
            os.makedirs(file_folder, exist_ok=True)

            filename = item['name']
            file_path = os.path.join(file_folder, filename)

            download_url = item.get("@microsoft.graph.downloadUrl")
            if download_url:
                r = requests.get(download_url, stream=True)
                r.raise_for_status()

                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

    recursive_collect_files(root_item, relative_path="")

    return temp_dir, drive_id, parent_folder_id, session_folder_id_map

def upload_file_replace_in_onedrive(local_file_path, target_drive_id, parent_folder_id, file_name_in_folder):
    access_token = get_graph_token()
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
