from typing import Any
from lf_toolkit.evaluation import Result, Params


# Accepted IPA transcriptions for "battery".
#
# The word is built as:  b  æ  <medial>  (schwa?)  r  i
#   - medial consonant : /t/ (RP citation), /ɾ/ (General American flap), /d/
#   - schwa            : present in the careful 3-syllable form (ˈbæt.ə.ri),
#                        absent in the common reduced 2-syllable form (ˈbæt.ri)
#
# We generate every sensible combination so that a correct answer is accepted
# regardless of accent choice, syllable count, and narrow/broad rhotic symbol.
_MEDIALS = ["t", "ɾ", "d"]
_SCHWAS = ["ə", ""]
_RHOTICS = ["r", "ɹ"]

_ACCEPTED = {
    f"bæ{medial}{schwa}{rhotic}i"
    for medial in _MEDIALS
    for schwa in _SCHWAS
    for rhotic in _RHOTICS
}


def _normalise(text: Any) -> str:
    """Strip the decoration around a transcription so we compare phonemes only.

    Removes delimiters (/.../, [...]), the primary/secondary stress marks,
    syllable separators and whitespace. The result is the bare phoneme string.
    """
    if not isinstance(text, str):
        text = str(text)

    # Characters that carry no phonemic content for this comparison.
    for ch in ("/", "[", "]", "ˈ", "'", "ˌ", ".", " ", "\t", "\n"):
        text = text.replace(ch, "")

    return text.strip()


def evaluation_function(
    response: Any,
    answer: Any,
    params: Params,
) -> Result:
    """
    Evaluate a student's IPA transcription of the word "Battery".

    Accepts the common valid pronunciations:
      - RP citation form        ˈbætəri  / ˈbætri
      - General American flap   ˈbæɾəri  / ˈbæɾri
      - voiced medial variant   ˈbædəri  / ˈbædri

    Stress marks, slashes/brackets, syllable dots and whitespace are ignored,
    and both the broad (r) and narrow (ɹ) rhotic symbols are accepted.
    """

    normalised_response = _normalise(response)

    # Compare against the generated set of valid transcriptions. The supplied
    # `answer` is also accepted (after normalisation) so the question's own key
    # always counts as correct, even if it is a variant we did not enumerate.
    accepted = set(_ACCEPTED)
    accepted.add(_normalise(answer))

    if normalised_response in accepted:
        return Result(is_correct=True)

    if not normalised_response:
        return Result(
            is_correct=False,
            feedback_items=[
                ("empty", "No transcription was provided. Transcribe \"battery\" in IPA, e.g. /ˈbætəri/."),
            ],
        )

    return Result(
        is_correct=False,
        feedback_items=[
            (
                "incorrect",
                "That isn't a recognised IPA transcription of \"battery\". "
                "Expected something like /ˈbætəri/ (RP) or /ˈbæɾəri/ (General American). "
                "Stress marks and slashes are optional.",
            ),
        ],
    )
