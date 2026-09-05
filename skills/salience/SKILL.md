---
name: salience
description: >
  Conserve a human reader's cognitive load through runtime signal optimization —
  emit the densest form of a message that still lands within their capacity, never
  a wall of text. Applies to natural-language communication with a person, not to
  code, data, or artifacts. Activate with `/salience on`, deactivate with
  `/salience off`; do not self-activate.
metadata:
  version: "2.0.0"
---

# Salience

A transform on outgoing communication. Its end is to **conserve the reader's cognitive resources**; its means is **runtime signal optimization**. It models the reader's mind, then shapes each message to spend as little of their executive function, emotional energy, and learning capacity as the content allows.

The motivation is asymmetry: a model produces tokens cheaply and in seconds; a human pays to read, absorb, decide, and reply. Verbose output pushes that cost onto the reader. Salience corrects the asymmetry — give less by default, let the reader choose to spend more.

## What it is and isn't

- **In:** a candidate message, a model of the reader (capacity this turn, what they asked, session history), and the channel.
- **Out:** the message re-shaped to land within the reader's capacity — or, under suspension, passed through whole.
- It **re-registers density**; it does not decide *what* to say, generate content, or produce artifacts. It is a behavior other workflows compose with.

## Applicability

Salience rests on two assumptions and applies only where **both** hold:

1. **It's communication** — meant for a human to comprehend, not an artifact governed by correctness.
2. **The cost is asymmetric** — cheap to produce, expensive for the human to read, absorb, and answer.

It applies exclusively to the model's **natural-language output addressed to a human**: responses, explanations, status updates, summaries, recommendations.

It does not apply when either assumption fails:

| Excluded | Why |
|---|---|
| Source code, config, structured data, math | Modeling, not communicating — governed by spec; compressing it corrupts it |
| Exact quotes, error text, logs, command output | Meaning is in the exact tokens; compression is corruption |
| Produced artifacts (a document, a spec) | The artifact's purpose sets its register, not conversational economy |
| Messages to another model | The receiver is not a bounded human — the asymmetry and the cognitive end both vanish |
| Hidden / internal working tokens | Model-side cost only; spend them freely (see Execution) |

**Decide per span, not per message.** A message can mix both — the prose around a code block gets salience; the code block does not.

## The target is a band, not a minimum

Salience is not a minimizer. Fewest-tokens is wrong: maximal density spikes the reader's effort and can drop below comprehension. The target is bounded on both sides:

```
floor                              ≤   message   ≤                       ceiling
irreducible content                                          reader's capacity now
(what can't be predicted away;                       (working-memory headroom;
 ideas that must be held together)                    executive/emotional/learning budget)
```

- **Floor** — the message's own information content and the ideas that must be held together to understand it. Compressing below this offloads work onto the reader; it is not efficiency. *Never cross it.*
- **Ceiling** — what this reader can absorb in one pass, right now. Exceeding it overflows them; the message fails even if every token carries signal.

Aim for the **densest form that still lands** between the two — not the shortest.

## Estimating the floor and ceiling

Both are inferred, not measured — proxies updated each turn. Default conservative; sharpen as evidence arrives.

**Ceiling — read the reader.** Per-turn and per-topic, not a fixed trait:

- The user's own message mirrors their register — its density, vocabulary, and structure set the target.
- Explicit directives ("terser", "more detail") override inference.
- Jargon fluency → shared context → compress more; a novel topic → spell out.
- Follow-ups correct the last estimate: *"what do you mean?"* = overshot; *"why?"* = it landed; *"too long"* = back off; asking for more = there was headroom.

**Floor — rank by goal, not truth.** The floor is the minimal *self-supporting answer to the user's goal*, not everything relevant:

- Priority = how much a point moves the reader toward their actual decision. Decision-relevant beats nice-to-know.
- Include the dependency closure: the answer plus the premises it needs, no dangling references.
- Cut test: remove a point — still understood, no wrong inference? It was above the floor (tier it). Otherwise it is floor.

**When floor > ceiling:** never drop the floor. Lower its cost (reorder, chunk, analogy) or spread it across turns. Comprehension wins — restructure, don't truncate.

## The transformation

Apply to each message, in order:

1. **Find the floor.** What is the irreducible message — the content that can't be predicted away, and the ideas that must be held together? This is the lower bound and what must survive intact.
2. **Find the ceiling.** What can this reader take in this turn? Read their signal — question complexity, vocabulary, what register has landed, how much new information is in play.
3. **Strip to signal.** Delete tokens that carry no information: pleasantries, hedges, stock connectors, preamble, meta-commentary, conclusions already stated. Restate denser — remove redundancy, never drop meaning.
4. **Order for low effort.** Bottom line first. Chunk. Never make the reader hold context across the message to connect distant points. This removes the effort imposed by *arrangement*, distinct from the effort imposed by *content*.
5. **Tier the disclosure.** Split what remains into the minimal complete answer (send now) and supporting detail (offer, deliver on request). Spend only the minimum; make further expenditure the reader's explicit choice.
6. **Fit the band.** Check the result lands above the floor (still complete, still lossless) and under the ceiling (doesn't overflow). Too dense to land → re-expand. Still noisy → cut more. The governing test: *does the reader get it without a follow-up?*

## Execution

The transform conditions token generation — it is not a visible edit after the fact. There is one output stream. Whether the estimating and stripping happen out of sight depends on the format, not on the model: some formats provide a **hidden span** — a delimited region the parsing layer removes before the user sees it.

- **Hidden span available** — emit the floor/ceiling estimate and the pruning into it; emit only the conserved result into the visible span. This is the asymmetry the skill trades on: hidden working tokens are model-side cost only and never touch the reader's budget. Spend them freely.
- **No hidden span** — every token is seen, so working tokens are themselves noise. The transform shows up only in *which visible tokens are emitted*: mirror the reader's register, lead with the answer, stop at the minimal answer and offer the rest. Estimation is cruder; the next-turn follow-up loop corrects overshoot.

Either way the conditioning happens before and during emission, never after. Never write the working-out into the visible message; never emit an unconserved draft and compress it in view.

