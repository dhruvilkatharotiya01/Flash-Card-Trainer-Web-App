import re
import tempfile
import unittest
from pathlib import Path

from flashcards import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "DATA_FILE": str(Path(self.tmp.name) / "cards.json")}
        )
        self.client = self.app.test_client()
        self.store = self.app.extensions["store"]

    def tearDown(self):
        self.tmp.cleanup()

    def token(self) -> str:
        html = self.client.get("/").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post(self, url, **data):
        return self.client.post(url, data={"csrf_token": self.token(), **data}, follow_redirects=True)


class TestPages(AppTestCase):
    def test_home_lists_demo_decks(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("German basics", html)
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})

    def test_post_without_csrf_token_is_rejected(self):
        self.assertEqual(self.client.post("/decks", data={"name": "X"}).status_code, 400)
        self.assertNotIn("X", self.store.decks())

    def test_create_deck_add_edit_delete_card(self):
        self.assertIn(
            "Deck &#39;Physics&#39; created", self.post("/decks", name="Physics").get_data(as_text=True)
        )
        self.post("/decks/Physics/cards", question="Unit of force?", answer="Newton", hint="N")
        card = self.store.deck("Physics")[0]
        self.post(
            f"/decks/Physics/cards/{card['id']}/edit", question="Unit of force?", answer="newton", hint=""
        )
        self.assertEqual(self.store.get_card("Physics", card["id"])["answer"], "newton")
        self.post(f"/decks/Physics/cards/{card['id']}/delete")
        self.assertEqual(self.store.deck("Physics"), [])

    def test_missing_deck_is_404(self):
        self.assertEqual(self.client.get("/decks/nope").status_code, 404)

    def test_html_is_escaped(self):
        self.post("/decks", name="<script>x</script>")
        self.assertNotIn("<script>x</script>", self.client.get("/").get_data(as_text=True))


class TestStudy(AppTestCase):
    def test_correct_answer_schedules_card_later(self):
        self.store.create_deck("D")
        card = self.store.add_card("D", "2+2", "4")
        html = self.post("/decks/D/study", card_id=card["id"], action="answer", answer=" 4 ").get_data(
            as_text=True
        )
        self.assertIn("Correct!", html)
        self.assertIn("All done for now", html)
        self.assertEqual(self.store.get_card("D", card["id"])["box"], 2)

    def test_wrong_answer_keeps_card_due(self):
        self.store.create_deck("D")
        card = self.store.add_card("D", "2+2", "4")
        html = self.post("/decks/D/study", card_id=card["id"], action="answer", answer="5").get_data(
            as_text=True
        )
        self.assertIn("The answer was", html)
        self.assertEqual(self.store.get_card("D", card["id"])["box"], 1)


class TestExam(AppTestCase):
    def test_scores_are_kept_across_requests(self):
        self.store.create_deck("D")
        self.store.add_card("D", "Capital of France", "Paris")
        self.store.add_card("D", "Capital of Italy", "Rome")
        self.store.add_card("D", "Capital of Spain", "Madrid")
        self.post("/decks/D/exam")
        order = [c["answer"] for c in self.store.deck("D")]
        self.post("/decks/D/exam/run", action="submit", answer=order[0])  # right
        self.post("/decks/D/exam/run", action="submit", answer="wrong")  # wrong
        self.post("/decks/D/exam/run", action="reveal")  # skipped
        html = self.post("/decks/D/exam/run", action="next").get_data(as_text=True)
        self.assertIn("33%", html)
        self.assertIn("1 of 3 correct", html)
        self.assertIn("1 wrong", html)
        self.assertIn("1 skipped", html)

    def test_exam_on_empty_deck(self):
        self.store.create_deck("Empty")
        self.assertIn("Add some cards", self.post("/decks/Empty/exam").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
