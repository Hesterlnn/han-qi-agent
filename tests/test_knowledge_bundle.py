import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
BUNDLE = (ROOT / "assets" / "universal-chat" / "韩琦智能体-通用知识包.md").read_text(
    encoding="utf-8"
)
PERSONA = (REFERENCES / "core-persona-model.md").read_text(encoding="utf-8")
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
SYSTEM_PROMPT = (ROOT / "assets" / "knowledge-base" / "系统提示词.md").read_text(
    encoding="utf-8"
)
RELATIONSHIPS = (REFERENCES / "relationship-cards.md").read_text(encoding="utf-8")
VOICE = (REFERENCES / "voice-and-dialogue-guide.md").read_text(encoding="utf-8")


class KnowledgeBundleTests(unittest.TestCase):
    def test_bundle_contains_current_reference_files(self):
        for name in (
            "core-persona-model.md",
            "relationship-cards.md",
            "voice-and-dialogue-guide.md",
            "bibliography-and-provenance.md",
        ):
            source = (REFERENCES / name).read_text(encoding="utf-8").strip()
            self.assertIn(f"<!-- bundled-from: {name} -->", BUNDLE)
            self.assertIn(source, BUNDLE)

    def test_persona_contains_corpus_based_calibrations(self):
        self.assertIn("不能因此直接称为庆历新政各项措施的共同设计者", PERSONA)
        self.assertIn("关系网络不等于秘密结党", PERSONA)
        self.assertIn("一事一议", PERSONA)
        self.assertIn("不应把每一次游赏都翻译成政治寓言", PERSONA)

    def test_agent_rules_apply_the_revised_model(self):
        self.assertIn("not automatically the designer of every Qingli measure", SKILL)
        self.assertIn("Do not make every leisure scene a disguised lesson in politics", SKILL)
        self.assertIn("不要把韩琦自动称为庆历新政各项措施的共同设计者", SYSTEM_PROMPT)

    def test_relationship_model_is_named_and_time_sensitive(self):
        for name in ("吕夷简", "王尧臣", "尹洙", "苏洵", "强至", "王陶"):
            self.assertIn(name, PERSONA)
            self.assertIn(name, RELATIONSHIPS)
        self.assertIn("locate the relationship in time", RELATIONSHIPS)
        self.assertIn("private warmth, literary exchange, official cooperation", RELATIONSHIPS)

    def test_han_qi_never_self_addresses_by_courtesy_name(self):
        self.assertIn("must **never call himself 稚圭**", VOICE)
        self.assertIn("Never have Han Qi call himself by his courtesy name `稚圭`", SKILL)
        self.assertIn("绝不让他以“稚圭”自称", SYSTEM_PROMPT)
        self.assertIn("before the emperor or in ruler-facing formal speech: `臣`", VOICE)
        self.assertIn("in 能力迁移 or ordinary modern conversation: `我`", VOICE)


if __name__ == "__main__":
    unittest.main()
