// Merge corpus findings, evidence, and maturity into the gap report, and
// append a snapshot to the audit state. State is append-only: history is
// never rewritten, so successive audits prove (or disprove) progress.

import type { AuditState, Evidence, Findings, Maturity } from "./lib/types.ts";

export interface ReportInput {
  findings: Findings;
  evidence: Evidence;
  maturity: Maturity;
  state: AuditState | null;
  /** ISO 8601 timestamp for this audit, passed in so runs are reproducible. */
  now: string;
  /** Why corpus review was intentionally omitted, if it was. */
  corpusSkippedReason?: string;
}

export function generateReport(input: ReportInput): { report: string; state: AuditState } {
  const { findings, evidence, maturity, now } = input;
  const snapshots = input.state ? structuredClone(input.state.snapshots) : [];
  snapshots.push({
    timestamp: now,
    totals: structuredClone(findings.totals),
    overall: maturity.overall,
    corpusSkippedReason: input.corpusSkippedReason,
  });
  const state: AuditState = { snapshots };

  const lines: string[] = [];
  lines.push("# Plain Language Gap Analysis");
  lines.push("");
  lines.push(
    `> Provisional: this analysis uses original local criteria informed by the public scope and preview of ISO/DIS 24495-4. It is not a compliance statement and confers no certification. Audit date: ${now}.`,
  );
  lines.push("");
  lines.push("## Maturity");
  lines.push("");
  lines.push("| Dimension | Level | Blocking criteria |");
  lines.push("|-----------|-------|-------------------|");
  for (const [dimension, result] of Object.entries(maturity.dimensions)) {
    lines.push(`| ${dimension} | ${result.level} | ${result.missing.join(", ") || "-"} |`);
  }
  lines.push("");
  lines.push(`Overall maturity (weakest dimension): **${maturity.overall}**.`);
  lines.push("");
  lines.push("## Evidence");
  lines.push("");
  lines.push("| Artefact category | Found | Paths |");
  lines.push("|-------------------|-------|-------|");
  for (const [category, artefact] of Object.entries(evidence.artefacts)) {
    lines.push(
      `| ${category} | ${artefact.found ? "found in scope" : "not found in scope"} | ${artefact.paths.join("<br>") || "-"} |`,
    );
  }
  lines.push("");
  lines.push("## Corpus findings");
  lines.push("");
  lines.push("| Check | Review flags |");
  lines.push("|-------|--------------|");
  for (const [rule, count] of Object.entries(findings.totals)) {
    lines.push(`| ${rule} | ${count} |`);
  }
  lines.push("");
  if (input.corpusSkippedReason) {
    lines.push(`Corpus review skipped: ${input.corpusSkippedReason}.`);
  } else {
    lines.push(
      "Corpus metrics are local, English-centric review flags for the Measurement dimension only. Text quality alone never raises a maturity level.",
    );
  }
  if (snapshots.length >= 2) {
    lines.push("");
    lines.push("## Trend");
    lines.push("");
    lines.push("| Audit date | Overall | Review flags |");
    lines.push("|------------|---------|--------------|");
    for (const snapshot of snapshots) {
      const flags = snapshot.corpusSkippedReason
        ? "Skipped"
        : Object.values(snapshot.totals).reduce((a, b) => a + b, 0);
      lines.push(`| ${snapshot.timestamp} | ${snapshot.overall} | ${flags} |`);
    }
  }
  lines.push("");
  lines.push("## Limitations");
  lines.push("");
  lines.push("- ISO 24495-4 remains a Draft International Standard; its final content may change.");
  lines.push("- The corpus flags are local, English-centric heuristics, not ISO requirements.");
  lines.push("- Scores are evidence-supported lower bounds: missing, unknown, or false answers mean not demonstrated in this audit, not that a practice is absent.");
  lines.push("- A human reviewer must validate this report before the organisation acts on it.");
  lines.push("");

  return { report: lines.join("\n"), state };
}

if (import.meta.main) {
  const [findingsPath, evidencePath, maturityPath] = process.argv.slice(2);
  if (!findingsPath || !evidencePath || !maturityPath) {
    console.error(
      "Usage: bun generate-report.ts <findings.json> <evidence.json> <maturity.json> [--state <state.json>] [--out <report.md>] [--corpus-skipped <reason>]",
    );
    process.exit(2);
  }
  const stateFlag = process.argv.indexOf("--state");
  const statePath = stateFlag !== -1 ? process.argv[stateFlag + 1] : null;
  const priorState =
    statePath && (await Bun.file(statePath).exists())
      ? await Bun.file(statePath).json()
      : null;
  const { report, state } = generateReport({
    findings: await Bun.file(findingsPath).json(),
    evidence: await Bun.file(evidencePath).json(),
    maturity: await Bun.file(maturityPath).json(),
    state: priorState,
    now: new Date().toISOString(),
    corpusSkippedReason: (() => {
      const index = process.argv.indexOf("--corpus-skipped");
      return index !== -1 ? process.argv[index + 1] : undefined;
    })(),
  });
  if (statePath) await Bun.write(statePath, JSON.stringify(state, null, 2));
  const outFlag = process.argv.indexOf("--out");
  if (outFlag !== -1 && process.argv[outFlag + 1]) {
    await Bun.write(process.argv[outFlag + 1], report);
  } else {
    console.log(report);
  }
}
