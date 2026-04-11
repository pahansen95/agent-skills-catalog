---
name: iterative-docs
description: Write long documents incrementally with structure-first approach and section-by-section elaboration. Use for implementation plans, specs, guides, or any document over 200 lines.
metadata:
  version: "1.1"
---

# Iterative Document Writing

**Don't one-shot long documents.** Write incrementally with structure-first approach.

## When to Use

- Documents longer than 200 lines
- Implementation plans or technical specs
- Guides or tutorials with multiple sections
- Any document requiring sustained coherence

## The Process

```
STRUCTURE → TRACK → ELABORATE → REVIEW → REPEAT
```

### Phase 1: Structure First

Create document with outline and placeholders:

```markdown
# Document Title

> Brief description of purpose

## Overview
[2-3 paragraphs summarizing the entire document]

## Section 1: [Topic]
*Details to follow...*

## Section 2: [Topic]
*Details to follow...*
```

**Key actions:**
1. Write a meaningful overview (not a placeholder)
2. List all sections with clear titles
3. Use `*Details to follow...*` for pending content
4. Commit structure before proceeding

### Phase 2: Track with TodoWrite

```typescript
TodoWrite([
  { content: "Write Section 1", status: "pending", activeForm: "Writing Section 1" },
  { content: "Write Section 2", status: "pending", activeForm: "Writing Section 2" },
])
```

### Phase 3: Section-by-Section

For each section:
1. Mark `in_progress`
2. Write content (50-150 lines)
3. Read back immediately
4. Mark `completed`
5. Move to next

### Phase 4: Review Loop

After each section, check:
- **Coherence** - Flows from previous sections?
- **Completeness** - All promised details included?
- **Consistency** - Same terminology throughout?

Fix issues before moving on.

## Section Writing

### Structure

```markdown
## Section Title

[1-2 sentence intro]

### Subsection A
[Content with examples]

### Subsection B
[Content with examples]
```

### Guidelines

| Guideline | Target |
|-----------|--------|
| Lines per section | 50-150 |
| Subsection trigger | >100 lines |
| Code examples | Where relevant |
| Tables | For structured data |

## Anti-Patterns

| Anti-Pattern | Fix |
|--------------|-----|
| One-shotting 500+ lines | Write 50-100, review, continue |
| 20 placeholder sections | 5-7 sections, fill before adding more |
| Skipping reviews | Review after each section |
| Ignoring todo tracking | TodoWrite before and after |
| Perfectionism paralysis | Good-enough, move on, polish later |

## Quality Checklist

### Per Section
- [ ] Placeholder text replaced
- [ ] Code examples correct
- [ ] Terminology matches previous

### Final
- [ ] All sections filled
- [ ] Overview matches content
- [ ] Consistent formatting

## Tools

| Tool | When |
|------|------|
| `Write` | Initial structure, new sections |
| `Edit` | Replace placeholders, fix issues |
| `Read` | Review after each section |
| `TodoWrite` | Track section progress |

## Remember

> "Start with high-level overview, then incrementally add details section by section, reviewing as you go."
