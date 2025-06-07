class JapaneseStrategy(TransliterationStrategy):
    def __init__(self):
        # Load heavy models once
        self.nlp = spacy.load('ja_core_news_trf')
        self.kks = pykakasi.kakasi()

    def transliterate(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        romaji = []
        for word in doc:
            if word.text.isascii():
                romaji.append(word.text)
            elif word.text in ("、", "。"):
                romaji.append({"、": ",", "。": "."}[word.text])
            else:
                kana = word.morph.to_dict().get('Reading', word.text)
                conv = self.kks.convert(kana)
                hepburn = " ".join(item['hepburn'] for item in conv)
                romaji.append(hepburn)
        return " ".join(romaji)