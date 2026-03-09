import json
import unittest
from pathlib import Path


class TestOrionRoutingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.repo = repo
        cls.routing_text = (repo / "src" / "core" / "shared" / "ROUTING.md").read_text(
            encoding="utf-8"
        )
        cls.orion_text = (repo / "src" / "agents" / "ORION.md").read_text(encoding="utf-8")
        cls.routes = json.loads(
            (repo / "src" / "core" / "shared" / "orion_routing_contract.json").read_text(
                encoding="utf-8"
            )
        )["routes"]

    def test_routing_contract_shape(self):
        ids = set()
        for route in self.routes:
            self.assertIn("id", route)
            self.assertIn("owner", route)
            self.assertIn("file_expectations", route)
            self.assertIn("trigger_phrase", route)
            self.assertNotIn(route["id"], ids)
            ids.add(route["id"])

    def test_routing_contract_phrases_exist_in_required_files(self):
        for route in self.routes:
            with self.subTest(route=route["id"]):
                for expectation in route["file_expectations"]:
                    text = (self.repo / expectation["path"]).read_text(encoding="utf-8")
                    self.assertIn(expectation["phrase"], text)

    def test_routing_cheatsheet_trigger_phrases_exist(self):
        for route in self.routes:
            with self.subTest(route=route["id"]):
                self.assertIn(route["trigger_phrase"], self.routing_text)

    def test_mixed_intent_gate_is_exact(self):
        mixed = next(route for route in self.routes if route["id"] == "mixed_intent_gate")
        phrases = [item["phrase"] for item in mixed["file_expectations"]]
        self.assertEqual(
            phrases[0],
            "Do you want to explore or execute right now?",
        )
        self.assertTrue(all(phrase == "Do you want to explore or execute right now?" for phrase in phrases))
        self.assertIn(phrases[0], self.orion_text)
        self.assertIn(phrases[0], self.routing_text)


if __name__ == "__main__":
    unittest.main()
