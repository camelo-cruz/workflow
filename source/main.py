import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import torch
from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser

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
    input_dir = input_dir_var.get()
    language = language_var.get()
    instruction = instruction_var.get()
    verbose = verbose_var.get()
    status_label.config(text="Processing...")
    
    if not input_dir:
        messagebox.showerror("Error", "Please select an input directory.")
        return

    if operation_var.get() == "Transcribe":
        threading.Thread(target=process_transcribe, args=(input_dir, language, verbose, status_label), daemon=True).start()
    elif operation_var.get() == "Translate":
        threading.Thread(target=process_translate, args=(input_dir, language, instruction, verbose, status_label), daemon=True).start()
    elif operation_var.get() == "Gloss":
        threading.Thread(target=process_gloss, args=(input_dir, language, instruction, status_label), daemon=True).start()

def select_directory():
    folder_selected = filedialog.askdirectory()
    input_dir_var.set(folder_selected)

def cancel_process():
    global cancel_flag
    cancel_flag = True
    status_label.config(text="Process canceled.")

# Create the main window
root = tk.Tk()
root.title("Processing Tool")
root.geometry("500x300")

tk.Label(root, text="Select an operation:").pack()
operation_var = tk.StringVar(value="Transcribe")
tk.Radiobutton(root, text="Transcribe", variable=operation_var, value="Transcribe").pack()
tk.Radiobutton(root, text="Translate", variable=operation_var, value="Translate").pack()
tk.Radiobutton(root, text="Gloss", variable=operation_var, value="Gloss").pack()

# Input Directory
input_dir_var = tk.StringVar()
tk.Label(root, text="Input Directory:").pack()
input_frame = tk.Frame(root)
input_frame.pack()
tk.Entry(input_frame, textvariable=input_dir_var, width=40).pack(side=tk.LEFT)
tk.Button(input_frame, text="Browse", command=select_directory).pack(side=tk.LEFT)

# Language
language_var = tk.StringVar()
tk.Label(root, text="Language:").pack()
tk.Entry(root, textvariable=language_var).pack()

# Instruction
instruction_var = tk.StringVar(value="automatic")
tk.Label(root, text="Instruction (optional for translation and glossing):").pack()
ttk.Combobox(root, textvariable=instruction_var, values=["automatic", "corrected", "sentences"], state="readonly").pack()

# Verbose Output Checkbox
verbose_var = tk.BooleanVar()
tk.Checkbutton(root, text="Verbose Output", variable=verbose_var).pack()

# Buttons
button_frame = tk.Frame(root)
button_frame.pack()
tk.Button(button_frame, text="Process", command=start_processing).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Cancel", command=cancel_process).pack(side=tk.LEFT, padx=5)

# Status Label
status_label = tk.Label(root, text="", fg="blue")
status_label.pack()

# Run the GUI
root.mainloop()
