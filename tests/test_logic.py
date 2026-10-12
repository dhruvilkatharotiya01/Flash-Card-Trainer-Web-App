import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from flashcards.answers import is_correct, normalise
from flashcards.scheduler import MAX_BOX, due_cards, is_due, schedule
from flashcards.storage import NotFound, Store

NOW = datetime(2026, 1, 1, 12, 0, 0)


class TestScheduler(unittest.TestCase):
    def test_correct_moves_up_and_waits_longer(self):
        card = schedule({}, correct=True, now=NOW)
        self.assertEqual(card["box"], 2)
        self.assertFalse(is_due(card, NOW))
        self.assertTrue(is_due(card, NOW + timedelta(days=1)))

    def test_wrong_resets_to_box_one_and_is_due_now(self):
        card = schedule({"box": 4}, correct=False, now=NOW)
        self.assertEqual(card["box"], 1)
        self.assertTrue(is_due(card, NOW))

    def test_box_is_capped(self):
        card = {"box": MAX_BOX}
        self.assertEqual(schedule(card, True, NOW)["box"], MAX_BOX)

    def test_counts_reviews(self):
        card = schedule(schedule({}, True, NOW), False, NOW)
        self.assertEqual((card["reviews"], card["correct"]), (2, 1))

    def test_due_cards_hardest_first(self):
        cards = [{"id": "a", "box": 3}, {"id": "b", "box": 1}, {"id": "c", "due": "2999-01-01T00:00:00"}]
        self.assertEqual([c["id"] for c in due_cards(cards, NOW)], ["b", "a"])


class TestAnswers(unittest.TestCase):
    def test_lenient_matching(self):
        self.assertFalse(is_correct("the Bahnhof", "der Bahnhof"))
        self.assertTrue(is_correct("new delhi", "New Delhi"))
        self.assertTrue(is_correct("Adam.", "Adam"))
        self.assertTrue(is_correct("the k-means", "k-means"))

    def test_empty_answer_is_wrong(self):
        self.assertFalse(is_correct("", ""))
        self.assertEqual(normalise("  "), "")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "cards.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_deck_and_card_lifecycle(self):
        self.store.create_deck("  Physics ")
        card = self.store.add_card("Physics", "E = ?", "mc^2", "Einstein")
        self.assertEqual(self.store.get_card("Physics", card["id"])["hint"], "Einstein")
        self.store.update_card("Physics", card["id"], answer="mc²")
        self.assertEqual(self.store.deck("Physics")[0]["answer"], "mc²")
        self.store.delete_card("Physics", card["id"])
        self.assertEqual(self.store.deck("Physics"), [])
        self.store.delete_deck("Physics")
        self.assertEqual(self.store.decks(), {})

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.store.create_deck("   ")
        self.store.create_deck("A")
        with self.assertRaises(ValueError):
            self.store.create_deck("A")
        with self.assertRaises(ValueError):
            self.store.add_card("A", "question", "  ")
        with self.assertRaises(NotFound):
            self.store.add_card("missing", "q", "a")
        with self.assertRaises(NotFound):
            self.store.delete_card("A", "nope")

    def test_migrates_original_format(self):
        path = Path(self.tmp.name) / "old.json"
        path.write_text('{"bike": [{"question": "wheels?", "answer": "2", "color": "#fff"}]}')
        card = Store(path).deck("bike")[0]
        self.assertTrue(card["id"])
        self.assertEqual(card["hint"], "")

    def test_seed_is_used_once(self):
        seed = Path(__file__).resolve().parents[1] / "data" / "demo_decks.json"
        path = Path(self.tmp.name) / "seeded.json"
        self.assertIn("German basics", Store(path, seed=seed).decks())
        Store(path).delete_deck("German basics")
        self.assertNotIn("German basics", Store(path, seed=seed).decks())


if __name__ == "__main__":
    unittest.main()
