## Project status

- 2026/2/17: Initialized README.md files, folder structure, and general workflow created
    - Used https://github.com/EveryInc/compound-engineering-plugin to create PRs #1 (SNAP test data) and #2 (DSL improvement)
- 2026/2/23: Added SNAP eligibility example and demo; improved custom DSL

## TODOs

- Create Claude skills, agents, commands
    - Borrow from [policyengine-claude](https://github.com/PolicyEngine/policyengine-claude/blob/main/agents/country-models/rules-engineer.md)
        - Be aware: it has PolicyEngine/OpenFisca heuristics
        - Compare with [doc-to-logic rule extraction](https://github.com/navapbc/lockpick-doc-to-logic/blob/591db7dab64e763b6952f614afa2c6b24b7aba9c/app/src/agents/prompts/entity_extraction.py#L2-L12)
    - Also RulesFoundation's [AutoRAC](https://github.com/RulesFoundation/autorac/blob/main/src/autorac/prompts/encoder.py) and maybe [reviewers.py](https://github.com/RulesFoundation/autorac/blob/main/src/autorac/prompts/reviewers.py)
    - [AI-powered Rules-as-Code: Experiment 3](https://digitalgovernmenthub.org/publications/ai-powered-rules-as-code-experiments-with-public-benefits-policy/#experiment-three) shows effectiveness of rule templates and RAG, along with challenges for state-specific policies ("policies in different states are inconsistently written. This variation means that translating certain highly variable policies directly to code may not be as promising a path for complicated policies as generating rules.").
- Improve DSL based on
    - [RAC spec](https://github.com/RulesFoundation/rac/blob/main/docs/RAC_SPEC.md)
- Extract to and generate from workflows
    - [Strata's business process workflow DSL](https://nava.slack.com/archives/C08V2HDPX97/p1771374909235309?thread_ts=1771348732.320939&cid=C08V2HDPX97)

For demos:
- Get XML versions of input docs
    - [Atlas mentions](https://github.com/RulesFoundation/atlas?tab=readme-ov-file#features) using [USLM XML](https://github.com/usgpo/uslm)
    - Google: "Many states now publish their codes (e.g., California Code, Texas Statutes) in XML or structured formats"
- Use David's answer key as first example
    - Create output ruleset to work with simple rules engine
        - [David's AK ruleset](https://nava.slack.com/archives/C08V2HDPX97/p1771426906119179?thread_ts=1770933744.702619&cid=C08V2HDPX97)
    - Create output UI
- Use [Meghana's test data](https://nava.slack.com/archives/C08V2HDPX97/p1771372280082369?thread_ts=1770838392.617209&cid=C08V2HDPX97)
    - Create ground truth rules as the "answer key" for what we expect a tool to extract from the source text snippets
- Target output code to use Strata's chosen rule engine and UI design system

To enable use by others:
- Package Xlator as a Claude plugin to be applied on user's codebase
    - For demo, use plugin against a demo codebase
- Add additional Claude code plugins? Be cautious of conflicts with compound-engineering-plugin
    - Write clearly and concisely
    - Writing skills (from superpower)
    - Productivity
    - Product Management
