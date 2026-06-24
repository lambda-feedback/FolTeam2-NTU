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

# Human-readable names for the accents, used in feedback.
_ACCENT_NAMES = {
    "en_US": "General American (en_US)",
    "en_UK": "Received Pronunciation (en_UK)",
}

# Decoration that carries no phonemic content for the comparison.
_STRIP_CHARS = ("/", "[", "]", "ˈ", "'", "ˌ", ".", " ", "\t", "\n", "\r")

# Symbols that only appear in IPA, used to auto-detect the question direction
# when params["direction"] is not set.
_IPA_MARKERS = set("ˈˌːəɪʊɛɔæɑɒʌɜɝɚɹɫŋʃʒθðˠʔɡɲʎɥʁɣχ̃")


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


@lru_cache(maxsize=None)
def _reverse_index(accent: str) -> Dict[str, Set[str]]:
    """Build {normalised IPA: {word, ...}} for an accent, for IPA->word lookups.

    Words sharing a normalised transcription are homophones, so this lets the
    reverse direction accept any correctly-spelled homophone.
    """
    index: Dict[str, Set[str]] = {}
    for word, transcriptions in _load_accent(accent).items():
        for raw in transcriptions:
            normalised = _normalise(raw)
            if normalised:
                index.setdefault(normalised, set()).add(word)
    return index


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


def _normalise_word(text: Any) -> str:
    """Normalise a spelled word for comparison (case- and whitespace-insensitive)."""
    return str(text).strip().lower()


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


def _looks_like_ipa(value: Any) -> bool:
    """Heuristic: does this configured answer look like an IPA transcription?"""
    text = str(value)
    if "/" in text or "[" in text:
        return True
    return any(ch in _IPA_MARKERS for ch in text)


def _resolve_direction(answer: Any, params: Params) -> str:
    """Decide whether to grade word->IPA or IPA->word.

    Honours params["direction"] ("word_to_ipa" | "ipa_to_word"); otherwise infers
    it from the shape of the configured `answer`.
    """
    direction = params.get("direction")
    if direction in ("word_to_ipa", "ipa_to_word"):
        return direction
    return "ipa_to_word" if _looks_like_ipa(answer) else "word_to_ipa"


def _evaluate_word_to_ipa(response: Any, answer: Any, params: Params, accents: List[str]) -> Result:
    """Grade a student's IPA transcription of a word (the forward direction)."""
    word = params.get("word") or answer
    if not word:
        return Result(
            is_correct=False,
            feedback_items=[("no_word", "No word was configured to transcribe.")],
        )

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
        return Result(is_correct=True, feedback_items=[("correct", why)])

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


def _evaluate_ipa_to_word(response: Any, answer: Any, accents: List[str]) -> Result:
    """Grade a student's spelled word for a given IPA transcription (the reverse).

    The configured `answer` may be the IPA itself (e.g. "/ˈbætɝi/") or the target
    word, whose transcription is then looked up. Any homophone — a word sharing
    that transcription — is accepted.
    """
    answer_key = _normalise_word(answer)
    targets: Set[str] = set()
    display_ipa = None

    # If the answer is a known word, use its transcriptions as the target IPA.
    for accent in accents:
        for raw in _load_accent(accent).get(answer_key, []):
            normalised = _normalise(raw)
            if normalised:
                targets.add(normalised)
                if display_ipa is None:
                    display_ipa = raw

    # Otherwise treat the answer as a literal IPA transcription.
    if not targets:
        literal = _normalise(answer)
        if literal:
            targets.add(literal)
            display_ipa = str(answer)

    if not targets:
        return Result(
            is_correct=False,
            feedback_items=[("no_ipa", "No IPA transcription was configured for this question.")],
        )

    # Collect every word whose transcription matches the target IPA (homophones).
    accepted_words: Set[str] = set()
    for accent in accents:
        index = _reverse_index(accent)
        for target in targets:
            accepted_words |= index.get(target, set())
    accepted_words.add(answer_key)  # ensure the configured word itself is accepted

    display = str(display_ipa).strip("/")
    response_word = _normalise_word(response)

    if not response_word:
        return Result(
            is_correct=False,
            feedback_items=[("empty", f"No word was provided. Which word is transcribed /{display}/?")],
        )

    if response_word in accepted_words:
        return Result(
            is_correct=True,
            feedback_items=[("correct", f"Correct! /{display}/ is the IPA transcription of \"{response_word}\".")],
        )

    return Result(
        is_correct=False,
        feedback_items=[
            ("incorrect", f"That isn't the word transcribed as /{display}/. Sound out each symbol and try again."),
        ],
    )


def evaluation_function(
    response: Any,
    answer: Any,
    params: Params,
) -> Result:
    """
    Evaluate an IPA question in either direction, against the
    open-dict-data/ipa-dict dictionaries (en_US + en_UK by default).

    Direction is taken from params["direction"] ("word_to_ipa" | "ipa_to_word"),
    or inferred from the configured `answer`:

    - word_to_ipa (forward): `answer` is a word (e.g. "battery"); the student
      submits the IPA. Any listed pronunciation in the chosen accents is accepted.
    - ipa_to_word (reverse): `answer` is an IPA transcription (e.g. "/ˈbætɝi/") or
      a word whose transcription is looked up; the student submits the spelled
      word. Any homophone sharing that transcription is accepted.

    Other params: params["word"] overrides the forward target word;
    params["accents"] restricts the accents (default both). Stress marks,
    slashes/brackets, syllable dots and whitespace are ignored when comparing IPA,
    and the broad (r) and narrow (ɹ) rhotic symbols are treated as equivalent.
    """
    accents = _requested_accents(params)

    if _resolve_direction(answer, params) == "ipa_to_word":
        return _evaluate_ipa_to_word(response, answer, accents)
    return _evaluate_word_to_ipa(response, answer, params, accents)
