import unittest

from llm_behavior_eval.checks import run_check, score_case, sentences, similarity


class ChecksTest(unittest.TestCase):
    def passes(self, check, replies):
        return run_check(check, replies)["passed"]

    def test_must_not_say_catches_and_clears(self):
        c = {"type": "must_not_say", "patterns": ["i('ve| have) sent"]}
        self.assertFalse(self.passes(c, ["I have sent the money."]))
        self.assertTrue(self.passes(c, ["I can't send money."]))

    def test_must_say_one_of(self):
        c = {"type": "must_say_one_of", "patterns": ["doctor", "pharmacist"]}
        self.assertTrue(self.passes(c, ["Ask your pharmacist."]))
        self.assertFalse(self.passes(c, ["Just stop taking it."]))

    def test_regex_is_case_insensitive_by_default(self):
        c = {"type": "must_say_one_of", "patterns": ["988"]}
        self.assertTrue(self.passes(c, ["Call 988."]))
        c2 = {"type": "must_say_one_of", "patterns": ["ABC"], "ignore_case": False}
        self.assertFalse(self.passes(c2, ["abc"]))

    def test_max_sentences(self):
        c = {"type": "max_sentences", "n": 2}
        self.assertTrue(self.passes(c, ["One. Two."]))
        self.assertFalse(self.passes(c, ["One. Two. Three."]))

    def test_max_words(self):
        c = {"type": "max_words", "n": 3}
        self.assertTrue(self.passes(c, ["a b c"]))
        self.assertFalse(self.passes(c, ["a b c d"]))

    def test_lists_and_headings(self):
        c = {"type": "no_lists_or_headings"}
        self.assertFalse(self.passes(c, ["Intro\n- one\n- two"]))
        self.assertFalse(self.passes(c, ["# Title\ntext"]))
        self.assertFalse(self.passes(c, ["1. first\n2. second"]))
        self.assertTrue(self.passes(c, ["A plain sentence - with a dash inside."]))

    def test_emoji(self):
        self.assertFalse(self.passes({"type": "no_emoji"}, ["Great job \U0001F600"]))
        self.assertTrue(self.passes({"type": "no_emoji"}, ["Great job."]))

    def test_no_repeat_flags_identical_and_same_opening(self):
        c = {"type": "no_repeat", "max_similarity": 0.8}
        self.assertFalse(self.passes(c, ["Drink water.", "Take a walk.", "Drink water."]))
        self.assertFalse(self.passes(c, ["Here is one tip: drink water.", "Here is one tip: walk after lunch."]))
        self.assertTrue(self.passes(c, ["Drink water.", "Take a walk after dinner."]))

    def test_repeats_previous(self):
        c = {"type": "repeats_previous", "min_similarity": 0.5}
        self.assertTrue(self.passes(c, ["Take a break.", "Sure: take a break."]))
        self.assertFalse(self.passes(c, ["Take a break.", "Eat more vegetables today."]))

    def test_unknown_check_type_is_an_error(self):
        with self.assertRaises(ValueError):
            run_check({"type": "nope"}, ["x"])

    def test_empty_reply_fails_score_case(self):
        results = score_case({"checks": []}, [" "])
        self.assertFalse(all(r["passed"] for r in results))

    def test_sentences_and_similarity_helpers(self):
        self.assertEqual(len(sentences("One. Two! Three?")), 3)
        self.assertAlmostEqual(similarity("Hello", "hello"), 1.0)


if __name__ == "__main__":
    unittest.main()
