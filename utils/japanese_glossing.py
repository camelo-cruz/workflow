import spacy
from sudachipy import tokenizer as japanese_tokenizer
from sudachipy import dictionary as japanese_dictionary

def gloss_with_sudachipy(sentence):
    """
    Perform morphological analysis of a Japanese sentence using SudachiPy
    and return the glossed sentence with detailed morphological information
    (including verb inflection, aspect, mood, etc.).
    
    Parameters
    ----------
    sentence : str
        The input sentence in Japanese.

    Returns
    -------
    glossed_sentence : str
        The glossed sentence with lemma, POS, and detailed morphological information.
    """
    glossed_sentence = ''
    # Load the Sudachi tokenizer
    tokenizer_obj = japanese_dictionary.Dictionary().create()
    mode = japanese_tokenizer.Tokenizer.SplitMode.C  # SplitMode.C provides the most detailed segmentation
    
    # Tokenize the Japanese sentence
    tokens = tokenizer_obj.tokenize(sentence, mode)
    
    for token in tokens:
        surface = token.surface()  # The actual token as it appears in the text
        lemma = token.dictionary_form()  # Lemma or dictionary form
        pos = '.'.join(token.part_of_speech())  # Full part of speech (POS) info
        inflection_type = token.inflection_type() or ''  # Verb/adjective inflection type (e.g., 五段-サ行)
        inflection_form = token.inflection_form() or ''  # Inflection form (e.g., 未然形, 連用形)
        reading = token.reading_form()  # The reading of the word in katakana
        normalized_form = token.normalized_form()  # Normalized form of the token
        
        # Extracting relevant linguistic features
        case = ''  # Case information (e.g., for particles like "が" or "に")
        aspect = ''  # Verb aspect (progressive, perfective, etc.)
        mood = ''  # Verb mood (indicative, imperative, etc.)
        verb_type = ''  # Type of verb (transitive, intransitive, etc.)

        # Map Part-of-Speech Tags to Linguistic Features
        if "動詞" in pos:  # Check if it's a verb
            # You can infer aspect and mood from inflection type/form
            # Example: For "行きます", inflection_type could be 五段-カ行 and form is 連用形
            if inflection_form == "連用形":
                aspect = "progressive"  # Ongoing action (continuous aspect)
            elif inflection_form == "未然形":
                mood = "negative"  # Typically the form used for negation

            # Additional aspects can be inferred based on conjugations
            if "命令形" in inflection_form:
                mood = "imperative"
            if "完了形" in inflection_form:
                aspect = "perfective"

            # Transitivity based on common verb classifications
            if inflection_type.startswith("五段") or inflection_type.startswith("一段"):
                verb_type = "transitive"  # Most 五段 and 一段 verbs are transitive
            else:
                verb_type = "intransitive"
        
        # Extract case from particles or other function words
        if "助詞" in pos:  # Check if it's a particle
            if surface == "が":
                case = "nominative"  # Subject marker
            elif surface == "を":
                case = "accusative"  # Object marker
            elif surface == "に":
                case = "dative"  # Indirect object marker
            elif surface == "で":
                case = "locative"  # Location marker

        # Build the gloss for each word
        glossed_word = f"{translated_lemma}.{arttype}.{definite}.{gender}.{person}.{number}.{case}.{tense}.{mood}"
        glossed_word = f"{surface}.{pos}.{lemma}.{inflection_type}.{inflection_form}.{reading}.{normalized_form}"
        glossed_word += f".{aspect}.{mood}.{case}.{verb_type}"  # Add inferred features
        
        glossed_sentence += glossed_word + ' '
    
    return glossed_sentence.strip()


def gloss_japanese_with_spacy(nlp, sentence):
    try: 
        nlp = spacy.load('ja_core_news_trf')
    except OSError:
        download('ja_core_news_trf')
        nlp = spacy.load('ja_core_news_trf')
        
    glossed_sentence = ''
    doc = nlp(sentence)
    
    # Iterating over each token in the sentence
    for token in doc:
        # Print basic information for the token
        print(f"Token: {token.text}")
        print(f"POS: {token.pos_}")  # Part of speech
        print(f"Tag: {token.tag_}")  # Detailed POS tag
        print(f"Morph: {token.morph}")  # Morphological information (if available)
        
        # Constructing the glossed sentence with token info
        glossed_sentence += f"{token.text}.{token.pos_}.{token.tag_}.{token.morph} "

    return glossed_sentence