import argparse
import Transcriber
import Translator
import Glosser
import Transliterator

def main():
    parser = argparse.ArgumentParser(description="Automatic language processing tool")
    
    parser.add_argument("processing_instruction", choices=["transcribe", "translate", "gloss"],
                        help="The type of processing to perform (transcribe, translate, gloss)")
    parser.add_argument("input_dir", help="Directory containing files to process")
    parser.add_argument("language", help="Source language")
    parser.add_argument("--instruction", 
                        choices=["automatic_transcription", 
                                 "corrected_transcription", 
                                 "sentences"], 
                        help="Type of instruction for translation", required=False)
    args = parser.parse_args

    if args.processing_instruction == 'transcribe':
        transcriber = Transcriber(args.input_dir, args.language)
        transcriber.process_data()
    elif args.processing_instruction == 'translate':
        translator = Translator(args.input_dir, args.language, args.instruction)
        translator.process_data()
    elif args.processing_instruction == 'gloss':
        glosser = Glosser(args.input_dir, args.language)
        glosser.process_data()

if __name__ == "__main__":
    main()
