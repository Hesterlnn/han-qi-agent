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
PASSAGES = (REFERENCES / "key-passages.md").read_text(encoding="utf-8")


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

    def test_relationship_weight_follows_han_qi_corpus_not_modern_fame(self):
        self.assertIn("不能按人物的后世知名度安排权重", PERSONA)
        self.assertIn("吴育（字春卿）", PERSONA)
        self.assertIn("崔公孺（字象之）", PERSONA)
        self.assertIn("陈荐（字彦升）", PERSONA)
        self.assertIn("政策史重要，私人关系权重有限", PERSONA)
        self.assertGreater(PERSONA.index("与吴育（字春卿）"), PERSONA.index("与王尧臣（字伯庸）"))
        self.assertGreater(PERSONA.index("与王安石：政策史重要"), PERSONA.index("与陈荐（字彦升）"))
        self.assertIn("Do not allocate attention by modern fame", RELATIONSHIPS)
        self.assertIn("Wang Anshi 王安石 — policy-important, privately low-weight", RELATIONSHIPS)

    def test_close_relationship_passages_are_available_for_safe_quotation(self):
        for phrase in (
            "爱则昆弟，同则胶漆",
            "十稔违谈燕",
            "相友也，以贤而不以亲",
            "人生不是无交旧，难得相知到白头",
            "与人交久而不变。如彦升者，无几也",
        ):
            self.assertIn(phrase, PASSAGES)


if __name__ == "__main__":
    unittest.main()
