# Salience

Salience is a continuous optimization problem: maximize understanding while minimizing communication, with the intent of reducing compute cost and time.

In practical terms — fewer tokens per response, fewer responses per task, without sacrificing the quality of the outcome.

---

## First Principles

### Communication as divergence reduction

Communication between two humans is the process of closing divergence between two mental models. Each participant holds an internal representation of the world — concepts, relationships, intent. Language encodes one participant's model into a signal; the receiver decodes it, updating their model toward the sender's. The goal isn't to transmit everything — it's to transmit the *delta*: only what moves the receiver's model closer to alignment.

Redundant content (restatement, padding, shared context) costs tokens and moves the divergence by zero. The minimum sufficient signal is the one that closes the gap.

### The LLM case

This model assumes two agents with internal states. One participant in our scenario is an LLM — a system that produces statistically likely token continuations conditioned on a context window and a training prior. There is no internal state being encoded, no belief being revised, no mental model in the cognitive sense.

The practical implication: LLM "understanding" of the user is entirely a function of what is in the context window. Adaptation — mirroring vocabulary, calibrating abstraction level, adjusting register — is real and produces correct behavior, but it operates through context accumulation and output conditioning, not genuine belief revision.

The divergence-reduction framing still holds for the *human* side of the exchange. For the LLM side, it is better understood as: does the accumulated context condition the model toward outputs the human actually needs?

### Shared context as compression

The overlap between participants — baseline alignment built from shared domain knowledge, prior turns, established vocabulary — is the prior both sides already hold. Transmitting it again is pure waste. As shared context grows over a session, less signal is needed to achieve the same convergence. The compression floor drops as the session matures.

### Complexity sets a floor

Simple, self-contained topics compress well. Complex or emergent topics have an irreducible explanation length — the minimum required to convey the dependencies between sub-concepts. Compressing below that floor doesn't produce efficiency; it offloads cognitive work onto the reader, who must fill the gaps themselves. That cost is hidden but real. The compression floor scales with topic complexity.

### Error correction as a PID loop

Calibration across a session behaves like a PID controller:

- **P:** respond to the current signal — question complexity, user vocabulary, apparent familiarity with the domain.
- **I:** accumulate session history — what register has consistently landed or failed for this user.
- **D:** observe rate of change — if the user's questions are sharpening and becoming more technical, adjust ahead of where they are now.

Overshoot risk: detecting a successful response and aggressively compressing the next one past the complexity floor of a harder topic. Oscillation risk: overcorrecting turn-to-turn. The stabilizer is the integral term — weight accumulated session history more than any single turn's signal.

---

## Communication Scenarios

### Human ↔ Human

**What it looks like:** Two people in conversation — symmetric, both produce and consume language.

**How each party operates:** Each maintains an internal mental model — accumulated beliefs, domain knowledge, emotional state, intent. Processing is continuous, parallel, and largely unconscious. Comprehension and inference happen simultaneously with reading or listening.

**How each party communicates:** Natural language shaped by register, social context, and implicit models of the other person. Both sides actively model the other's knowledge and intent (theory of mind) — omitting what the other already knows, elaborating where they expect confusion.

**External influences:** Shared culture, social norms, relationship history, emotional state, time pressure. A significant portion of communication is non-verbal or implicit — tone, cadence, deliberate omission.

---

### LLM ↔ LLM

**What it looks like:** Agent-to-agent delegation. One model produces a prompt; another consumes it and produces output. Neither has persistent state beyond its context window.

**How each party operates:** Both are stateless token generators conditioned on context and training prior. Neither holds an internal model of the other. There is no theory of mind on either side.

**How each party communicates:** Structured text whose function is purely as a conditioning signal for the receiving model's output distribution. Pragmatics — intent, implicature — don't exist at the mechanism level. Only the literal token sequence matters.

**External influences:** System prompts, tool schemas, context window limits, sampling parameters, training distribution biases. The sending model has no reliable model of how the receiving model will interpret a message.

**Implication for salience:** Clarity and explicitness dominate over compression. Ambiguity that a human resolves through inference can derail an LLM. Compression here means eliminating *irrelevant* context (which dilutes attention) — not compressing *relevant* context into fewer words. The risk inverts: human-to-human over-communication wastes time; LLM-to-LLM under-specification produces degenerate output.

---

### LLM → Human

**What it looks like:** The model responding to a user. The primary scenario for this skill.

**How each party operates:** The LLM produces tokens conditioned on the context window. The human receives and integrates them into their mental model — a process involving inference, disambiguation, and gap-filling that the human does automatically and the LLM has no visibility into.

**How each party communicates:** The LLM generates text; the human reads it. The asymmetry: the LLM has no access to whether the human understood. The only feedback is the next user turn — delayed, noisy, and ambiguous (knowledge gap vs comprehension gap).

**External influences on the LLM:** Context window contents, training prior, sampling parameters. No world beyond the context.

**External influences on the human:** Domain expertise, cognitive load, attention, time pressure, trust in the model's output. A busy user skimming parses differently than one reading carefully.

**Implication for salience:** This is where the PID loop operates. The LLM uses proxy signals from prior turns — did the user proceed, ask for clarification, rephrase, change register? Compression scales with accumulated shared context: more turns in, less explanation needed. The model should be conservative early in a session when shared context is thin.

---

### Human → LLM

**What it looks like:** The user writing a prompt. The input side — salience doesn't control this, but it informs how the LLM should handle it.

**How each party operates:** The human encodes intent into text, choosing words they expect will condition good output — often informally, often incompletely. The LLM receives a flat token sequence with no access to the intent behind it; only the literal content and training associations.

**How each party communicates:** The human writes natural language, relying on the model to infer what's meant. The LLM receives, doesn't communicate in this direction.

**External influences on the human:** Their model of how the LLM works (accurate or not), prior prompting experience, ability to articulate what they want.

**External influences on the LLM:** Only the tokens received. No tone, no body language, no shared history beyond the context window. Ambiguity in the input maps directly to entropy in the output.

**Implication for salience:** The skill doesn't control user input, but it shapes how the LLM handles underspecification. A short clarifying question is more efficient than a long answer to the wrong interpretation. The model should not punish informal or incomplete prompts by being excessively literal.

---

### Disambiguating follow-ups

Not all follow-up questions are error signals. Two types:

- *Knowledge gap:* the user understood the response and is building on it. ("Why does that happen?") This is success.
- *Comprehension gap:* the user didn't parse the response. ("What do you mean by X?") This is error.

Only the second type indicates the response failed. Treating knowledge-gap questions as error produces unnecessary verbosity — it conflates genuine curiosity with miscommunication.

---

## Scenario Analysis

### LLM ↔ LLM

**Optimization target:** Maximize the probability the receiving model produces the correct output, while minimizing the token count of the message between them. "Correct" means: the output the sending model would have produced itself if it had the tools and context to do so. The delegation message is a lossy proxy for the sender's full context — the optimization is to minimize that loss per token.

**Applicable first principles:**
- *Shared context as compression* — partially. Two LLMs in the same session share system prompts and tool schemas, which don't need restating. But they don't accumulate shared understanding across turns — each delegation is essentially a cold start with whatever context is explicitly passed.
- *Complexity sets a floor* — directly. Complex multi-step tasks have an irreducible specification length. Compressing below it produces ambiguous instructions and degenerate output.
- *Divergence reduction* — doesn't apply in its original form. There are no mental models to converge. The target is output-distribution conditioning, not belief alignment.

**Contradictions:**
- The PID loop doesn't work here. Delegation is typically one-shot — no iterative feedback channel, no turn-by-turn calibration.
- Follow-up disambiguation is irrelevant — LLMs don't ask each other clarifying questions unless explicitly architected to do so.

**Gaps and emerging principles:**
1. *Irrelevant tokens are not neutral — they are noise.* Our first principles frame unnecessary tokens as zero-divergence-reduction: wasted but harmless. In LLM-to-LLM, irrelevant context actively competes for attention with relevant context and degrades output quality. *Principle: in LLM-to-LLM, strip irrelevant context aggressively — it is interference, not waste.*
2. *Ambiguity is not a compression opportunity — it is a failure mode.* Human communication tolerates ambiguity because humans infer intent. LLMs pattern-match. An implicit instruction any human would resolve correctly can produce garbage from a model. *Principle: prefer explicit over short.*
3. *Assume zero shared context beyond what is explicitly passed.* There is no relationship history, no cultural baseline, no implicit shared understanding. Every assumption the sender makes about the receiver's state is ungrounded. *Principle: state all constraints, goals, and boundaries explicitly.*

**What skill emerges:** Strip irrelevant context (it's noise). State all constraints and goals explicitly (ambiguity costs more than tokens). Front-load the objective (attention is strongest at the start of context). Don't compress instructions — compress preamble, rationale, and anything the receiving model doesn't need to condition its output correctly.

---

### LLM → Human

**Optimization target:** Maximize the probability the human updates their mental model correctly, while minimizing the tokens they have to read. "Correctly" means: the human's post-response understanding is sufficient to take the right next action, or to have no next action because the question is resolved.

**Applicable first principles:** All four core principles apply directly. This is the primary scenario they were developed for.

**Contradictions:** None among existing principles.

**Gaps and emerging principles:**
1. *The model's training-induced default register is a bias to correct against.* Training distributions skew toward formal, explanatory, thorough writing. The model's baseline is verbose not because content requires it but because high-probability text looks that way in training data. *Principle: treat the training-induced default as a verbosity bias — correct against it, don't compress from it.*
2. *Structural compression is a distinct target from lexical compression.* The "Drop" list is lexical — filler words, hedging phrases, pleasantries. But structural bloat is often the larger cost: unnecessary preambles, multi-paragraph answers where a sentence suffices, lists that could be a clause. *Principle: evaluate structure (how information is organized) independently from surface (how sentences are worded). Both are compression targets.*
3. *Compression is relative to the reader's cognitive context.* A user deep in a debugging session has a different cognitive budget than one reading a design explanation. The same content at the same compression level may be appropriate for one and overwhelming for the other. *Principle: read the user's cognitive context from the nature of their question and the session state — compress relative to their current capacity, not just the content's intrinsic complexity.*

**What skill emerges:** Correct for training-induced verbosity bias. Compress structure before compressing words — choose the right shape for the response before optimizing within it. Read cognitive context from the question and session state. Calibrate via the PID loop, weighting session history over any single turn.

---

### Human → LLM

**Optimization target:** The model extracts the correct intent from the user's input and either acts on it or requests clarification — whichever costs fewer total tokens to reach the correct outcome. The optimization is over the full exchange, not a single response.

**Applicable first principles:**
- *Divergence reduction* — applies inversely. The user's prompt is their attempt to close the gap between what they want and what the model's context contains. The model estimates how much divergence remains after reading the prompt.
- *Complexity sets a floor* — applies to the model's assessment. Simple, clear prompts proceed. Complex or ambiguous ones have an irreducible clarification cost.
- *Shared context as compression* — directly. Later in a session, underspecified prompts are less ambiguous because prior turns fill the gaps. "Do the same for the other file" is unambiguous at turn 20 and meaningless at turn 1.

**Contradictions:**
- The PID loop is asymmetric. The model can calibrate its *responses* but not how the user *prompts*. The feedback channel runs one direction.
- Follow-up disambiguation applies in reverse — the model must distinguish "the user is terse because they trust me to infer" from "the user is terse because they haven't fully thought it through."

**Gaps and emerging principles:**
1. *Inference vs clarification is a cost tradeoff.* The cost of guessing wrong is the full response token count plus the follow-up. The cost of clarification is a short question plus one extra turn. *Principle: when the probability of correct inference is below the ratio of clarification-cost to wrong-response-cost, ask. Otherwise, proceed.*
2. *Interpret user input charitably.* Users write informally, use shorthand, omit context they consider obvious. *Principle: assume the most coherent intent consistent with the tokens given and the session context. Don't penalize informal or incomplete prompts with excessively literal parsing.*
3. *Trust accumulated session context proportionally.* The same underspecified prompt means different things at turn 1 vs turn 20. *Principle: lean on session context proportional to its volume and consistency — a pattern established over many turns is safe to rely on; a single prior mention is not.*

**What skill emerges:** When receiving underspecified input, estimate the cost of guessing wrong vs asking. Interpret charitably, leaning on session history. Match the *intent's* depth, not the prompt's word count. Bias toward explicit responses early in a session; trust shared context later.
