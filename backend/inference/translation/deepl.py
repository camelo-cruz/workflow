from inference.translation.abstract import TranslationStrategy
import os
import sys
import deepl

class DeeplStrategy(TranslationStrategy):
    def load_model(self):
            """
            Attempt to create a DeepL client. If the API key is missing
            or DeepL is unreachable, leave them as None.
            """
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            secrets_path = os.path.join(base_path, "materials", "secrets.env")
            from dotenv import load_dotenv
            load_dotenv(secrets_path, override=True)
            api_key = os.getenv("DEEPL_API_KEY")
            if not api_key:
                raise RuntimeError("DeepL API_KEY missing or invalid")

            self._deepl_client = deepl.DeepLClient(api_key)
            # Normalize “PT → PT-BR” for DeepL
            code = self.language_code.upper()
            if code.lower() == "pt":
                code = "PT-BR"
            self._deepl_source_lang = code

    def translate(self, text: str) -> str | None:
            """
            If the DeepL client was successfully created, call it.
            Otherwise return None.
            """
            if not self._deepl_client:
                raise RuntimeError(
                    "DeepL client not initialized. "
                    "Call _init_deepl_client() before translating."
                )

            try:
                # First try explicit source_lang; if that fails, let DeepL auto-detect
                try:
                    result = self._deepl_client.translate_text(
                        text,
                        source_lang=self._deepl_source_lang,
                        target_lang="EN-US"
                    )
                except deepl.DeepLException:
                    result = self._deepl_client.translate_text(text, target_lang="EN-US")

                return result.text
            except Exception:
                return None