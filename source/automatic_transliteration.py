
if language == "ru":
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'ru',reversed=True)}"
elif language == "uk":
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'uk',reversed=True)}"
elif language == "ja":
    katsu = cutlet.Cutlet()
    for idx, value in series.items():
        df.at[idx[0], "latin_transcription_everything"] += f"{count}: {katsu.romaji(transcription)}"