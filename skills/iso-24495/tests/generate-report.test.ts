import { describe, expect, test } from "bun:test";
import { join } from "node:path";
import { auditCorpus } from "../scripts/audit-corpus.ts";
import { auditEvidence } from "../scripts/audit-evidence.ts";
import { generateReport } from "../scripts/generate-report.ts";
import { scoreMaturity } from "../scripts/score-maturity.ts";

const FIXTURES = join(import.meta.dir, "fixtures");
const findings = auditCorpus(join(FIXTURES, "corpus"));
const evidence = auditEvidence(join(FIXTURES, "repo-level2"));
const answers = await Bun.file(join(import.meta.dir, "..", "assets", "answers.sample.json")).json();
const maturity = scoreMaturity(answers);
const NOW = "2026-08-11T14:00:00.000Z";

describe("generateReport", () => {
  test("the report contains every required section", () => {
    const { report } = generateReport({ findings, evidence, maturity, state: null, now: NOW });
    for (const heading of ["## Maturity", "## Evidence", "## Corpus findings", "## Limitations"]) {
      expect(report).toContain(heading);
    }
  });

  test("the report declares its provisional basis", () => {
    const { report } = generateReport({ findings, evidence, maturity, state: null, now: NOW });
    expect(report).toContain("ISO/DIS 24495-4");
    expect(report.toLowerCase()).toContain("provisional");
    expect(report.toLowerCase()).not.toContain("certified");
  });

  test("a first run creates state with one timestamped snapshot", () => {
    const { state } = generateReport({ findings, evidence, maturity, state: null, now: NOW });
    expect(state.snapshots).toHaveLength(1);
    expect(state.snapshots[0].timestamp).toBe(NOW);
    expect(state.snapshots[0].totals["legalese"]).toBe(5);
  });

  test("records an intentionally skipped corpus review", () => {
    const emptyFindings = { files: {}, totals: {} };
    const { report } = generateReport({
      findings: emptyFindings,
      evidence,
      maturity,
      state: null,
      now: NOW,
      corpusSkippedReason: "The selected corpus is not English",
    });
    expect(report).toContain("Corpus review skipped: The selected corpus is not English.");
  });

  test("keeps a skipped corpus distinct from a later audited corpus in the trend", () => {
    const emptyFindings = { files: {}, totals: {} };
    const first = generateReport({
      findings: emptyFindings,
      evidence,
      maturity,
      state: null,
      now: NOW,
      corpusSkippedReason: "The selected corpus is not English",
    }).state;
    const { report, state } = generateReport({
      findings,
      evidence,
      maturity,
      state: first,
      now: "2026-11-01T09:00:00.000Z",
    });
    expect(state.snapshots[0].corpusSkippedReason).toBe("The selected corpus is not English");
    expect(state.snapshots[1].corpusSkippedReason).toBeUndefined();
    expect(report).toContain(`| ${NOW} | 0 | Skipped |`);
    expect(report).toContain("| 2026-11-01T09:00:00.000Z | 0 | 12 |");
  });

  test("a later run appends a snapshot without rewriting history", () => {
    const first = generateReport({ findings, evidence, maturity, state: null, now: NOW }).state;
    const LATER = "2026-11-01T09:00:00.000Z";
    const { state, report } = generateReport({ findings, evidence, maturity, state: first, now: LATER });
    expect(state.snapshots).toHaveLength(2);
    expect(state.snapshots[0]).toEqual(first.snapshots[0]);
    expect(state.snapshots[1].timestamp).toBe(LATER);
    expect(report).toContain("## Trend");
  });
});
