from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser
from functions import load_text_file
import torch
import os
import sys

PySimpleGUI_License = "eyyrJkMSaSW2NjlWbGnsNMloVhHvlpwPZDSuIT6JI4kJRcl0dhmYVXsfbz3GB1lYcOiKI6sPI7knxkpiY022VouxcX2XVJJIRJCLIX6zMbTMczzQNdjUEw2CNuDdcXzJNfCuwjipTDGmlrjkZ0Wd5NzAZPUyR5lnc1GTxqvGe2WF1llYbRn9RLW2ZcXkJ2zwaaWu9auzI1jVoexuLQC5JdOYYvWM1klnRPmflCyAce38QFiqO2iKJXB2b5GAVhqWYkWx5ukdcAmXEbiILJCKJ6OaY2WB1glTTxG2Ffz4dkCaIZ6HIak6N9hlbpW6VbsebQy2I5sHIzk7NYvmbbXMBbhbbHnwkHiyOUiiIsi5LeCDJ7DgdgXlNK0Lbl2P1UlHcvkflnEfIOjzoTi1NzTeEr5MOcDnUbiCLKC3JJEwYaXKRtlzS6XANkzNd8WjVbk5IEjzoLi0MmDAELvoMkDrYNv1MajsAUyzNnSdIosMI7kERNhxd0GNV0F4ejHgBLpvcEmcVLzFIcjWofisMrDsERvTMCDnYqvAMujfAuyqNwijIostIEkCVatPYEWvlisvQBWaRKk2ctmMVozzcNyOIg6gIGmaFkjjYnWN1clCbTG09rjWcjnyV66rQ3GFdZtmYfWelGsILzmON6vUbUS2IOssIbkLlmQSQUW9RMkFc4mYV8zlc7yFId63IDjKca56LJjsUo0kLkjEIv00MOyo4jxRNzy6JF933abc740182429369834dcf97b4e0eaa0dd77e0b050a7e08fbb373dc38cfb4760209bc3979afec5265e63064c62d6f0ab3ca3186995bb54f5f75ce3940a6b5ef5097c14b1954f82177c141bc7d6370c26b9a429ca70f83154926881645012a2f5200124c90a223fd123d523c1770dc44bfc7c34fb50808f5ed6c4420f1401ef5f914b068ea5134188b74d0e544e71b9acded445b5b014eff9547f376b75fda10931e61ae2e86f4964655b3f76a11245f9b436b558326bc3df883345ea3c7b691baec9e228bff780573602a268ba2eeaacf9df0adad4a2c67ef5b100f35f3c7bba4a979503c04d1033fc7f9b66b8160ed58c62e8b58a447a14dcd5862685e652601f06577b065ac090d27b62a0368eff2d972715d72eaff547d250033ca281c5acf5eab52ab19af3bd7375222893f28691231c64e606c4f25ea390f95f085fc1b268566ace4b0585023642190791e8c264838ff878e9f8df1166888da3952ed96323f22f3c3d7aa77837185c7c5d7c46c23b1fe8c59e2d71101f1a18fa8c40b73cafeca962aa446025010d6670e2abd93fa815d3d0fa30e01c2af97e69e8f4d61d9b245364d1fc4f938781d5517a827762381d794df493c02171a27f9e1ece6a24ed5f802ca5dceb32031b31477a9b2e332dacf9045d5bbc129148acbd451d0451621fe53376216110dc0f4a4ba4468b2aee1a9f5995cc51bf02807a64517b865f"

import PySimpleGUI as sg

def main():
    print("Main function called")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # Define the GUI layout
    layout = [
        [sg.Text("Select an operation:")],
        [sg.Radio('Transcribe', "RADIO1", default=True, key='transcribe'),
         sg.Radio('Translate', "RADIO1", key='translate'),
         sg.Radio('Gloss', "RADIO1", key='gloss')],
        [sg.Text('Input Directory:'), sg.InputText(key='input_dir'), sg.FolderBrowse()],
        [sg.Text('Language:'), sg.Combo(['German', 'Russian', 'Ukranian', 'Portuguese', 'Turkish', 'Japanese'], 
                                     key='language', default_value='German', readonly=True)],
        [sg.Text('Instruction (optional for translation and glossing):'), 
            sg.Combo(['automatic', 'corrected'], key='instruction', default_value='automatic', readonly=True, visible=False)],
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

        if values['translate'] or values['gloss']:
            window['instruction'].update(visible=True)
        else:
            window['instruction'].update(visible=False)

        # Extract parameters from GUI inputs
        input_dir = values['input_dir']
        language = values['language']
        instruction = values['instruction']
        verbose = values['verbose']

        # Determine the selected operation
        try:
            if event == 'Process':
                print(f"Runtime whisper path: {os.path.join(sys._MEIPASS, 'whisper/assets')}")
                print(f"Runtime materials path: {os.path.join(sys._MEIPASS, 'materials')}")
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
