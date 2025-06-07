from pypinyin import lazy_pinyin, Style

class ChineseStrategy(TransliterationStrategy):
    def __init__(self):
        # Choose pinyin style: TONE3 (numbers) or TONE (tone marks)
        self.style = Style.TONE3

    def transliterate(self, sentence: str) -> str:
        # Use lazy_pinyin for simple local transliteration
        # It handles non-Chinese characters by returning them unchanged
        pinyin_list = lazy_pinyin(
            sentence,
            style=self.style,
            errors='default',
            strict=False
        )
        return ' '.join(pinyin_list)