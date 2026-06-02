---
id: tier-1/scope-and-boundaries
name: Scope and boundaries
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Stay inside the project working tree. Ask before touching source-of-truth files in shared locations.
---

# Scope and boundaries

1. **Stay inside the project's working tree.** No reads/writes to iCloud, the user's `Documents` folder, other projects' working trees in your workspace, or unrelated paths unless explicitly authorized for the task. The working tree includes any `data/` symlinks the project explicitly declares.
2. **Source-of-truth files in shared locations are read-only by default.** Files in cloud-storage-linked directories that a project references are usually source-of-truth for non-git workflows (writing, scans, datasets). Ask before moving, renaming, or overwriting them. Read access is fine.
3. **Don't generalize from one repo to another silently.** A pattern that works in repo A may have been deliberately rejected in repo B. If a rule isn't documented in *this* project's CLAUDE.md, treat it as not-yet-decided here.
4. **External APIs and paid services are scope boundaries too.** Don't call NCBI, OpenAI, Anthropic, ESM API, or other quota'd / paid endpoints in unattended loops. See `tier-2/external-api-cost` if the project opts in.
