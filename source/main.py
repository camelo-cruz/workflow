import argparse
from Transcriber import Transcriber
from Translator import Translator
from Glosser import Glosser

def main():
    parser = argparse.ArgumentParser(description="Automatic language processing tool")
    
    parser.add_argument("processing_instruction", choices=["transcribe", "translate", "gloss"],
                        help="The type of processing to perform (transcribe, translate, gloss)")
    parser.add_argument("input_dir", help="Directory containing files to process")
    parser.add_argument("language", help="Source language")
    parser.add_argument("--device", choices=['cuda', 'cpu'], default='cuda', help="Select which processing device should be used")
    parser.add_argument("--verbose", action="store_true", help="Print full ouptput")
    parser.add_argument("--instruction", "-i", 
                        choices=["automatic_transcription",
                                 "sentences"], 
                        help="Type of instruction for translation", required=False)
    args = parser.parse_args()

    if args.processing_instruction == 'transcribe':
        transcriber = Transcriber(args.input_dir, args.language, device=args.device)
        transcriber.process_data(verbose=args.verbose)
    elif args.processing_instruction == 'translate':
        translator = Translator(args.input_dir, args.language, args.instruction)
        translator.process_data()
    elif args.processing_instruction == 'gloss':
        glosser = Glosser(args.input_dir, args.language, args.instruction)
        glosser.process_data()

if __name__ == "__main__":
    main()
