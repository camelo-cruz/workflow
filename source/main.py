import threading
import torch
import os
import signal
import msal  # pip install msal
import requests
import tkinter as tk
from ttkthemes import ThemedTk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import webbrowser

from functions import get_materials_path
from Transcriber import Transcriber
from Translator import Translator
from Transliterator import Transliterator
from SentenceSelector import SentenceSelector
from Glosser import Glosser

cancel_flag = False
device = 'cuda' if torch.cuda.is_available() else 'cpu'
app_closing = False  # Global shutdown flag

# Global variables for folder selection and OneDrive token
local_folder_path = None        # Holds full local folder path if selected locally
selected_folder_id = None       # Holds OneDrive folder ID if selected via OneDrive
drive_id = None                # Holds OneDrive drive ID if selected via OneDrive
onedrive_token = None           # Cached OneDrive token (remains logged in)

# --------------------- Processing Functions ---------------------

def process_transcribe(input_dir, language, verbose, status_label):
    try:
        msg = "Starting transcription..."
        status_label.config(text=msg)
        print(msg)
        # Transcriber will use the global onedrive_token if needed.
        transcriber = Transcriber(input_dir, language, device=device, drive_id=drive_id, onedrive_token=onedrive_token)
        transcriber.process_data(verbose=verbose)
        msg = "Transcription completed."
        status_label.config(text=msg)
        print("Transcription completed")
    except Exception as local_e:
        status_label.config(text=f"Local error: {local_e}")
        print(f"Local error: {local_e}")

def process_translate(input_dir, language, instruction, verbose, status_label):
    try:
        msg = "Starting translation..."
        status_label.config(text=msg)
        print(msg)
        translator = Translator(input_dir, language, instruction, device=device)
        translator.process_data(verbose=verbose)
        msg = "Translation completed."
        status_label.config(text=msg)
        print(msg)
    except Exception as e:
        msg = f"Error: {e}"
        status_label.config(text=msg)
        print(msg)

def process_gloss(input_dir, language, instruction, status_label):
    try:
        msg = "Starting glossing..."
        status_label.config(text=msg)
        print(msg)
        glosser = Glosser(input_dir, language, instruction, device=device)
        glosser.process_data()
        msg = "Glossing completed."
        status_label.config(text=msg)
        print(msg)
    except Exception as e:
        msg = f"Error: {e}"
        status_label.config(text=msg)
        print(msg)

def process_transliterate(input_dir, language, instruction, status_label):
    try:
        msg = "Starting transliteration..."
        status_label.config(text=msg)
        print(msg)
        transliterator = Transliterator(input_dir, language, instruction, device=device)
        transliterator.process_data()
        msg = "Transliteration completed."
        status_label.config(text=msg)
        print(msg)
    except Exception as e:
        msg = f"Error: {e}"
        status_label.config(text=msg)
        print(msg)

def process_sentence_selection(input_dir, language, study, verbose, status_label):
    try:
        msg = "Starting sentence selection..."
        status_label.config(text=msg)
        print(msg)
        sentence_selector = SentenceSelector(input_dir, language, study, device=device)
        sentence_selector.process_data(verbose=verbose)
        msg = "Sentence selection completed."
        status_label.config(text=msg)
        print(msg)
    except Exception as e:
        msg = f"Error: {e}"
        status_label.config(text=msg)
        print(msg)

# --------------------- OneDrive Helper Functions ---------------------

def list_shared_files(access_token):
    """Retrieve shared items from OneDrive with a timeout."""
    if app_closing:
        return []
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://graph.microsoft.com/v1.0/me/drive/sharedWithMe"
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        print("Network error in list_shared_files:", e)
        return []
    if response.ok:
        return response.json().get("value", [])
    else:
        print("Error retrieving shared files:", response.text)
        return []

def list_folder_contents(access_token, drive_id, folder_id):
    """Retrieve the children of a given folder from OneDrive with a timeout."""
    if app_closing:
        return []
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        print("Network error in list_folder_contents:", e)
        return []
    if response.ok:
        return response.json().get("value", [])
    else:
        print("Error retrieving folder contents:", response.text)
        return []

def open_shared_files_window(access_token, shared_files):
    """Open an improved OneDrive shared files window with lazy loading, scrollability, and folder selection."""
    shared_window = tk.Toplevel(window)
    shared_window.title("Shared Files")
    shared_window.geometry("600x400")
    
    # Create a frame for the Treeview and its scrollbar
    frame = ttk.Frame(shared_window)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    scrollbar = ttk.Scrollbar(frame, orient="vertical")
    tree = ttk.Treeview(frame, columns=("id", "drive_id"), yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    
    # Configure tree headings and column widths
    tree.heading("#0", text="Name")
    tree.heading("id", text="ID")
    tree.heading("drive_id", text="Drive ID")
    tree.column("#0", width=250)
    tree.column("id", width=150)
    tree.column("drive_id", width=150)
    
    # Insert top-level shared items
    for item in shared_files:
        if "remoteItem" in item:
            remote = item["remoteItem"]
            drive_id = remote.get("parentReference", {}).get("driveId")
            folder_id = remote.get("id")
            name = remote.get("name")
            is_folder = remote.get("folder") is not None
        else:
            drive_id = item.get("parentReference", {}).get("driveId")
            folder_id = item.get("id")
            name = item.get("name", "Unknown")
            is_folder = item.get("folder") is not None
        
        node = tree.insert("", "end", text=name, values=(folder_id, drive_id))
        # For folders, add a dummy child for lazy loading.
        if is_folder:
            tree.insert(node, "end", text="dummy")
    
    def on_open_node(event):
        """When a node is expanded, load its children if a dummy exists."""
        node = tree.focus()
        children = tree.get_children(node)
        if children:
            first_child = children[0]
            if tree.item(first_child, "text") == "dummy":
                tree.delete(first_child)
                values = tree.item(node, "values")
                if not values or len(values) < 2:
                    return
                global drive_id
                folder_id = values[0]  # The folder's ID
                drive_id = values[1]   # The drive ID
                print(f"Expanding folder {folder_id} in drive {drive_id}")  # Debug logging
                children_items = list_folder_contents(access_token, drive_id, folder_id)
                if not children_items:
                    print("No children found or error listing children.")
                for child in children_items:
                    if "remoteItem" in child:
                        remote = child["remoteItem"]
                        child_drive_id = remote.get("parentReference", {}).get("driveId")
                        child_id = remote.get("id")
                        child_name = remote.get("name")
                        is_child_folder = remote.get("folder") is not None
                    else:
                        child_drive_id = child.get("parentReference", {}).get("driveId")
                        child_id = child.get("id")
                        child_name = child.get("name", "Unknown")
                        is_child_folder = child.get("folder") is not None
                    child_node = tree.insert(node, "end", text=child_name, values=(child_id, child_drive_id))
                    if is_child_folder:
                        tree.insert(child_node, "end", text="dummy")
    
    # Bind the event for expanding a node to load its children
    tree.bind("<<TreeviewOpen>>", on_open_node)
    
    def select_folder():
        selected_items = tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a folder.")
            return
        node = selected_items[0]
        folder_name = tree.item(node, "text")
        values = tree.item(node, "values")
        if not values or len(values) < 2:
            messagebox.showerror("Error", "Invalid selection.")
            return
        folder_id = values[0]
        drive_id = values[1]  # You may store this globally if needed.
        # For OneDrive, update the global folder variable and show folder name
        global selected_folder_id, local_folder_path
        print(f"Selected folder ID: {folder_id}, Drive ID: {drive_id}")  # Debug logging
        selected_folder_id = folder_id
        local_folder_path = None
        folder_var.set(folder_name)
        messagebox.showinfo("Folder Selected", f"Folder '{folder_name}' selected.")
        shared_window.destroy()
    
    # Only the button triggers folder selection now.
    select_button = ttk.Button(shared_window, text="Select Folder", command=select_folder)
    select_button.pack(pady=5)

def sign_in_onedrive():
    """Start OneDrive authentication in a separate thread."""
    threading.Thread(target=sign_in_onedrive_thread, daemon=True).start()

def sign_in_onedrive_thread():
    """
    Run the device code flow in a background thread.
    Schedule UI updates via window.after() so they run in the main thread.
    """
    global onedrive_token
    # If already logged in, try reusing the token
    if onedrive_token is not None:
        shared_files = list_shared_files(onedrive_token)
        if shared_files:
            window.after(0, lambda: open_shared_files_window(onedrive_token, shared_files))
            return
        else:
            onedrive_token = None

    # Replace with your Azure app's details
    client_id = '58c0d230-141d-4a30-905e-fd63e331e5ea'
    tenant_id = '7ef3035c-bf11-463a-ab3b-9a9a4ac82500'
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["Files.ReadWrite.All", "User.Read"]

    app = msal.PublicClientApplication(client_id, authority=authority)
    flow = app.initiate_device_flow(scopes=scope)
    if "user_code" not in flow:
        window.after(0, lambda: messagebox.showerror("Error", "Failed to create device flow."))
        return

    window.after(0, lambda: messagebox.showinfo("Device Code", flow["message"]))
    webbrowser.open(flow["verification_uri"])

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        onedrive_token = result["access_token"]
        shared_files = list_shared_files(onedrive_token)
        if shared_files:
            window.after(0, lambda: open_shared_files_window(onedrive_token, shared_files))
        else:
            window.after(0, lambda: messagebox.showinfo("Shared Files", "No shared files found."))
    else:
        window.after(0, lambda: messagebox.showerror("Error", "Authentication failed: " + result.get("error_description", "")))

def local_search():
    """Allow the user to select a local folder."""
    global local_folder_path, selected_folder_id
    folder = filedialog.askdirectory(title="Select Local Folder")
    if folder:
        local_folder_path = folder
        selected_folder_id = None
        folder_var.set(os.path.basename(folder))
        messagebox.showinfo("Local Folder Selected", f"Local folder '{os.path.basename(folder)}' selected.")

def start_processing():
    global local_folder_path, selected_folder_id
    if local_folder_path is not None:
        input_dir = local_folder_path
    elif selected_folder_id is not None:
        input_dir = selected_folder_id
    else:
        messagebox.showerror("Error", "Please select a folder (OneDrive or Local).")
        return
    
    print("Input directory:", input_dir)
    language = language_var.get()
    instruction_or_study = instruction_var.get()
    verbose = verbose_var.get()
    status_label.config(text="Processing...")
    print("Processing...")

    if not input_dir:
        messagebox.showerror("Error", "Please select a folder.")
        return

    action = action_var.get()
    if action == "Transcribe":
        threading.Thread(target=process_transcribe, args=(input_dir, language, verbose, status_label), daemon=True).start()
    elif action == "Translate":
        threading.Thread(target=process_translate, args=(input_dir, language, instruction_or_study, verbose, status_label), daemon=True).start()
    elif action == "Gloss":
        threading.Thread(target=process_gloss, args=(input_dir, language, instruction_or_study, status_label), daemon=True).start()
    elif action == "Transliterate":
        threading.Thread(target=process_transliterate, args=(input_dir, language, instruction_or_study, status_label), daemon=True).start()
    elif action == "Select sentences":
        threading.Thread(target=process_sentence_selection, args=(input_dir, language, instruction_or_study, verbose, status_label), daemon=True).start()
    else:
        messagebox.showerror("Error", "Please select a valid action.")

def on_closing():
    global app_closing
    app_closing = True
    window.destroy()
    os.kill(os.getpid(), signal.SIGKILL)

def main():
    global folder_var, language_var, instruction_var, verbose_var, action_var, status_label, window

    window = ThemedTk(theme="arc")
    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.geometry("862x519")
    window.resizable(False, False)
    window.title("Tkinter Designer Example")

    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TCombobox", foreground="black", fieldbackground="white", background="white", arrowcolor="black")
    style.configure("TEntry", foreground="black", fieldbackground="white", background="white")
    style.configure("Blue.TButton", background="#9B0A0A", foreground="white", font=("Inter", 13),
                    borderwidth=0, relief="flat", anchor="center")
    style.map("Blue.TButton", background=[("active", "#7F0707"), ("disabled", "#A9A9A9")],
              foreground=[("active", "white"), ("disabled", "white")])
    style.configure("White.TButton", background="white", foreground="#7F0707", font=("Inter", 11),
                    borderwidth=0, relief="flat", anchor="center")
    style.map("White.TButton", background=[("active", "white"), ("disabled", "#A9A9A9")],
              foreground=[("active", "#7F0707"), ("disabled", "#7F0707")])

    canvas = tk.Canvas(window, width=862, height=519, bd=0, highlightthickness=0, relief="ridge")
    canvas.place(x=0, y=0)
    wine_red = "#7F0707"
    canvas.create_rectangle(0, 0, 431, 519, fill=wine_red, outline="")
    canvas.create_rectangle(431, 0, 862, 519, fill="#FCFCFC", outline="")

    action_label = tk.Label(window, text="Action:", bg=wine_red, fg="white", font=("Inter", 13))
    action_label.place(x=80, y=40)
    action_var = tk.StringVar()
    action_combo = ttk.Combobox(window, textvariable=action_var,
                                values=["Transcribe", "Translate", "Gloss", "Transliterate", "Select sentences"],
                                state="readonly")
    action_combo.place(x=80, y=70, width=275, height=30)

    folder_label = tk.Label(window, text="Folder:", bg=wine_red, fg="white", font=("Inter", 13))
    folder_label.place(x=80, y=110)
    folder_var = tk.StringVar()
    folder_entry = ttk.Entry(window, textvariable=folder_var)
    folder_entry.place(x=80, y=140, width=275, height=30)

    onedrive_button = ttk.Button(window, text="OneDrive", style="White.TButton", command=sign_in_onedrive)
    onedrive_button.place(x=80, y=180, width=130, height=30)

    local_search_button = ttk.Button(window, text="Local Search", style="White.TButton", command=local_search)
    local_search_button.place(x=220, y=180, width=130, height=30)

    instruction_label = tk.Label(window, text="For Translation, Gloss, Transliteration:", bg=wine_red, fg="white", font=("Inter", 13))
    instruction_label.place(x=80, y=220)
    instruction_var = tk.StringVar()
    instruction_combo = ttk.Combobox(window, textvariable=instruction_var, values=["automatic", "corrected", "sentences"], state="readonly")
    instruction_combo.place(x=80, y=250, width=275, height=30)

    def update_instruction_box(event):
        selected_action = action_var.get()
        if selected_action == "Select sentences":
            instruction_label.config(text="Study:")
            instruction_combo.config(values=[], state="normal")
            instruction_combo.set("")
        elif selected_action in ["Translate", "Gloss", "Transliterate"]:
            instruction_label.config(text="Instruction:")
            instruction_combo.config(values=["automatic", "corrected", "sentences"], state="readonly")
            instruction_combo.set("automatic")
        else:
            instruction_label.config(text="Instruction:")
            instruction_combo.set("")
            instruction_combo.config(state="disabled")

    action_combo.bind("<<ComboboxSelected>>", update_instruction_box)
    instruction_combo.config(state="disabled")

    language_label = tk.Label(window, text="Language:", bg=wine_red, fg="white", font=("Inter", 13))
    language_label.place(x=80, y=290)
    language_var = tk.StringVar()
    language_entry = ttk.Entry(window, textvariable=language_var)
    language_entry.place(x=80, y=320, width=275, height=30)

    verbose_label = tk.Label(window, text="Verbose output:", bg=wine_red, fg="white", font=("Inter", 13))
    verbose_label.place(x=80, y=360)
    verbose_var = tk.BooleanVar(value=False)
    verbose_radiobutton = tk.Radiobutton(window, variable=verbose_var, value=True, bg=wine_red)
    verbose_radiobutton.place(x=220, y=362)

    status_label = tk.Label(window, text="", bg="#FCFCFC", fg="black", font=("Inter", 12))
    status_label.place(x=450, y=470)

    offset_x = 431
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, 'materials', 'zas_logo.jpg')
        pil_image = Image.open(get_materials_path(image_path))
        box_x1, box_y1 = 162 + offset_x, 111
        box_x2, box_y2 = 269 + offset_x, 218
        box_width = box_x2 - box_x1
        box_height = box_y2 - box_y1
        orig_width, orig_height = pil_image.size
        aspect_ratio = orig_width / orig_height
        box_ratio = box_width / box_height
        if aspect_ratio > box_ratio:
            new_width = box_width
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = box_height
            new_width = int(new_height * aspect_ratio)
        pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
        process_image = ImageTk.PhotoImage(pil_image)
        image_x = box_x1 + (box_width - new_width) // 2
        image_y = box_y1 + (box_height - new_height) // 2
        canvas.create_image(image_x, image_y, anchor="nw", image=process_image)
        canvas.process_image = process_image
        text_x = image_x + new_width / 2
        text_y = image_y + new_height + 20
        canvas.create_text(text_x, text_y, text="LeibnizDream", fill="black", font=("Inter", 14))
    except Exception as e:
        print("Could not load image:", e)

    process_button = ttk.Button(window, text="Process", style="Blue.TButton", command=start_processing)
    process_button.place(x=119 + offset_x, y=315, width=189, height=55)

    window.mainloop()

if __name__ == "__main__":
    main()