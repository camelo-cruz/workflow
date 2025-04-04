import threading
import torch
import os
from functions import get_materials_path
from Transcriber import Transcriber
from Translator import Translator
from Transliterator import Transliterator
from SentenceSelector import SentenceSelector
import requests
from Glosser import Glosser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

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

def start_processing():
    input_dir = folder_var.get()
    language = language_var.get()
    # Depending on the action, use the instruction or study name from the same variable
    instruction_or_study = instruction_var.get()
    verbose = verbose_var.get()
    status_label.config(text="Processing...")
    print("Processing...")

    if not input_dir:
        messagebox.showerror("Error", "Please select an input directory.")
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
    global folder_var, language_var, instruction_var, verbose_var, action_var, status_label
    
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

    # Custom style for the Browse button (white with blue text)
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

    # Left panel: Wine-red color
    wine_red = "#7F0707"
    canvas.create_rectangle(0, 0, 431, 519, fill=wine_red, outline="")
    # Right panel: White
    canvas.create_rectangle(431, 0, 862, 519, fill="#FCFCFC", outline="")

    # LEFT SIDE (wine-red background)
    # 1) Action
    action_label = tk.Label(window, text="Action:", bg=wine_red, fg="white", font=("Inter", 13))
    action_label.place(x=80, y=40)
    action_var = tk.StringVar()
    action_combo = ttk.Combobox(window, textvariable=action_var, 
                                values=["Transcribe", "Translate", "Gloss"], #transliterate", "Select sentences"],
                                state="readonly")
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

    # 3) Instruction / Study Name (Dynamically changes based on Action)
    instruction_label = tk.Label(window, text="For Translation, Gloss, Transliteration:", bg=wine_red, fg="white", font=("Inter", 13))
    instruction_label.place(x=80, y=180)
    instruction_var = tk.StringVar()
    instruction_combo = ttk.Combobox(window, textvariable=instruction_var, values=["automatic", "corrected", "sentences"], state="readonly")
    instruction_combo.place(x=80, y=210, width=275, height=30)

    def update_instruction_box(event):
        selected_action = action_var.get()
        if selected_action == "Select sentences":
            # For sentence selection, change label to "Study:" and allow free text
            instruction_label.config(text="Study:")
            instruction_combo.config(values=[], state="normal")
            instruction_combo.set("")
        elif selected_action in ["Translate", "Gloss", "Transliterate"]:
            # For these actions, use instruction values
            instruction_label.config(text="Instruction:")
            instruction_combo.config(values=["automatic", "corrected", "sentences"], state="readonly")
            instruction_combo.set("automatic")
        else:
            # For Transcribe (or if nothing is selected), disable the instruction box
            instruction_label.config(text="Instruction:")
            instruction_combo.set("")
            instruction_combo.config(state="disabled")
    
    action_combo.bind("<<ComboboxSelected>>", update_instruction_box)
    
    # Set default state for instruction box initially (disabled)
    instruction_combo.config(state="disabled")

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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, 'materials', 'zas_logo.jpg')

        pil_image = Image.open(get_materials_path(image_path))
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

    # The Process button calls start_processing
    process_button = ttk.Button(window, text="Process", style="Blue.TButton", command=start_processing)
    process_button.place(x=119 + offset_x, y=315, width=189, height=55)

    window.mainloop()

if __name__ == "__main__":
    main()
