import threading
import PySimpleGUI as sg
import torch
from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser

cancel_flag = False

def process_transcribe(input_dir, language, verbose, window):
    try:
        print("Starting transcription...")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        transcriber = Transcriber(input_dir, language, device=device)
        transcriber.process_data(verbose=verbose)
        print("Transcription completed.")
    except Exception as e:
        print(f"Error: {e}")

def process_translate(input_dir, language, verbose, instruction, window):
    try:
        print("Starting translation...")
        translator = Translator(input_dir, language, instruction)
        translator.process_data()
        print("Translation completed.")
    except Exception as e:
        print(f"Error: {e}")

def process_gloss(input_dir, language, instruction, window):
    try:
        print("Starting glossing...")
        glosser = Glosser(input_dir, language, instruction)
        glosser.process_data()
        print("Glossing completed.")
    except Exception as e:
        print(f"Error: {e}")

def main():

    global cancel_flag

    print("Main function called")

    layout = [
        [sg.Text("Select an operation:")],
        [sg.Radio('Transcribe', "RADIO1", default=True, key='transcribe'),
         sg.Radio('Translate', "RADIO1", key='translate'),
         sg.Radio('Gloss', "RADIO1", key='gloss')],
        [sg.Text('Input Directory:'), sg.InputText(key='input_dir'), sg.FolderBrowse()],
        [sg.Text('Language:'), sg.Combo(['German', 'Russian', 'Ukranian', 'Portuguese', 'Turkish', 'Japanese'], 
                                         key='language', default_value='German', readonly=True)],
        [sg.Text('Instruction (optional for translation and glossing):'), 
            sg.Combo(['automatic', 'corrected', 'sentences'], key='instruction', default_value='automatic', readonly=True, visible=True)],
        [sg.Checkbox('Verbose Output', key='verbose')],
        [sg.Button('Process'), sg.Button('Cancel')],
    ]

    # Create the window
    window = sg.Window('Processing Tool', layout)

    # Event loop
    while True:
        event, values = window.read()

        # Exit conditions
        if event == sg.WIN_CLOSED:
            break
        
        if event == 'Cancel':
            cancel_flag = True
            print("Cancel button pressed. The current process will stop shortly.")
            continue

        # Extract parameters from GUI inputs
        input_dir = values['input_dir']
        language = values['language']
        instruction = values['instruction']
        verbose = values['verbose']

        # Start the processing when the "Process" button is clicked
        if event == 'Process':
            if not input_dir:
                print("Error: Please select an input directory.", text_color='red')
                continue

            if values['transcribe']:
                # Run the transcription process in a new thread
                threading.Thread(target=process_transcribe, args=(input_dir, language, verbose, window), daemon=True).start()
            elif values['translate']:
                # Run the translation process in a new thread
                threading.Thread(target=process_translate, args=(input_dir, language, instruction, window), daemon=True).start()
            elif values['gloss']:
                # Run the glossing process in a new thread
                threading.Thread(target=process_gloss, args=(input_dir, language, instruction, window), daemon=True).start()

    # Close the window
    window.close()

if __name__ == "__main__":
    main()
