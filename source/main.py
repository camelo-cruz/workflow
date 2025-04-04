import threading
import torch
import os
import msal  # Make sure to install msal (pip install msal)
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from functions import get_materials_path
from Transcriber import Transcriber
from Translator import Translator
from Transliterator import Transliterator
from SentenceSelector import SentenceSelector
from Glosser import Glosser

cancel_flag = False
device = 'cuda' if torch.cuda.is_available() else 'cpu'


def process_transcribe(input_dir, language, verbose, status_label):
    try:
        msg = "Starting transcription..."
        status_label.config(text=msg)
        print(msg)
        transcriber = Transcriber(input_dir, language, device=device)
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


def sign_in_onedrive():
    """
    This function initiates a device code flow to authenticate the user with OneDrive,
    then lists the folders in the OneDrive root and opens a window for the user to select one.
    """
    global window, folder_var

    # Replace these with your Azure app's details
    client_id = '58c0d230-141d-4a30-905e-fd63e331e5ea'
    tenant_id = '7ef3035c-bf11-463a-ab3b-9a9a4ac82500'
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["Files.ReadWrite.All", "User.Read"]

    app = msal.PublicClientApplication(client_id, authority=authority)
    flow = app.initiate_device_flow(scopes=scope)
    if "user_code" not in flow:
        messagebox.showerror("Error", "Failed to create device flow.")
        return

    # Show the device code message to the user
    messagebox.showinfo("Device Code", flow["message"])

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        access_token = result["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get("https://graph.microsoft.com/v1.0/me/drive/root/children", headers=headers)
        if response.ok:
            files = response.json().get("value", [])
            # Filter for folders (each folder will have a 'folder' key)
            folders = [f for f in files if f.get('folder')]
            if not folders:
                messagebox.showerror("Error", "No folders found in your OneDrive root.")
                return

            # Create a new window for folder selection
            select_window = tk.Toplevel(window)
            select_window.title("Select OneDrive Folder")
            listbox = tk.Listbox(select_window, width=50)
            listbox.pack(padx=10, pady=10)

            # Create a mapping from display name to folder ID
            folder_map = {}
            for folder in folders:
                display_name = folder.get('name')
                folder_map[display_name] = folder.get('id')
                listbox.insert(tk.END, display_name)

            def select_folder():
                selection = listbox.curselection()
                if selection:
                    selected_name = listbox.get(selection[0])
                    # Save the folder ID in folder_var (this is used by your processing functions)
                    folder_var.set(folder_map[selected_name])
                    select_window.destroy()
                else:
                    messagebox.showerror("Error", "Please select a folder.")

            select_button = ttk.Button(select_window, text="Select", command=select_folder)
            select_button.pack(pady=5)
        else:
            messagebox.showerror("Error", "Failed to list OneDrive folders: " + response.text)
    else:
        messagebox.showerror("Error", "Authentication failed: " + result.get("error_description", ""))


def start_processing():
    input_dir = folder_var.get()  # Now this contains the OneDrive folder ID
    language = language_var.get()
    instruction_or_study = instruction_var.get()
    verbose = verbose_var.get()
    status_label.config(text="Processing...")
    print("Processing...")

    if not input_dir:
        messagebox.showerror("Error", "Please select a OneDrive folder.")
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


def main():
    global folder_var, language_var, instruction_var, verbose_var, action_var, status_label, window

    window = tk.Tk()
    window.geometry("862x519")
    window.resizable(False, False)
    window.title("Tkinter Designer Example")

    style = ttk.Style()
    style.theme_use("clam")

    # Configure combobox and entry styles
    style.configure("TCombobox", foreground="black", fieldbackground="white", background="white", arrowcolor="black")
    style.configure("TEntry", foreground="black", fieldbackground="white", background="white")
    style.configure("Blue.TButton", background="#9B0A0A", foreground="white", font=("Inter", 13), borderwidth=0, relief="flat", anchor="center")
    style.map("Blue.TButton", background=[("active", "#7F0707"), ("disabled", "#A9A9A9")], foreground=[("active", "white"), ("disabled", "white")])
    style.configure("White.TButton", background="white", foreground="#7F0707", font=("Inter", 11), borderwidth=0, relief="flat", anchor="center")
    style.map("White.TButton", background=[("active", "white"), ("disabled", "#A9A9A9")], foreground=[("active", "#7F0707"), ("disabled", "#7F0707")])

    # BACKGROUND CANVAS for color panels
    canvas = tk.Canvas(window, width=862, height=519, bd=0, highlightthickness=0, relief="ridge")
    canvas.place(x=0, y=0)
    wine_red = "#7F0707"
    canvas.create_rectangle(0, 0, 431, 519, fill=wine_red, outline="")
    canvas.create_rectangle(431, 0, 862, 519, fill="#FCFCFC", outline="")

    # LEFT SIDE (wine-red background)
    # 1) Action
    action_label = tk.Label(window, text="Action:", bg=wine_red, fg="white", font=("Inter", 13))
    action_label.place(x=80, y=40)
    action_var = tk.StringVar()
    action_combo = ttk.Combobox(window, textvariable=action_var,
                                values=["Transcribe", "Translate", "Gloss", "Transliterate", "Select sentences"],
                                state="readonly")
    action_combo.place(x=80, y=70, width=275, height=30)

    # 2) OneDrive Folder (instead of local folder)
    folder_label = tk.Label(window, text="OneDrive Folder ID:", bg=wine_red, fg="white", font=("Inter", 13))
    folder_label.place(x=80, y=110)
    folder_var = tk.StringVar()
    folder_entry = ttk.Entry(window, textvariable=folder_var)
    folder_entry.place(x=80, y=140, width=275, height=30)

    # Button to sign in to OneDrive and select a folder
    onedrive_button = ttk.Button(window, text="Sign in to OneDrive", style="White.TButton", command=sign_in_onedrive)
    onedrive_button.place(x=80, y=180, width=275, height=30)

    # 3) Instruction / Study Name
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

    # 4) Language
    language_label = tk.Label(window, text="Language:", bg=wine_red, fg="white", font=("Inter", 13))
    language_label.place(x=80, y=290)
    language_var = tk.StringVar()
    language_entry = ttk.Entry(window, textvariable=language_var)
    language_entry.place(x=80, y=320, width=275, height=30)

    # 5) Verbose
    verbose_label = tk.Label(window, text="Verbose output:", bg=wine_red, fg="white", font=("Inter", 13))
    verbose_label.place(x=80, y=360)
    verbose_var = tk.BooleanVar(value=False)
    verbose_radiobutton = tk.Radiobutton(window, variable=verbose_var, value=True, bg=wine_red)
    verbose_radiobutton.place(x=220, y=362)

    # Status label for output messages
    status_label = tk.Label(window, text="", bg="#FCFCFC", fg="black", font=("Inter", 12))
    status_label.place(x=450, y=470)

    # RIGHT SIDE (white background)
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

    # Process button
    process_button = ttk.Button(window, text="Process", style="Blue.TButton", command=start_processing)
    process_button.place(x=119 + offset_x, y=315, width=189, height=55)

    window.mainloop()


if __name__ == "__main__":
    main()
