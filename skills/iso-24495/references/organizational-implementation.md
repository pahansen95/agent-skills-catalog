# Organisational implementation

Use this reference only when the task is to establish, assess, or improve an organisation's content-development practice: leadership, strategy, implementation planning, resources, culture, assessment, or improvement. It applies to new and established organisations, with or without AI. Ordinary writing, rewriting, and review of one document use the foundation and any applicable legal, science, or design reference instead.

ISO 24495-4 is currently a Draft International Standard. The guidance and optional audit tooling in this skill are local methods informed by public scope and preview; they are not ISO requirements, a conformance assessment, or certification.

## Optional local audit extension

Use the extension only when the user asks for an organisational assessment. Reuse the directory and read authorization already supplied for that assessment; ask only when the scope is missing or needs to change. One repository is evidence about that repository, not the whole organisation.

Set `skill_root` to this installed skill directory, then run the commands from the project being assessed. Outputs and state stay in that project; never write them into the installed skill.

```sh
skill_root=/absolute/path/to/installed/iso-24495
cd /path/to/project-being-assessed
```

1. Run `time bun "$skill_root/scripts/audit-evidence.ts" . --json evidence.json` to locate candidate policy, workflow, check, training, and glossary artefacts. Read the relevant material and use [the evidence map](#evidence-map) before drawing conclusions.
2. For an English-language corpus, optionally run `time bun "$skill_root/scripts/audit-corpus.ts" docs --json findings.json`. Replace `docs` with the agreed corpus path. Its sentence, paragraph, term, and heading checks are local review flags for the Measurement dimension only. They do not measure clarity, prove compliance, or raise a maturity score by themselves.
3. Ask only the questions needed to fill important evidence gaps, then copy [`answers.sample.json`](../assets/answers.sample.json) to `answers.json`, record evidence-backed answers, and run `time bun "$skill_root/scripts/score-maturity.ts" answers.json --json maturity.json`.
4. Run `time bun "$skill_root/scripts/generate-report.ts" findings.json evidence.json maturity.json --state .plain-language-audit-state.json --out gap-report.md`. Keep the append-only state where the organisation can maintain it.

The generated report is a scaffold. Before delivering it, add the assessed scope,
evidence citations and quality observations, any unreadable or excluded paths,
and recommended actions tied to demonstrated gaps. Rank actions by reader impact
and effort, and identify an owner where the evidence supports one. Compare trends
only when the corpus scope and assessment criteria are comparable.

For a non-English corpus or when corpus review is not useful, create a valid empty `findings.json` with `{"files":{},"totals":{}}`, do not mark a corpus baseline as demonstrated, and add `--corpus-skipped "reason"` to the report command. The report then records that the corpus review was skipped.

## Interpreting evidence

The evidence sweep records names and paths only. A result marked not found means the local scan did not find it; it does not prove that the organisation lacks that practice or that the artefact is not elsewhere. Confirm quality, use, ownership, and organisation-wide coverage with the people and records in scope.

The local maturity model covers governance, capability, process, measurement, and culture. Its score is an evidence-supported lower bound. A `false` or unknown answer means the practice was not demonstrated in this audit, not that it is absent. Keep evidence beside each answer, and describe missing evidence separately from a confirmed gap.

## Evidence map

| Category | The sweep can locate | It can support | It cannot prove |
|---|---|---|---|
| `policy` | Plain-language policy and style-guide filenames | A documented policy or available guide | Ownership or that people use it |
| `review-workflow` | Review templates, workflow, process, and checklist files | A review step exists | That the step runs for every document |
| `automated-checks` | Prose-linter configuration and matching CI workflows | Checks exist in a workflow | That checks block release or cover every document type |
| `training` | Files in training or onboarding paths | Training material is available | That training ran or who attended |
| `glossary` | Glossary and terminology filenames | A consistency resource is available | That terms are applied consistently |

## Evidence questions

After reviewing the sweep, select only the questions that close important evidence gaps. Ask no more than five in one audit.

- When did a leader last mention plain language to the wider organisation, and how?
- Who owns plain language, and what time or budget supports that responsibility?
- What training has run recently, for whom, and with what attendance record?
- How have representative readers used or tested important documents, and what happened to their feedback?
- How can a reader report confusing content, and who responds?
- Can an important public document ship without a clarity review or sign-off? What prevents that?

Record a criterion as demonstrated only with a specific artefact, date, named person, or example. An unverified affirmative answer remains not demonstrated for this local score.

## Local maturity criteria

Each dimension progresses only when the criteria below it are demonstrated. These are local assessment criteria, maintained in `scripts/lib/types.ts`, not ISO clauses. Level 0 means no foundation criterion has been demonstrated; Levels 1–4 correspond to the successive columns.

| Dimension | Level 1: foundation | Level 2: active use | Level 3: systematic practice | Level 4: sustained improvement |
|---|---|---|---|---|
| Governance | `policy-documented` — written policy | `owner-accountable` — named owner | `resourced-mandated` — time and budget | `executive-review-cycle` — scheduled leadership review |
| Capability | `style-guide-available` — reachable guide | `training-delivered` — training ran | `competence-maintained` — refreshers and onboarding | `roles-embedded` — duties in roles |
| Process | `review-step-exists` — defined review | `checks-in-workflow` — checks run | `signoff-gates` — priority release gate | `all-document-types-covered` — coverage evidence |
| Measurement | `corpus-baseline-taken` — usable baseline | `regular-sampling` — repeated audits | `user-testing` — reader testing | `metrics-drive-decisions` — evidence changes practice |
| Culture | `leadership-aware` — leaders know | `leadership-champions` — leaders promote | `feedback-loops` — reader feedback acted on | `improvement-cycles` — learning updates practice |

Use the [gap-report template](../assets/gap-report-template.md) when a structured report is useful. The scripts and tests are maintained together; the scripts require Bun.
