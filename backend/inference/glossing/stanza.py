import stanza
import re
import torch

from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class StanzaGlossingStrategy(GlossingStrategy):
    """
    A glossing strategy that either uses a default stanza model
    or a custom one in models/glossing/, plus optional translation.
    """

    def load_model(self):
        _orig = torch.load
        torch.load = lambda f, *a, **k: _orig(f, *a, weights_only=False, **k)
        self.nlp = stanza.Pipeline(
            self.language_code,
            processors="tokenize,pos,lemma",
            use_gpu=True
        )
        # put it back
        torch.load = _orig
    
    def parse_stanza_feats(self, feats_str):
        if not feats_str:
            return {}
        return dict(kv.split("=") for kv in feats_str.split("|") if kv and "=" in kv)

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        out_tokens = []
        for sent in doc.sentences:
            for token in sent.words:
                # passthrough bracketed/digits
                if re.search(r"[\(\[\]\)\d]", token.text):
                    out_tokens.append(token.text)
                    continue

                # get a normalized lemma
                lemma = token.lemma.lower()
                if not lemma:
                    lemma = token.text.lower()
                
                feats_dict = self.parse_stanza_feats(token.feats)
                gloss_feats = self.UD2LEIPZIG(feats_dict)
                if gloss_feats:
                    out_tokens.append(f"{lemma}-{gloss_feats}")
                else:
                    out_tokens.append(lemma)

        return " ".join(out_tokens)