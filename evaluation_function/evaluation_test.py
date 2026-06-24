import unittest

from .evaluation import Params, evaluation_function

class TestEvaluationFunction(unittest.TestCase):
    """
    TestCase Class used to test the algorithm.
    ---
    Tests are used here to check that the algorithm written
    is working as it should.

    It's best practise to write these tests first to get a
    kind of 'specification' for how your algorithm should
    work, and you should run these tests before committing
    your code to AWS.

    Read the docs on how to use unittest here:
    https://docs.python.org/3/library/unittest.html

    Use evaluation_function() to check your algorithm works
    as it should.
    """

    def test_correct_transcription_gives_feedback(self):
        # The General American transcription of "battery" should be accepted,
        # and a correct answer now comes with an explanation of why.
        result = evaluation_function("ˈbætɝi", "battery", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), True)
        self.assertTrue(result.get("feedback"))
        self.assertIn("battery", result.get("feedback"))

    def test_uk_variant_accepted(self):
        result = evaluation_function("bætəri", "battery", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), True)

    def test_incorrect_transcription(self):
        result = evaluation_function("banana", "battery", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), False)
        self.assertTrue(result.get("feedback"))

    def test_reverse_ipa_to_word(self):
        # answer is IPA -> direction auto-detected as ipa_to_word.
        result = evaluation_function("battery", "/ˈbætɝi/", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), True)
        self.assertIn("battery", result.get("feedback"))

    def test_reverse_accepts_homophone(self):
        # "read" (past tense) shares /ˈɹɛd/ with "red", so it should be accepted.
        result = evaluation_function("read", "/ˈɹɛd/", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), True)

    def test_reverse_wrong_word(self):
        result = evaluation_function("computer", "/ˈbætɝi/", Params()).to_dict()

        self.assertEqual(result.get("is_correct"), False)
        self.assertTrue(result.get("feedback"))
