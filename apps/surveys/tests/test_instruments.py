"""Tests for survey instrument definitions and scoring logic."""

from django.test import TestCase

from apps.surveys.instruments import registry
from apps.surveys.instruments.afeqt import AFEQT
from apps.surveys.instruments.daily_symptom import DailySymptomCheck
from apps.surveys.instruments.kccq_12 import KCCQ12
from apps.surveys.instruments.phq_2 import PHQ2
from apps.surveys.instruments.promis import PROMISGlobal
from apps.surveys.instruments.saq_7 import SAQ7
from apps.surveys.scoring import ScoringResult


class InstrumentRegistryTest(TestCase):
    def test_all_instruments_registered(self):
        instruments = registry.all()
        self.assertIn("phq_2", instruments)
        self.assertIn("daily_symptom", instruments)
        self.assertIn("kccq_12", instruments)
        self.assertIn("saq_7", instruments)
        self.assertIn("afeqt", instruments)
        self.assertIn("promis_global", instruments)
        self.assertEqual(len(instruments), 6)

    def test_get_instrument(self):
        cls = registry.get("phq_2")
        self.assertIs(cls, PHQ2)

    def test_get_unknown_instrument(self):
        self.assertIsNone(registry.get("nonexistent"))


class PHQ2Test(TestCase):
    def setUp(self):
        self.instrument = PHQ2()

    def test_metadata(self):
        self.assertEqual(self.instrument.code, "phq_2")
        self.assertEqual(self.instrument.category, "mental_health")
        self.assertEqual(self.instrument.estimated_minutes, 2)

    def test_questions(self):
        questions = self.instrument.get_questions()
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["code"], "interest")
        self.assertEqual(questions[1]["code"], "depressed")
        self.assertEqual(questions[0]["question_type"], "likert")

    def test_score_minimal(self):
        result = self.instrument.score({"interest": 0, "depressed": 0})
        self.assertIsInstance(result, ScoringResult)
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.interpretation, "Minimal concerns")
        self.assertFalse(result.escalation_needed)

    def test_score_mild(self):
        result = self.instrument.score({"interest": 1, "depressed": 1})
        self.assertEqual(result.total_score, 2)
        self.assertEqual(result.interpretation, "Mild concerns — monitor closely")
        self.assertFalse(result.escalation_needed)

    def test_score_escalation(self):
        result = self.instrument.score({"interest": 2, "depressed": 2})
        self.assertEqual(result.total_score, 4)
        self.assertTrue(result.escalation_needed)
        self.assertEqual(result.escalation_severity, "urgent")

    def test_score_max(self):
        result = self.instrument.score({"interest": 3, "depressed": 3})
        self.assertEqual(result.total_score, 6)
        self.assertTrue(result.escalation_needed)

    def test_escalation_defaults(self):
        defaults = self.instrument.get_escalation_defaults()
        self.assertIn("total", defaults)
        self.assertEqual(defaults["total"]["threshold"], 3)

    def test_change_alert_config(self):
        config = self.instrument.get_change_alert_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["min_delta"], 2)

    def test_display_config(self):
        config = self.instrument.get_display_config()
        self.assertEqual(config["mode"], "single_page")


class DailySymptomCheckTest(TestCase):
    def setUp(self):
        self.instrument = DailySymptomCheck()

    def test_questions(self):
        questions = self.instrument.get_questions()
        self.assertEqual(len(questions), 5)
        codes = [q["code"] for q in questions]
        self.assertEqual(codes, ["pain", "swelling", "fever", "wound", "mood"])

    def test_score_all_good(self):
        result = self.instrument.score(
            {
                "pain": 0,
                "swelling": 0,
                "fever": 0,
                "wound": 0,
                "mood": 0,
            }
        )
        self.assertEqual(result.total_score, 0)
        self.assertIn("on track", result.interpretation)
        self.assertFalse(result.escalation_needed)

    def test_score_severe_pain_escalation(self):
        result = self.instrument.score(
            {
                "pain": 9,
                "swelling": 0,
                "fever": 0,
                "wound": 0,
                "mood": 0,
            }
        )
        self.assertTrue(result.escalation_needed)
        self.assertIn("severe pain", result.escalation_reason)

    def test_score_fever_escalation(self):
        result = self.instrument.score(
            {
                "pain": 0,
                "swelling": 0,
                "fever": 1,
                "wound": 0,
                "mood": 0,
            }
        )
        self.assertTrue(result.escalation_needed)
        self.assertIn("fever", result.escalation_reason)

    def test_score_wound_escalation(self):
        result = self.instrument.score(
            {
                "pain": 0,
                "swelling": 0,
                "fever": 0,
                "wound": 3,
                "mood": 0,
            }
        )
        self.assertTrue(result.escalation_needed)
        self.assertIn("wound", result.escalation_reason)

    def test_domains(self):
        self.assertEqual(self.instrument.get_domains(), ["physical", "emotional"])


class KCCQ12Test(TestCase):
    def setUp(self):
        self.instrument = KCCQ12()

    def test_questions(self):
        questions = self.instrument.get_questions()
        self.assertEqual(len(questions), 12)

    def test_score_excellent(self):
        # All answers at 5 (best) = 100/100
        answers = {q["code"]: 5 for q in self.instrument.get_questions()}
        result = self.instrument.score(answers)
        self.assertEqual(result.total_score, 100.0)
        self.assertEqual(result.interpretation, "Good health status")
        self.assertFalse(result.escalation_needed)

    def test_score_severe(self):
        # All answers at 1 (worst) = 0/100
        answers = {q["code"]: 1 for q in self.instrument.get_questions()}
        result = self.instrument.score(answers)
        self.assertEqual(result.total_score, 0.0)
        self.assertTrue(result.escalation_needed)

    def test_display_config_grouped(self):
        config = self.instrument.get_display_config()
        self.assertEqual(config["mode"], "grouped")
        self.assertEqual(len(config["groups"]), 5)

    def test_domains(self):
        domains = self.instrument.get_domains()
        self.assertEqual(len(domains), 5)
        self.assertIn("physical_limitation", domains)
        self.assertIn("quality_of_life", domains)


class SAQ7Test(TestCase):
    def setUp(self):
        self.instrument = SAQ7()

    def test_questions(self):
        self.assertEqual(len(self.instrument.get_questions()), 7)

    def test_score_minimal_angina(self):
        answers = {}
        for q in self.instrument.get_questions():
            if q["domain"] == "angina_frequency":
                answers[q["code"]] = 6  # Never
            else:
                answers[q["code"]] = 5  # Not limited / completely satisfied
        result = self.instrument.score(answers)
        self.assertGreater(result.total_score, 75)
        self.assertFalse(result.escalation_needed)


class AFEQTTest(TestCase):
    def setUp(self):
        self.instrument = AFEQT()

    def test_questions(self):
        self.assertEqual(len(self.instrument.get_questions()), 10)

    def test_score_minimal_impact(self):
        answers = {q["code"]: 1 for q in self.instrument.get_questions()}
        result = self.instrument.score(answers)
        self.assertEqual(result.total_score, 100.0)
        self.assertFalse(result.escalation_needed)


class PROMISGlobalTest(TestCase):
    def setUp(self):
        self.instrument = PROMISGlobal()

    def test_questions(self):
        self.assertEqual(len(self.instrument.get_questions()), 10)

    def test_score_excellent_health(self):
        answers = {q["code"]: 5 for q in self.instrument.get_questions()}
        answers["pain"] = 0  # Pain is 0-10 scale, 0 = no pain (best)
        result = self.instrument.score(answers)
        self.assertGreater(result.total_score, 40)
        self.assertFalse(result.escalation_needed)

    def test_domains(self):
        self.assertEqual(self.instrument.get_domains(), ["physical", "mental"])
