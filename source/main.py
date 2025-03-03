import threading
import torch
from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

cancel_flag = False
device = 'cuda' if torch.cuda.is_available() else 'cpu'

def process_transcribe(input_dir, language, verbose, status_label):
    try:
        status_label.config(text="Starting transcription...")
        transcriber = Transcriber(input_dir, language, device=device)
        transcriber.process_data(verbose=verbose)
        status_label.config(text="Transcription completed.")
    except Exception as e:
        status_label.config(text=f"Error: {e}")

def process_translate(input_dir, language, instruction, verbose, status_label):
    try:
        status_label.config(text="Starting translation...")
        translator = Translator(input_dir, language, instruction, device=device)
        translator.process_data(verbose=verbose)
        status_label.config(text="Translation completed.")
    except Exception as e:
        status_label.config(text=f"Error: {e}")

def process_gloss(input_dir, language, instruction, status_label):
    try:
        status_label.config(text="Starting glossing...")
        glosser = Glosser(input_dir, language, instruction)
        glosser.process_data()
        status_label.config(text="Glossing completed.")
    except Exception as e:
        status_label.config(text=f"Error: {e}")

def start_processing():
    input_dir = folder_var.get()
    language = language_var.get()
    instruction = instruction_var.get()
    verbose = verbose_var.get()
    status_label.config(text="Processing...")
    
    if not input_dir:
        messagebox.showerror("Error", "Please select an input directory.")
        return

    action = action_var.get()
    if action == "Transcribe":
        threading.Thread(target=process_transcribe, args=(input_dir, language, verbose, status_label), daemon=True).start()
    elif action == "Translate":
        threading.Thread(target=process_translate, args=(input_dir, language, instruction, verbose, status_label), daemon=True).start()
    elif action == "Gloss":
        threading.Thread(target=process_gloss, args=(input_dir, language, instruction, status_label), daemon=True).start()
    else:
        messagebox.showerror("Error", "Please select a valid action.")

window = tk.Tk()
window.geometry("862x519")
window.resizable(False, False)
window.title("Tkinter Designer Example")

style = ttk.Style()
style.theme_use("clam")

# Configure comboboxes & entries
style.configure(
    "TCombobox",
    foreground="black",
    fieldbackground="white",
    background="white",
    arrowcolor="black"
)
style.configure(
    "TEntry",
    foreground="black",
    fieldbackground="white",
    background="white"
)

# Custom button style for the Process button (blue)
style.configure(
    "Blue.TButton",
    background="#9B0A0A",
    foreground="white",
    font=("Inter", 13),
    borderwidth=0,
    relief="flat",
    anchor="center"
)
style.map(
    "Blue.TButton",
    background=[("active", "#7F0707"), ("disabled", "#A9A9A9")],
    foreground=[("active", "white"), ("disabled", "white")]
)

# New custom style for the Browse button (white with blue text)
style.configure(
    "White.TButton",
    background="white",
    foreground="#7F0707",
    font=("Inter", 11),
    borderwidth=0,
    relief="flat",
    anchor="center"
)
style.map(
    "White.TButton",
    background=[("active", "white"), ("disabled", "#A9A9A9")],
    foreground=[("active", "#7F0707"), ("disabled", "#7F0707")]
)

# BACKGROUND CANVAS for color panels
canvas = tk.Canvas(window, width=862, height=519, bd=0, highlightthickness=0, relief="ridge")
canvas.place(x=0, y=0)

# -- CHANGE HERE: Wine-red color for the left panel
wine_red = "#7F0707"

# Left panel (wine red)
canvas.create_rectangle(0, 0, 431, 519, fill=wine_red, outline="")
# Right panel (white)
canvas.create_rectangle(431, 0, 862, 519, fill="#FCFCFC", outline="")

# LEFT SIDE (wine-red background)
# 1) Action
action_label = tk.Label(window, text="Action:", bg=wine_red, fg="white", font=("Inter", 13))
action_label.place(x=80, y=40)
action_var = tk.StringVar()
action_combo = ttk.Combobox(window, textvariable=action_var, values=["Transcribe", "Translate", "Gloss"], state="readonly")
action_combo.place(x=80, y=70, width=275, height=30)

# 2) Folder: Browse for directory
folder_label = tk.Label(window, text="Folder:", bg=wine_red, fg="white", font=("Inter", 13))
folder_label.place(x=80, y=110)
folder_var = tk.StringVar()
folder_entry = ttk.Entry(window, textvariable=folder_var)
folder_entry.place(x=80, y=140, width=150, height=30)

def browse_folder():
    selected_dir = filedialog.askdirectory()
    if selected_dir:
        folder_var.set(selected_dir)

browse_button = ttk.Button(window, text="Browse...", style="White.TButton", command=browse_folder)
browse_button.place(x=235, y=140, width=120, height=30)

# 3) Instruction
instruction_label = tk.Label(window, text="Instruction:", bg=wine_red, fg="white", font=("Inter", 13))
instruction_label.place(x=80, y=180)
instruction_var = tk.StringVar()
instruction_combo = ttk.Combobox(window, textvariable=instruction_var, values=["Automatic", "Corrected", "Sentences"], state="readonly")
instruction_combo.place(x=80, y=210, width=275, height=30)

# 4) Language
language_label = tk.Label(window, text="Language:", bg=wine_red, fg="white", font=("Inter", 13))
language_label.place(x=80, y=250)
language_var = tk.StringVar()
language_entry = ttk.Entry(window, textvariable=language_var)
language_entry.place(x=80, y=280, width=275, height=30)

# 5) Verbose
verbose_label = tk.Label(window, text="Verbose output:", bg=wine_red, fg="white", font=("Inter", 13))
verbose_label.place(x=80, y=330)
verbose_var = tk.BooleanVar(value=False)
verbose_radiobutton = tk.Radiobutton(window, variable=verbose_var, value=True, bg=wine_red)
verbose_radiobutton.place(x=220, y=332)

# Create a status label on the right panel for output messages
status_label = tk.Label(window, text="", bg="#FCFCFC", fg="black", font=("Inter", 12))
status_label.place(x=450, y=470)

# RIGHT SIDE (white background)
offset_x = 431
try:
    pil_image = Image.open("images/zas_logo.jpg")  # Replace with your image file
    box_x1, box_y1 = 162 + offset_x, 111
    box_x2, box_y2 = 269 + offset_x, 218
    box_width  = box_x2 - box_x1
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

    # Add the text under the image
    text_x = image_x + new_width / 2
    text_y = image_y + new_height + 20  # 20 pixels below the image
    canvas.create_text(text_x, text_y, text="LeibnizDream", fill="black", font=("Inter", 14))
except Exception as e:
    print("Could not load image:", e)

# The Process button now calls start_processing
process_button = ttk.Button(window, text="Process", style="Blue.TButton", command=start_processing)
process_button.place(x=119 + offset_x, y=315, width=189, height=55)

window.mainloop()
