import argparse
from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser
import torch
import PySimpleGUI as sg

def main():

    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # Define the GUI layout
    layout = [
        [sg.Text("Select an operation:")],
        [sg.Radio('Transcribe', "RADIO1", default=True, key='transcribe'),
         sg.Radio('Translate', "RADIO1", key='translate'),
         sg.Radio('Gloss', "RADIO1", key='gloss')],
        [sg.Text('Input Directory:'), sg.InputText(key='input_dir'), sg.FolderBrowse()],
        [sg.Text('Language:'), sg.Combo(['German', 'Turkish', 'Japanese'], 
                                     key='language', default_value='German', readonly=True)],
        [sg.Text('Instruction (optional for translation and glossing):'), sg.Combo(['automatic', 'corrected'], 
                                     key='instruction', default_value='automatic', readonly=True)],
        [sg.Checkbox('Verbose Output', key='verbose')],
        [sg.Button('Process'), sg.Button('Cancel')],
        [sg.Output(size=(80, 20), key='output')]  # Output area for logs or results
    ]

    # Create the window
    window = sg.Window('Processing Tool', layout)

    # Event loop
    while True:
        event, values = window.read()

        # Exit conditions
        if event == sg.WIN_CLOSED or event == 'Cancel':
            break

        # Extract parameters from GUI inputs
        input_dir = values['input_dir']
        language = values['language']
        instruction = values['instruction']
        verbose = values['verbose']

        # Determine the selected operation
        try:
            if event == 'Process':
                if not input_dir:
                    sg.cprint("Error: Please select an input directory.", text_color='red')
                    continue
                if values['transcribe']:
                    sg.cprint("Starting transcription...")
                    transcriber = Transcriber(input_dir, language, device=device)
                    transcriber.process_data(verbose=verbose)
                    sg.cprint("Transcription completed.")
                elif values['translate']:
                    sg.cprint("Starting translation...")
                    translator = Translator(input_dir, language, instruction)
                    translator.process_data()
                    sg.cprint("Translation completed.")
                elif values['gloss']:
                    sg.cprint("Starting glossing...")
                    glosser = Glosser(input_dir, language, instruction)
                    glosser.process_data()
                    sg.cprint("Glossing completed.")
        except Exception as e:
            sg.cprint(f"Error: {e}", text_color='red')

    # Close the window
    window.close()

if __name__ == "__main__":
    main()
