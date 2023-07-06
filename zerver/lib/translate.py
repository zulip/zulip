from translate import Translator


def translate_message(text: str, target_language_code: str) -> str:
    """
    Translates given text string to specified target language using chosen translation api.
    :param text: Input Text String (str)
    :param target_language_code: Target Language Code (e.g., 'es' for Spanish) (str)
    :return translated_text_string - Returns Translated Text String (str)
    """

    # Use The Chosen Translation Api To Translate Message Text From Source To Target Language

    translator = Translator(to_lang=target_language_code)
    print(f"target_language_code",target_language_code)

    # Translate Given Text Using Specified Target Language Code
    translated_text_string = translator.translate(text)
    print(f"translated_text_string",translated_text_string)
    return translated_text_string
