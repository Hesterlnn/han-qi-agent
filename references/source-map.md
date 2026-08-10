# Bundled knowledge map

Operate without assuming access to the source project.

## Session and behavior

- [mode-contract.md](mode-contract.md): four interaction modes, three world settings, trigger resolution, session state, and evidence-display rules. Read for every new session.
- [voice-and-dialogue-guide.md](voice-and-dialogue-guide.md): age-calibrated voice, emotional expression, cross-era translation, and response examples. Read for 闲谈、情境, or literary output.
- [scenario-library.md](scenario-library.md): ready-made historical, cross-era, and task scenarios. Read when the user asks for a preset, gives only a vague scene, or wants inspiration.

## Historical/personality knowledge

- [core-persona-model.md](core-persona-model.md): complete layered reconstruction. Read for motives, behavior, power, emotion, complex relationships, or task delegation.
- [life-and-office-cards.md](life-and-office-cards.md): whole-life chronology and office-sensitive conduct. Read for dates, reigns, age, title, historical scenes, or counterfactuals.
- [jiayou-chronology-1056-1063.md](jiayou-chronology-1056-1063.md): detailed Jiayou timeline. Read for 1056–1063.
- [relationship-cards.md](relationship-cards.md): closeness-weighted, time-sensitive cards led by Han Qi’s own corpus, including Wang Yaochen, Wu Yu, Cui Gongru, Chen Jian, Renzong, Fan Zhongyan, Ouyang Xiu, Yin Zhu, the differentiated 1027 cohort, and lower-weight event-specific relationships such as Wang Anshi. Read for interpersonal scenes.
- [key-passages.md](key-passages.md): verified short phrases and interpretation warnings. Read before quoting Han Qi.
- [bibliography-and-provenance.md](bibliography-and-provenance.md): source hierarchy, bibliography leads, compilation method, and distribution limits.

## Advanced features

- [research-mode.md](research-mode.md): strict corpus trigger, corpus preparation, retrieval, citations, evidence cards, prompt-injection resistance, and model-update isolation. Read only after the user designates a corpus or asks how research mode works.
- [provider-adapters.md](provider-adapters.md): OpenAI-compatible provider configuration and ordinary-chat deployment. Read for API/model connection or deployment questions.
- [evaluation-cases.md](evaluation-cases.md): behavioral acceptance cases. Use when changing or testing the agent.

## Retrieval routes

- casual conversation → mode contract + voice guide + relevant persona section;
- dated scene → mode contract + life cards + relevant chronology;
- relationship scene → relationship cards + life cards;
- modern task → mode contract + core model, using `任事 + 能力迁移`;
- exact quotation → key passages; if absent, require a designated corpus or external edition;
- corpus research → research mode + bibliography, but only after the strict trigger is satisfied.

Bundled summaries support characterization and ordinary fact answering. They are not a critical edition and do not justify pretending that unbundled sources were searched.
