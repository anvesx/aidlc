---
name: asking-questions
description: How AIDLC asks a person questions - find the real gaps, ask only what can't be looked up, give options and a suggested default, and ask everything in one message. Use in the Clarify and Plan steps, or whenever AIDLC work needs a person's answer.
---

# Asking questions

A person's attention is the most expensive thing in AIDLC. Every question costs some of it, so each one has to earn its place.

## Find the real gaps

For each requirement or choice, check:

- **Who** does it, and **what triggers** it?
- **What do they see** after? What changes?
- **What happens when it goes wrong** (bad input, nothing found, an outside system down)?
- **What are the limits** (sizes, counts, times, who is allowed)?
- **Does it contradict** something else in the input, a recorded decision, or the existing code?

A missing answer is a gap. A gap you fill yourself without asking is a guess, and guesses are how the wrong thing gets built.

## Before asking, try to answer it yourself

Don't ask what you can look up: the code, `aidlc/project.md`, `aidlc/decisions/`, `aidlc/standards/`, the ticket, the linked documents, official docs. Ask only what needs the person's knowledge or decision.

| Ask the person | Look it up yourself |
|---|---|
| What they want, and why | How the existing code works |
| Which option to pick when it's a real trade-off | What a library or API supports |
| What is in or out of scope | What was decided before (decisions/) |
| Who is affected, and what matters to them | The project's conventions (standards/) |

Clarify asks about **the need**, not technical choices. Plan asks the technical choices.

## How to ask

1. **All questions in one message.** Never drip them one at a time. In a driver session there is no person to talk to: "one message" means writing every question into the file's "Questions and answers" table at once, then waiting (rules: When a stage needs a person). The person sees them in their own session through `/aidlc:start`.
2. **Number them**, so the person can answer "1: yes, 2: B".
3. **Each question says what it affects:** "This decides whether R3 needs a login."
4. **Give options and a suggested default** where you can: "A) ... B) ... I'd suggest A, because ..."
5. **Plain words.** No jargon the person didn't use first.
6. **Separate blocking from non-blocking.** Non-blocking questions can be answered later; the work carries on with the default, written down as an assumption.

## After the answers

- Write each question and its answer into the step's file. A later session must never ask it again.
- If an answer creates a new gap, ask again, still in one message.
- If someone other than the owner answers, confirm with the owner before using it.
