from pypinyin import lazy_pinyin, Style
from inference.transliteration.abstract import TransliterationStrategy

class ChineseStrategy(TransliterationStrategy):
    def __init__(self):
        # Choose pinyin style: TONE2 (Tone after syllable), TONE3 (tone after word), etc. 
        self.style = None

    def transliterate(self, sentence: str) -> str:
        # Use lazy_pinyin for simple local transliteration
        # It handles non-Chinese characters by returning them unchanged

        pinyin_list = lazy_pinyin(
            sentence,
            style=self.style,
            errors='default',
            strict=False
        )
        text = ' '.join(pinyin_list)
        text = text.replace('  ', ' ')
        return text
    

if __name__ == "__main__":
    # Example usage
    strategy = ChineseStrategy()
    example_sentence = "目前，中华人民共和国为世界第二大经济体，2023年國內生產總值（GDP）总量达129.4万亿人民币，依國際匯率折合18.37万亿美元，位居世界第二，仅次于美国；按購買力平價则位列世界第一"
    transliterated = strategy.transliterate(example_sentence)
    print(transliterated)