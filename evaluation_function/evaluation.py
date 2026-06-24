from typing import Any, Dict, List, Set
from pathlib import Path
from functools import lru_cache

from lf_toolkit.evaluation import Result, Params


# IPA dictionaries vendored from https://github.com/open-dict-data/ipa-dict
# (data/en_US.txt and data/en_UK.txt). Each line is "word<TAB>/ipa/[, /ipa/...]".
_DATA_DIR = Path(__file__).parent / "data"
_ACCENT_FILES = {
    "en_US": _DATA_DIR / "en_US.txt",
    "en_UK": _DATA_DIR / "en_UK.txt",
}

# Accents checked by default; override per question via params["accents"].
_DEFAULT_ACCENTS = ("en_US", "en_UK")

# Decoration that carries no phonemic content for the comparison.
_STRIP_CHARS = ("/", "[", "]", "ˈ", "'", "ˌ", ".", " ", "\t", "\n", "\r")


@lru_cache(maxsize=None)
def _load_accent(accent: str) -> Dict[str, List[str]]:
    """Parse one ipa-dict file into {lowercased word: [raw transcription, ...]}.

    Cached so each dictionary file is read and parsed at most once per process.
    """
    path = _ACCENT_FILES.get(accent)
    mapping: Dict[str, List[str]] = {}
    if path is None or not path.exists():
        return mapping

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            word, _, ipa_field = line.partition("\t")
            if not ipa_field:
                continue
            # A word may have several comma-separated pronunciations.
            transcriptions = [t.strip() for t in ipa_field.split(",") if t.strip()]
            if transcriptions:
                mapping[word.strip().lower()] = transcriptions
    return mapping


def _normalise(text: Any) -> str:
    """Reduce a transcription to bare phonemes for comparison.

    Strips delimiters, stress marks, syllable dots and whitespace, and unifies
    the broad/narrow rhotic symbols (ɹ -> r) so /ˈbætəɹi/ and /ˈbætəri/ match.
    """
    if not isinstance(text, str):
        text = str(text)
    for ch in _STRIP_CHARS:
        text = text.replace(ch, "")
    return text.replace("ɹ", "r").strip()


# Human-readable names for the accents, used in feedback.
_ACCENT_NAMES = {
    "en_US": "General American (en_US)",
    "en_UK": "Received Pronunciation (en_UK)",
}


def _accepted_map(word: str, accents: Set[str]) -> Dict[str, List[tuple]]:
    """Map each normalised transcription of `word` to the (accent, raw) forms it came from.

    Keeping the source lets us tell the student which accent they matched and
    show the canonical spelling in the feedback.
    """
    accepted: Dict[str, List[tuple]] = {}
    for accent in accents:
        for raw in _load_accent(accent).get(word.lower(), []):
            normalised = _normalise(raw)
            if normalised:
                accepted.setdefault(normalised, []).append((accent, raw))
    return accepted


def _requested_accents(params: Params) -> List[str]:
    """Resolve the accents to check, validating against the available files."""
    requested = params.get("accents") or _DEFAULT_ACCENTS
    if isinstance(requested, str):
        requested = [requested]
    return [a for a in requested if a in _ACCENT_FILES] or list(_DEFAULT_ACCENTS)


def evaluation_function(
    response: Any,
    answer: Any,
    params: Params,
) -> Result:
    """
    Evaluate a student's IPA transcription of a word against the
    open-dict-data/ipa-dict dictionaries.

    The word to transcribe is the teacher-configured `answer` (e.g. "battery"),
    or params["word"] if given. Its IPA is looked up across the accepted accents,
    which default to General American (en_US) and Received Pronunciation (en_UK)
    and are overridable via params["accents"]. If the word is not in the
    dictionaries, `answer` is treated as a literal IPA transcription instead, so a
    teacher can supply one directly.

    Stress marks, slashes/brackets, syllable dots and whitespace are ignored when
    comparing, and the broad (r) and narrow (ɹ) rhotic symbols are treated as
    equivalent.
    """

    word = params.get("word") or answer
    if not word:
        return Result(
            is_correct=False,
            feedback_items=[
                ("no_word", "No word was configured to transcribe."),
            ],
        )

    accents = _requested_accents(params)
    accepted = _accepted_map(str(word), set(accents))

    if not accepted:
        # The word is not in the dictionaries: fall back to treating the
        # configured answer as a literal IPA transcription.
        answer_normalised = _normalise(answer)
        if answer_normalised:
            accepted[answer_normalised] = [("answer", str(answer))]

    if not accepted:
        return Result(
            is_correct=False,
            feedback_items=[
                ("not_found", f"No reference IPA transcription is available for \"{word}\"."),
            ],
        )

    normalised_response = _normalise(response)

    if not normalised_response:
        return Result(
            is_correct=False,
            feedback_items=[
                ("empty", f"No transcription was provided. Transcribe \"{word}\" in IPA."),
            ],
        )

    if normalised_response in accepted:
        sources = accepted[normalised_response]
        # Show the canonical dictionary spelling and which accent(s) it matches.
        accent_names = [_ACCENT_NAMES.get(accent, accent) for accent, _ in sources if accent != "answer"]
        canonical = sources[0][1]
        if accent_names:
            joined = " and ".join(dict.fromkeys(accent_names))
            why = (
                f"Correct! /{canonical.strip('/')}/ is the accepted {joined} "
                f"IPA transcription of \"{word}\"."
            )
        else:
            why = f"Correct! That matches the expected IPA transcription of \"{word}\"."
        return Result(
            is_correct=True,
            feedback_items=[("correct", why)],
        )

    return Result(
        is_correct=False,
        feedback_items=[
            (
                "incorrect",
                f"That isn't a recognised IPA transcription of \"{word}\". "
                "Stress marks and slashes are optional.",
            ),
        ],
    )
