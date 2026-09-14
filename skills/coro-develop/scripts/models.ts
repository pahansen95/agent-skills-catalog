/** Model capability baseline, verified 2026-09-13.
 * https://platform.claude.com/docs/en/models/overview
 * https://platform.claude.com/docs/en/build-with-claude/effort
 * Runtime-reported limits take precedence. `cost` is a local warning threshold
 * in USD, not API pricing. Unlisted IDs pass through with an unknown-model warning.
 */
export const specs = [
  {
    id: "claude-fable-5-1",
    aliases: ["fable", "best"],
    context: 1000000,
    extended: 1000000,
    maxOutput: 128000,
    efforts: ["low", "medium", "high", "xhigh", "max"],
    defaultEffort: "high",
    cost: 100,
  },
  {
    id: "claude-opus-5",
    aliases: ["opus"],
    context: 1000000,
    extended: 1000000,
    maxOutput: 128000,
    efforts: ["low", "medium", "high", "xhigh", "max"],
    defaultEffort: "high",
    cost: 50,
  },
  {
    id: "claude-sonnet-5",
    aliases: ["sonnet"],
    context: 1000000,
    extended: 1000000,
    maxOutput: 128000,
    efforts: ["low", "medium", "high", "xhigh", "max"],
    defaultEffort: "high",
    cost: 25,
  },
  {
    id: "claude-haiku-4-5",
    aliases: ["haiku"],
    context: 200000,
    extended: null,
    maxOutput: 64000,
    efforts: [],
    defaultEffort: null,
    cost: 10,
  },
] as const;
export type Spec = typeof specs[number];
