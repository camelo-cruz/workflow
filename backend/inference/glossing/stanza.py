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

    def gloss(self, text: str, keep_punct: bool = True, debug: bool = False) -> str:
        """
        Build a Leipzig-style gloss from a Stanza pipeline.
        - Handles multi-line input
        - Uses SpaceAfter=No to preserve whitespace
        - Safe hyphen-join (no '--')
        """
        lines = text.splitlines()
        out_lines = []

        for line in lines:
            if not line.strip():
                out_lines.append("")  # preserve blank lines
                continue

            doc = self.nlp(line)           # Stanza document
            parts = []

            for sent in doc.sentences:
                for w in sent.words:       # w: stanza.models.common.doc.Word
                    # passthrough for punctuation/brackets/numbers
                    if keep_punct and (
                        w.upos == "PUNCT" or
                        re.search(r"[\(\)\[\]]", w.text or "") or
                        (w.text or "").isdigit()
                    ):
                        piece = w.text or ""
                    else:
                        # lemma fallback + normalization
                        lemma = (w.lemma or w.text or "").lower().strip()
                        lemma = lemma.replace(" ", "-")   # multiword lemma -> hyphens

                        # parse UD feats string like "Case=Nom|Number=Sing"
                        feats_dict = self.parse_stanza_feats(w.feats) if getattr(w, "feats", None) else {}
                        leipzig = self.UD2LEIPZIG(feats_dict) or ""

                        if debug:
                            print(f"TOK={w.text!r} LEMMA={lemma!r} FEATS={w.feats} → {leipzig!r}")

                        # safe join (no trailing hyphens)
                        piece = "-".join(p for p in (lemma, leipzig) if p)

                    # preserve original spacing using SpaceAfter
                    misc = getattr(w, "misc", None) or ""
                    space = "" if "SpaceAfter=No" in misc else " "
                    parts.append(piece + space)

            out_lines.append("".join(parts).rstrip())

        return "\n".join(out_lines)