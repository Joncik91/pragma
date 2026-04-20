# Pragma — Design

> **Scope:** the full v1.0 target design. Pragma ships evolutionarily — see
> [`roadmap.md`](roadmap.md) for what is in each release. v0.1 implements a
> thin slice of this design (manifest + freeze + verify + pre-commit hook);
> everything else is deferred to later increments.

---

## 1. Identity and mission

**Pragma — "The senior engineer you rent per session."**

Pragma is a Python tool that lets a non-developer ship production-grade
software without writing code. The user thinks in systems and writes a spec.
An AI assistant — in v1, Claude Code — implements it. Pragma's job is to
**hold the AI to the standards a senior engineer would enforce on
themselves**: simple over easy, SOLID, DRY, no overengineering, lint-clean,
actually tested, no hidden shortcuts.

The AI is competent. Given a clear spec, it usually does the right thing.
But it also:

- **Over-engineers** — reaches for abstractions, patterns, and dependencies
  the spec didn't ask for.
- **Forgets the boring stuff** — skips a lint pass, forgets to run types,
  doesn't add a test for the edge case it just coded around.
- **Violates discipline silently** — copies code instead of extracting a
  helper (DRY), lumps unrelated concerns into one function (SRP), hardcodes
  what should be injected, picks a big library when three lines would do
  (YAGNI).

A senior engineer catches those in code review. The non-coder user *cannot*.
Pragma is that reviewer — automated, enforced, non-negotiable. It sits
between the spec and the code and refuses to let the AI cut corners.

### Four layers of enforcement

1. **Before writing code** — the AI must produce a spec-backed Logic
   Manifest and failing tests before the gate unlocks.
2. **While writing code** — Claude Code hooks constrain what the AI can do:
   no editing `src/` while LOCKED, must annotate with `@pragma.trace` so
   intent is traceable, can't shortcut around a failing test.
3. **Before committing** — a safety battery runs: secrets, types, dependency
   audit, security SAST, dead-code detection, overengineering heuristics
   (complexity / file size / abstraction depth), lint, format, test pass,
   manifest sync.
4. **After the fact** — the Post-Implementation Log (PIL) tells the user in
   plain English whether the spec was actually exercised by the code and
   where the AI may have drifted.

### Target user

A non-developer who can describe a system clearly but cannot audit a diff.
They trust Pragma to enforce what a staff engineer would enforce.

### What Pragma is (honestly)

Pragma orchestrates existing tools (gitleaks, ruff, mypy, semgrep,
pip-audit, deptry), provides a small manifest / gate / PIL layer of its
own, and ships a tiny SDK (`@pragma.trace`). The identity is "senior
engineer on rails," but *mechanically* Pragma is a manifest-driven
linter-orchestrator + Claude Code hook bundle + OpenTelemetry post-hoc
reporter. Accepting that plainly is part of the design; pretending Pragma
is something more mystical invites overengineering.

### v1 is explicitly Claude-Code-coupled

Pragma v1 assumes Claude Code is the AI harness. The hook wiring, the
`permissionDecision: deny` semantics, the `additionalContext` injection
pattern, and the reliance on the AI to translate structured hook output
into chat prose — all are Claude Code specifics. Portability to other AI
harnesses is a v2 question. Do not engineer v1 for it.

### Success test (one sentence)

> *"I wrote a spec. The AI built it. Pragma forced the AI to build it the
> way a senior engineer would — simple, disciplined, verified — not the way
> it would have if nobody was watching. I didn't have to read the code to
> trust the outcome."*

### 1.1 The senior-engineer frame — applied to every action

Pragma's identity as "senior engineer on rails" isn't just about *what* the
AI writes (lint-clean, tested, simple). It's about *how the AI
communicates* — every artifact the AI produces must read as if a senior
engineer wrote it: with context, causality, and reviewability. Discipline
isn't only enforced at the code boundary; it's enforced at the **narrative
boundary**, wherever the AI leaves a trace for a human or future AI to
read.

Concretely, the senior-engineer frame is mandatory in all of these
surfaces:

- **Git commits.** Every commit message follows Conventional Commits and
  answers who / what / when / where / why: what changed (concrete files +
  intent), why it changed (which REQ-ID or which decision record motivated
  it), what it unblocks or depends on, and any non-obvious risks a reviewer
  should know. Generated automatically by Claude Code from the active
  slice's context, with `Co-Authored-By:` attribution. Pre-commit hook
  (commitlint-style gate inside `pragma verify`) rejects commits that don't
  meet the shape.
- **Pull-request descriptions.** When Claude Code opens a PR, the body is
  written from the senior-engineer frame: a short summary, the list of
  REQs shipped, the PIL verdict per REQ, the safety-battery status, known
  follow-ups, and an explicit "what to look at first in review" pointer.
  No "fixed stuff." Ever.
- **Decision records (`decisions/*.md`).** Every non-trivial judgment — a
  new dependency added, a discipline budget overridden, a security gap
  acknowledged, a mock-only permutation declared — produces an ADR. Format
  fixed: Context / Decision / Consequences / Alternatives considered / Who
  decided. Pragma auto-generates the scaffold; Claude Code fills it from
  chat + session state. Never a blank "we chose X because it made sense."
- **Hook remediation messages.** Every PreToolUse `deny` and PostToolUse
  `block` includes not just *what* is wrong but *what a senior engineer
  would do next* — concrete file paths, concrete commands, and the reason
  the rule exists. Example: not "complexity too high" but
  "`TaskManager.process` has cyclomatic complexity 14 (budget 10).
  Senior-engineer fix: extract the validation branch into a helper or use
  early returns. The budget exists because functions over ~10 paths are
  harder to test exhaustively than to rewrite."
- **PIL report prose.** The plain-English Markdown isn't marketing copy;
  it's a review handoff from a senior engineer to a non-coder
  stakeholder. State what was verified, what wasn't, what that *means* for
  the user's stated goal, what to do next. No jargon unless defined inline.
- **Chat summaries.** When Claude Code reports progress to the user in
  chat, it uses the same frame: *what changed this turn, why, what's
  next, any risk the user should weigh in on*. No "done!" with a checkmark
  emoji.
- **Error messages surfaced to the user.** When the 5% automation budget
  gets tapped — a genuine ambiguity, a destructive action, a security
  override — the message Claude Code shows the user reads like a senior
  engineer raising a concern: framed, contextualised, with a recommended
  default and explicit options.
- **Audit log entries (`.pragma/audit.jsonl`).** Every entry carries who
  (Claude Code session ID), what (action), when (ISO timestamp), where
  (file / REQ / slice touched), why (triggering event or spec ref). Future
  auditors — human or AI — can reconstruct intent, not just sequence.

This is enforced less by strict validation and more by **templates +
Pragma's own `CONTRIBUTING_RULES.md`**: every artifact type has a Jinja
template shipped by `pragma init` with the senior-engineer frame baked in,
and `CONTRIBUTING_RULES.md` instructs Claude Code to fill them honestly
rather than skim. Where a mechanical check is possible (commit message
shape, ADR required fields, hook remediation field presence), Pragma
verifies it.

The principle: **a senior engineer is always on the comms layer, not just
the code layer.**

---

## 2. Target user, scope, and out-of-scope

### 2.1 Who Pragma v1 is for

- Non-developers who can describe a system in words (inputs, outputs,
  states, failure modes) and who use Claude Code as their implementation
  partner.
- Willing to spend ~10 minutes on `pragma init` in exchange for not
  auditing diffs.

### 2.2 Who it is not for (v1)

- Experienced developers who already run pre-commit, mypy, and semgrep by
  habit — Pragma's scaffolding will feel heavy.
- Teams larger than ~3 people — v1 doesn't model multi-user gate
  coordination.
- Projects where the target app isn't Python — v1 SDK and safety battery
  are Python-only. **Most of Pragma is already language-agnostic**
  though; see §2.2.1 for what ports cheaply vs. what has to be rewritten
  per language.

#### 2.2.1 What's language-agnostic vs. Python-specific

Pragma is designed so the majority of its surface is
language-independent. The Python coupling is concentrated in two
identifiable layers; everything else can serve a target app in any
language when the per-language adapters land.

**Already language-agnostic (~70% of Pragma):**

| Component | Why it doesn't care about the target language |
|---|---|
| Manifest (`pragma.yaml`) | Plain YAML; REQ / permutation / touches are string-level concepts |
| Lockfile + integrity hash | SHA-256 over canonical JSON; no code parsing |
| Gate state machine | JSON state file + atomic writes; transitions are event-driven |
| Slice activation / completion | Lifecycle, not code analysis |
| Claude Code hooks | `.claude/settings.json` + subprocess; LOCKED/UNLOCKED logic reads state.json, not source code |
| Commit-message shape check | Regex on the message body |
| PR-description template | Jinja, filled from manifest + state |
| ADR scaffolding | Jinja; required-field enforcement is string-level |
| Hook remediation templates | Jinja + state.json lookups |
| Audit log (`.pragma/audit.jsonl`) | Append-only JSON lines |
| `pragma doctor` / `pragma migrate` | Self-check and schema migration, no target-code parsing |
| PIL aggregation logic | Groups OpenTelemetry spans by `logic_id` — the OTel protocol is language-neutral; any SDK in any language that emits the span schema feeds it |

**Python-specific (the two remaining layers):**

| Component | Why it's Python-only today | Cost to port |
|---|---|---|
| `pragma-sdk` — `@pragma.trace`, `set_permutation` | Python decorator + OTel Baggage via `contextvars` | **Medium.** Each target language gets its own SDK package (`@pragma/sdk` on npm for TS, `pragma-sdk` Go module, etc.). All share the one `logic_id` attribute schema in `shared/logic_id_schema.md`. The protocol is already language-neutral; only the wrapping ergonomics differ |
| Safety battery tool config | `ruff` / `mypy` are Python-only; `ruff format`, `mypy --strict` flags are Python-specific | **Medium.** Each language needs its own battery: TS gets `biome` / `tsc --strict` / `eslint` / `npm audit`; Go gets `golangci-lint` / `staticcheck` / `govulncheck`; Rust gets `clippy` / `cargo-audit`. Pragma ships the battery manifest per language; `pragma init --language=ts` picks the right `.pre-commit-config.yaml` template |
| AST overengineering checks | `pragma/core/discipline.py` uses Python's built-in `ast` module | **Medium.** Each language needs a parser: tree-sitter covers TS / Go / Rust / Java in one dependency; language-native parsers (`ts-morph`, `go/ast`, `syn`) give better fidelity. The *budgets* (complexity ≤ 10, LoC ≤ 60, depth ≤ 3) are universal; only the measurement implementation changes |

**What this means for v2:**

The v1 architecture already accommodates a TypeScript (or Go, or Rust)
target app without rewriting the core. Adding a language is additive: a
new SDK package, a new pre-commit battery template, and a new
discipline-checker plug-in. The manifest, gate, hooks, state machine,
audit log, and narrative templates don't change. This is why the
`pragma-sdk` vs. `pragma` package split in §3.1 matters — it isolates the
one thing that must ship per language from the dev-tool orchestrator that
stays in Python.

**Why v1 is Python-only anyway:**

Shipping one language well through all six increments (v0.1 → v1.0) is
already six and a half weeks (see [`roadmap.md`](roadmap.md)). Splitting
effort across three languages means none ship well. Python is first
because: (a) Pragma's own codebase is Python and we dogfood every
increment on ourselves; (b) OpenTelemetry's Python SDK is the most
mature; (c) the AI-hallucination-prone stack (loose-typed scripting with
heavy dependency surfaces) is where Pragma's value prop lands hardest.
TypeScript is the natural v1.1 target (same ecosystem, same kind of
user); Go and Rust follow if demand surfaces.

### 2.3 Operating model

The user interacts with **Claude Code** via chat. They never open a
terminal, never run `pragma` commands directly (except one bootstrap
`pragma init`).

**Claude Code drives the CLI.** For every workflow step, Claude Code
shells out to `pragma <command>` as a Bash invocation. Hooks wired into
`.claude/` fire automatically on lifecycle events.

**Pragma exposes three surfaces:**

| Surface | Who calls it | When |
|---|---|---|
| **CLI** | Claude Code via Bash | Between tool calls, as workflow steps |
| **Hooks** | Claude Code harness | Automatically on lifecycle events |
| **SDK** | Target app code (AI-authored) | At function-decoration time |

CLI output is **AI-consumable first, human-readable second**.
Machine-parseable JSON by default (`--format json`), human-readable
Markdown / Rich only when `--human` is passed.

### 2.4 In scope for v1

1. `pragma` CLI (Python, Typer-based, `pipx install pragma`).
2. Logic Manifest (`pragma.yaml` + `pragma.lock.json`) with greenfield and
   brownfield modes.
3. `pragma spec` interactive authoring commands.
4. Gate mechanics: `pragma unlock`, `pragma verify`, `pragma freeze`,
   slice-scoped state machine.
5. Claude Code integration: `.claude/settings.json` + four hooks wired by
   `pragma init`.
6. Pre-commit safety battery (see §6).
7. GitHub Actions workflow template (GitHub-only for v1).
8. Tiny Python SDK (`@pragma.trace`, `set_permutation`).
9. PIL (Post-Implementation Log) Markdown report.
10. Overengineering guardrails via `ast` analysis (complexity, depth, LoC,
    abstraction-for-one-subclass).

### 2.5 Out of scope (explicitly deferred)

- Non-Python target apps (TypeScript SDK is v1.1).
- Virtual filesystem / FUSE gating (aspirational).
- Symbolic execution / formal verification (research tier).
- Plugin architecture for custom gates / reporters.
- Multi-user gate coordination.
- Renovate, CodeRabbit, signed commits, SLSA provenance.
- GitLab / Bitbucket CI support.
- Dedicated AI-hallucination linters (still research-stage in 2026).
- In-IDE refactoring suggestions.

---

## 3. Architecture

### 3.1 Two packages (runtime-isolated)

Pragma ships as **two** pip packages from one monorepo:

- **`pragma-sdk`** — the runtime library. Contains `@pragma.trace` and
  `set_permutation`. Depends only on `opentelemetry-api`,
  `opentelemetry-sdk`. No Typer, no Pydantic, no Jinja. Target apps
  install this.
- **`pragma`** — the CLI + hooks + safety-battery orchestrator + report
  generator. Depends on `pragma-sdk` plus the dev toolchain. Installed via
  `pipx install pragma` into its own venv; never pollutes the target app.

The SDK runs in the target app's production; the CLI runs in the
developer's dev loop. They are two unrelated concerns tied together only
by the `logic_id` attribute schema. Bundling them forces production apps
to carry Typer / Jinja / PyYAML just to emit an OpenTelemetry span. Split,
each package does one thing.

```
pragma-repo/
  packages/
    pragma-sdk/            # runtime package (tiny)
      pyproject.toml
      src/pragma_sdk/
        __init__.py
        trace.py
        permutation.py
    pragma/                # dev-tool package
      pyproject.toml
      src/pragma/
        cli/ core/ hooks/ report/ narrative/ templates/ schemas/
  shared/
    logic_id_schema.md     # the one contract both packages share
```

### 3.2 Dependency budget

**`pragma-sdk` runtime deps** — 2 direct, both OpenTelemetry (any tracing
app already carries these):

| # | Package |
|---|---|
| 1 | `opentelemetry-api` |
| 2 | `opentelemetry-sdk` |

**`pragma` dev-tool deps** — 5 direct (~15 transitive):

| # | Package | Purpose |
|---|---|---|
| 1 | `pragma-sdk` | Schema constants shared with runtime |
| 2 | `typer` | CLI |
| 3 | `pydantic` | Manifest + state validation, schema generation |
| 4 | `pyyaml` | YAML parsing |
| 5 | `jinja2` | Template rendering |

Git operations via `subprocess.run(["git", ...])`. Schema validation via
Pydantic's `model_json_schema()`.

Target app's safety-battery tools (gitleaks, semgrep, ruff, mypy, etc.)
live in pre-commit's sandboxed venvs, not the app's runtime.

**Target app's runtime** gains three packages: `pragma-sdk` +
`opentelemetry-api` + `opentelemetry-sdk`. Any OpenTelemetry-tracing app
already ships the latter two; the net-new runtime weight is `pragma-sdk`
alone (~100 LoC).

### 3.3 Internal module layout (`pragma` package)

```
pragma/
  cli/                     # Typer app — AI-consumable
    __main__.py
    commands/
      init.py
      spec.py              # Pattern A: add-requirement. (Patterns B/C deferred to v1.1+)
      freeze.py
      unlock.py
      verify.py            # `verify manifest|gate|discipline|commits|adrs|all` subcommands
      report.py
      hook.py              # `pragma hook <event>` dispatcher
      milestone.py
      slice.py             # activate | complete | cancel | status
      doctor.py            # self-check; emergency recovery
      migrate.py           # state/manifest schema migrations (stub in v0.1)
  core/                    # Pure logic, no IO side effects
    manifest.py            # YAML load, schema validate, canonicalise
    gate.py                # State machine
    state.py               # .pragma/state.json atomic reads/writes
    matrix.py              # Permutation matrix ↔ test mapping
    discipline.py          # Overengineering heuristics (AST)
    git.py                 # Thin subprocess wrapper
    decisions.py           # User-decision routing
    integrity.py           # .claude/settings.json hash verify
  narrative/               # Senior-engineer frame — owns artifact generation
    commits.py             # build commit message from slice/REQ context
    prs.py                 # build PR description
    adrs.py                # build ADR scaffold, required-field enforcement
    remediation.py         # structured hook deny/block reasons
  hooks/                   # Hook event handlers (shell into `pragma hook <event>`)
    session_start.py       # + integrity check of .claude/settings.json
    pre_tool_use.py
    post_tool_use.py
    stop.py
  report/
    collector.py
    aggregator.py
    formatter_md.py
    formatter_json.py
  templates/               # Files copied by `pragma init`
    claude-settings.json
    pre-commit-config.yaml
    github-workflow.yml
    pragma-yaml.tpl
    contributing-rules.md
    conftest.py.tpl
    commit-message.tpl
    pr-description.tpl
    adr.tpl
    hook-remediation.tpl
  schemas/
    manifest.schema.json
    state.schema.json
```

### 3.4 One data-flow cycle

```
1. User in chat: "add user login with email/password, reject weak passwords"

2. Claude Code (following CONTRIBUTING_RULES.md):
   - Asks clarifying questions in chat (permutations, edge cases)
   - Bash: pragma spec add-requirement --id REQ-017 ...
   - Bash: pragma freeze           ← writes lock.json, state=LOCKED
   - Writes tests/test_req_017.py (failing tests for each permutation)
   - Bash: pragma unlock           ← verifies, flips to UNLOCKED
   - Writes src/auth.py with @pragma.trace("REQ-017") decorators
   - Bash: pytest -q               ← tests now pass, spans captured

3. Pre-commit hook on git commit:
   - gitleaks / ruff / mypy / semgrep / pip-audit / deptry / liccheck /
     check-added-large-files / pytest / pragma verify
   - Auto-fix + re-stage where possible; only genuine violations block

4. Claude Code: Bash: pragma report --human
   - Summarises in chat: "REQ-017 verified: 4 permutations exercised, 0 mocked."

5. User reviews chat summary, approves merge, or sends a spec revision back.
```

---

## 4. The Logic Manifest

### 4.1 Dual-file architecture

- **`pragma.yaml`** — human-authored (by the AI, on the user's behalf):
  multiline descriptions, comments, clean nesting, hand-editable via Edit
  tool.
- **`pragma.lock.json`** — machine-generated by `pragma freeze`:
  deterministic canonical form, `manifest_hash` for tamper detection.

Both files are committed. Integrity check:
`sha256(pragma.yaml) == pragma.lock.json.manifest_hash`. Divergence
hard-locks the gate until `pragma freeze` runs.

### 4.2 Hierarchical shape (greenfield + brownfield)

```yaml
version: "1"
project:
  name: "example-saas"
  mode: greenfield                   # greenfield | brownfield
  language: python
  source_root: src/
  tests_root: tests/

vision: |
  A multi-tenant task-tracking SaaS. Users sign up, create workspaces,
  invite collaborators, create tasks, assign them, track status.
  MVP ships email/password auth + workspace CRUD + task CRUD.

milestones:
  - id: M01
    title: "Auth foundation"
    description: "Operators can register, log in, and manage sessions."
    depends_on: []
    slices:
      - id: M01.S1
        title: "Registration"
        description: "Email/password signup with validation."
        requirements: [REQ-001, REQ-002, REQ-003]
      - id: M01.S2
        title: "Login"
        description: "JWT issue + refresh."
        requirements: [REQ-004, REQ-005]

  - id: M02
    title: "Workspaces"
    depends_on: [M01]
    slices: [...]

requirements:
  - id: REQ-001
    title: "Register with valid email + strong password"
    milestone: M01
    slice: M01.S1
    description: |
      The system accepts an email + password, validates the password
      strength (>= 8 chars, not in common-breach list), stores the
      operator record, and issues a JWT.
    touches:
      - src/auth/register.py
      - src/auth/passwords.py
    permutations:
      - id: valid_credentials
        description: "Valid email + strong password returns a JWT"
        expected: success
      - id: weak_password
        description: "Password < 8 chars returns 400"
        expected: reject
      - id: breach_list_password
        description: "Password on the breach list returns 400"
        expected: reject
      - id: malformed_email
        description: "Non-email string returns 400"
        expected: reject
    security_notes: |
      No user enumeration. Constant-time bcrypt comparison.
```

### 4.3 Gate operates at slice level

One slice is "active" at a time. The gate (LOCKED / UNLOCKED) applies only
to that slice. Other slices are "pending" and don't block. Dependencies
between milestones enforce order: `pragma slice activate M02.S1` fails if
M01 isn't fully shipped.

Brownfield mode = single implicit milestone `M00` containing a single
slice `M00.S0` with all requirements. The hierarchical structure is
invisible.

### 4.4 Invariants enforced on the manifest

1. Every `id` is unique.
2. ID formats fixed: `^REQ-\d{3,4}$` and `^[a-z][a-z0-9_]*$` for
   permutations.
3. Every requirement has ≥1 permutation. Single-permutation requires a
   `single_permutation_reason`.
4. `touches:` must map to files the AI later edits; PostToolUse
   cross-checks.
5. Description not optional.
6. Security-sensitive requirements (keywords: auth, password, token,
   admin, secret, ingest, export) require `security_notes`; missing
   triggers `pragma freeze --acknowledge-security-gap` flow.

### 4.5 Authoring flow (AI-driven)

Claude Code uses three patterns:

- **`pragma spec add-requirement`** (Pattern A, day-to-day) — after
  extracting detail from chat, runs the command with flags. Returns JSON
  diff for Claude to surface.
- **`pragma spec review`** (Pattern B) — scans whole manifest, emits JSON
  flags: missing permutations, vague descriptions, contradictions.
- **`pragma spec plan-greenfield`** (Pattern C, bootstrap only) — takes a
  free-text problem statement, produces a draft manifest skeleton with
  TODO placeholders. Used during `pragma init --greenfield`.

---

## 5. Gate mechanics and Claude Code hooks

### 5.1 State machine

State lives in `.pragma/state.json` (committed, schema-validated):

```json
{
  "version": 1,
  "active_slice": "M01.S1",
  "gate": "LOCKED",
  "current_req": "REQ-001",
  "manifest_hash": "sha256:a1b2c3...",
  "slices": {
    "M01.S1": { "status": "in_progress", "gate": "LOCKED",
                "activated_at": "2026-04-20T14:30:00Z" },
    "M01.S2": { "status": "pending", "gate": null }
  },
  "last_transition": {
    "event": "slice_activated",
    "at": "2026-04-20T14:30:00Z",
    "reason": "pragma slice activate M01.S1"
  }
}
```

All transitions are atomic (temp-file + rename). Full history appends to
`.pragma/audit.jsonl`.

| Event | From → To | Triggers |
|---|---|---|
| `pragma slice activate <id>` | inactive → LOCKED | AI starting work on a slice |
| `pragma freeze` | any → LOCKED | Manifest edited; resync required |
| `pragma unlock` | LOCKED → UNLOCKED | All active-slice REQs have failing tests per permutation |
| `pragma slice complete` | UNLOCKED → shipped | All tests green; PIL confirms coverage |
| `pragma verify --re-lock` | any → LOCKED | Integrity violation |

### 5.2 Four Claude Code hooks

All wired by `pragma init` into `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{"matcher": "startup|resume|clear|compact",
      "hooks": [{"type": "command",
                 "command": "\"$CLAUDE_PROJECT_DIR\"/.venv/bin/pragma hook session-start"}]}],
    "PreToolUse": [{"matcher": "Edit|Write|MultiEdit",
      "hooks": [{"type": "command",
                 "command": "\"$CLAUDE_PROJECT_DIR\"/.venv/bin/pragma hook pre-tool-use"}]}],
    "PostToolUse": [{"matcher": "Edit|Write|MultiEdit",
      "hooks": [{"type": "command",
                 "command": "\"$CLAUDE_PROJECT_DIR\"/.venv/bin/pragma hook post-tool-use"}]}],
    "Stop": [{"hooks": [{"type": "command",
                 "command": "\"$CLAUDE_PROJECT_DIR\"/.venv/bin/pragma hook stop"}]}]
  }
}
```

**SessionStart** — reads `.pragma/state.json`, emits `additionalContext`
with vision + active slice + gate + current REQ + rules in force. Caps at
~9500 chars (documented Claude Code limit as of 2.1.0); overflow routed to
`pragma state` paging command. Also verifies `.claude/settings.json`
integrity hash matches `.pragma/claude-settings.hash`; mismatch triggers
`pragma doctor`.

**PreToolUse (Edit | Write | MultiEdit)** — the lockout. Emits structured
`permissionDecision: deny` with machine-parseable `remediation` string
when:

- LOCKED and `file_path` matches `src/**`
- UNLOCKED but `file_path` not in active-slice requirement's `touches:`

Runs before permission mode, so blocks even under
`--dangerously-skip-permissions`.

**PostToolUse** — AST-analyses every edit to `src/`. Checks: decorator
presence, complexity ≤ 10, LoC ≤ 60 per function, depth ≤ 3, no
single-subclass base classes, no single-method utility classes. On
violation, emits `{"decision": "block", "reason": "..."}` so Claude
re-edits while context is fresh. Logs to `.pragma/audit.jsonl`.

**Stop** — runs `pragma verify all` before turn-end. Blocks turn-end on
half-finished state (red tests that should be green, manifest desync, new
src function without a matching test).

#### 5.2.1 Why four hooks instead of five

An earlier draft included `UserPromptSubmit` as a fifth hook, re-injecting
state on every user turn. Dropped: `SessionStart` already handles init +
compact; `PreToolUse` already re-reads state on every tool call. Adding a
third read-point per turn is duplicated work with no new coverage. The
prompt-injection check moves into `SessionStart` and `PreToolUse` (check
the tool call's `file_path` and any pasted content for markers). Simpler
composes; redundant hooks braid.

### 5.3 Defense in depth

| Layer | Where | Catches | Bypass closed how |
|---|---|---|---|
| 1. SessionStart (+ integrity check) | Claude Code harness | AI doesn't know the rules; hooks disabled | `.claude/settings.json` hash stored in committed `.pragma/claude-settings.hash`; SessionStart hook verifies and logs to audit.jsonl on mismatch; `pragma doctor` auto-runs |
| 2. PreToolUse `deny` | Claude Code harness | AI edits src/ when LOCKED | Known `deny` bugs → caught by layer 4/5 |
| 3. PostToolUse `block` | Claude Code harness | Discipline violations at edit-time | Caught at pre-commit / pre-push / CI |
| 4. Pre-commit battery | Local `git commit` | Secrets, types, tests, gate state, overeng | `--no-verify` → **pre-push layer (4b)** catches on `git push` |
| 4b. Pre-push hook | Local `git push` | Same battery as layer 4 | `--no-verify` on push → layer 5 |
| 5. CI `pragma verify all --ci` | GitHub Actions | Everything rechecked from clean state | Branch protection blocks merge |

No single layer is trusted. A `--no-verify` commit can land locally but
cannot reach `origin/main`: the pre-push hook blocks push, the CI blocks
merge, and branch protection blocks admin override.

### 5.4 What the user sees

The user never sees raw hook output. Claude Code digests and surfaces in
chat, e.g.:

> I tried to write `src/auth/login.py` but Pragma's gate is still locked —
> I need to add two failing tests first (REQ-001.malformed_email and
> REQ-002.empty_password). I'll do that now.

The translation lives in Claude Code's model. Pragma's job is to emit
structured `remediation` strings the AI can read and summarise faithfully.

---

## 6. Safety battery, overengineering guardrails, and PIL

### 6.1 Automation is the default

The user is never asked about routine work. Asking is reserved for:

- **Genuine spec ambiguity** — the AI cannot derive an answer from the
  manifest or prior decisions. Ask once; record the answer as an ADR.
- **Destructive or shared-system actions** — per CLAUDE.md rules (pushes,
  force operations, production touches).
- **Security gate overrides** — explicit `pragma freeze
  --acknowledge-security-gap` flow; never auto-accept a security shortcut.

Everything else is automation's problem: manifest freeze after YAML edits,
slice activation when dependencies clear, re-lock on integrity violation,
test runs, PIL generation, pre-commit auto-fix + re-stage, retry on
transient failures, AI course-correction on hook blocks, commit-message
generation, dependency pinning.

**Design rules:**

- No interactive prompts in CLI commands. All inputs are flags or stdin.
  When a command can't decide, it exits non-zero with
  `{"error": "needs_user_decision", "question": "...", "options": [...]}`
  JSON. Claude Code reads that and decides whether to ask the user in chat
  or make a reasonable default.
- `pragma init` is non-interactive. Claude Code gathers inputs from chat,
  shells out with flags preset.
- Every hook failure includes a `remediation` field for AI autonomy.
- Aggressive defaults; overrides later if evidence warrants.
- Self-healing over self-reporting.
- Batched surfacing per turn: one summary at the end, not five
  interruptions mid-flow.

### 6.2 Pre-commit battery (auto-runs on every `git commit`)

`pragma init` writes `.pre-commit-config.yaml` with this fixed battery.
Auto-fix → auto-stage → re-run is silent. Each Pragma check is a
*distinct subcommand* — one concern per exit code, one remediation per
failure.

**External tools (industry-standard):**

| Stage | Tool | Catches | Auto-fix? |
|---|---|---|---|
| Secrets | `gitleaks` (blocking) | Leaked keys / tokens | No |
| Format | `ruff format` | Formatting drift | Yes |
| Lint | `ruff check --fix --select E,F,I,B,S,UP,SIM,C90` | Undefined names, unused imports, bandit-equivalent, complexity, simplifications | Partial |
| Types | `mypy --strict` | Type errors | No |
| Security SAST | `semgrep --config=p/default --config=p/python --config=p/fastapi` | Permissive CORS, DEBUG=True, raw SQL, missing auth, confused-deputy | No |
| Deps — vulns | `pip-audit --strict` | Known CVEs | No |
| Deps — hygiene | `deptry` | Undeclared imports (hallucinated deps), unused deps | No |
| File hygiene | `check-added-large-files --maxkb=500`, `check-merge-conflict` | Binary commits, unresolved conflicts | No |
| Tests | `pytest -q --no-header` | Red tests | No |

**Pragma's own checks — each is a separate subcommand:**

| Subcommand | Catches |
|---|---|
| `pragma verify manifest` | YAML ↔ lock.json hash match; schema validity; `touches:` vs. `git ls-files src/` |
| `pragma verify gate` | state.json coherence; active slice's REQs all have failing / passing tests per permutation as gate state dictates |
| `pragma verify discipline` | AST overeng checks (§6.3); decorator presence when UNLOCKED |
| `pragma verify commits` | Commit message body present, WHY line present, `Co-Authored-By:` trailer present |
| `pragma verify adrs` | Required ADR files exist for each new dep / budget override / security ack introduced in this commit |
| `pragma verify integrity` | `.claude/settings.json` hash matches committed value; hooks not silently disabled |
| `pragma verify all` | Thin wrapper running all of the above; used by pre-commit and CI |

Each subcommand has one exit code, one remediation string. Pre-commit
runs `pragma verify all`; CI runs it with `--ci` flag for strict mode (no
auto-fix retries).

`.pre-commit-config.yaml` **also installs a `pre-push` hook** running
`pragma verify all --ci`. This closes the `git commit --no-verify`
window: the user / AI can bypass commit checks locally, but not push
checks. CI is the final layer.

**v1.1+ (deferred):** `zizmor` (Actions SAST), `actionlint`, OpenSSF
Scorecard, Dependabot, `liccheck`. Shipped as an opt-in supply-chain
bundle `pragma init --supply-chain-hardened` once a real user asks.

### 6.3 Overengineering guardrails (inside `pragma verify`)

AST-based, in `pragma/core/discipline.py`. Senior-engineer code-review
checks:

| Guardrail | Default budget | Rationale |
|---|---|---|
| Cyclomatic complexity | ≤ 10 per function | McCabe standard |
| LoC per function | ≤ 60 | Multiple responsibilities |
| LoC per file | ≤ 400 | File doing too much |
| Nesting depth | ≤ 3 | Flat > nested |
| Single-subclass base classes | 0 | Premature abstraction |
| Single-method utility classes | 0 | Should be a function |
| Empty `__init__.py` pass-through in src/ | 0 | API surface bloat |
| New dep without decision record | 0 | Every `requirements.txt` line needs `decisions/dep-<name>.md` |
| TODO / FIXME / XXX in src/ | 0 | Half-finished; must be a tracked REQ |

Budgets are **hard-coded in v1**. No `config.toml` override. If the
budget is wrong for a real user, that's data worth gathering before
making it configurable. Shipping configurability pre-demand is a YAGNI
violation and invites users to ratchet budgets up to mask overeng.
Override moves to v1.1+ if evidence warrants.

Set once, never asked about per-file.

### 6.4 SDK — `pragma-sdk` package (separate from `pragma`)

The SDK is a separate pip package with only OpenTelemetry as its runtime
dependency. Target apps install `pragma-sdk`; they never install `pragma`
(the dev-tool package) into their runtime venv.

```python
# pragma_sdk/trace.py
from opentelemetry import trace, baggage

_tracer = trace.get_tracer("pragma")

def trace(req_id: str):
    """Required on every public function in src/ when UNLOCKED."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            with _tracer.start_as_current_span(
                name=f"{req_id}:{fn.__name__}",
                attributes={
                    "logic_id": req_id,
                    "permutation": baggage.get_baggage("permutation") or "none",
                }
            ):
                return fn(*args, **kwargs)
        wrapper.__wrapped__ = fn
        wrapper.__pragma_req__ = req_id
        return wrapper
    return decorator
```

```python
# pragma_sdk/permutation.py
from opentelemetry import baggage
from opentelemetry.context import attach, detach

class set_permutation:
    """Context manager used in tests to tag the running permutation."""
    def __init__(self, name: str):
        self.name = name
    def __enter__(self):
        self._token = attach(baggage.set_baggage("permutation", self.name))
        return self
    def __exit__(self, *exc):
        detach(self._token)
```

Tests:

```python
from pragma_sdk import set_permutation
from src.auth.login import authenticate

def test_req_001_valid_credentials(live_db):
    with set_permutation("valid_credentials"):
        result = authenticate("user@example.com", "StrongP@ss1")
        assert result.token is not None
```

`InMemorySpanExporter` initialized by autouse fixture `pragma init` drops
into `tests/conftest.py`. No collector, no docker, no network — simple
over easy.

**Why OpenTelemetry is the substrate (not a dict).** Baggage propagates
across async / thread / subprocess boundaries that a dict does not;
target apps that *already* use OpenTelemetry tracing get Pragma
observability for free; the span-absence mock-detection heuristic relies
on OTel's before / after-function semantics, not on a synchronous
counter.

### 6.5 PIL — Post-Implementation Log

Triggers: (a) `pragma slice complete`, (b) `pragma report --human` on
demand.

**Data flow:** pytest runs → spans land in `InMemorySpanExporter` →
`pragma report` loads lock.json + span dump → for each active-slice
requirement, groups spans by `logic_id`, buckets by `permutation`,
cross-checks against manifest.

**Flags:** `fully exercised` / `partially exercised` /
`declared-but-not-seen` / `passed-but-mocked` (test named
`test_req_xxx_*` passed, no matching-logic_id span emitted during it —
novel Pragma heuristic).

**Example output:**

```markdown
# Pragma Verification Report — slice M01.S1 "Registration"
Generated: 2026-04-20 14:35:00
Gate: UNLOCKED → shipped

## Summary
3 requirements, 10 permutations declared, 9 verified, 1 flagged.

| REQ | Status | Declared | Verified | Mocked | Missing |
|-----|--------|----------|----------|--------|---------|
| REQ-001 Register with strong password | OK | 4 | 4 | 0 | — |
| REQ-002 Reject weak password | OK | 3 | 3 | 0 | — |
| REQ-003 Email verification sent | FLAG | 3 | 2 | 1 | — |

## REQ-003 — flagged
`test_req_003_timeout` passed, but no OTel span with `logic_id=REQ-003`
was emitted during that test. This usually means the test mocked the
email sender and the real send path was never executed.

Recommendation: add an integration permutation hitting the real send
path, or acknowledge as mock-only via `pragma spec update REQ-003
--permutation timeout --mock-acknowledged`.

## Overengineering check
All budgets within limits. 3 files in src/auth/, avg 83 LoC, max
complexity 6.

## Safety battery
gitleaks OK | ruff OK | mypy OK | semgrep OK | pip-audit OK | deptry OK

## Discipline audit (last 24h)
0 PostToolUse blocks. 2 auto-fixes (ruff format + ruff --fix).
```

Claude Code surfaces this in chat — typically as a short summary with
full Markdown attached.

### 6.6 User involvement per slice

~2 chat messages: initial description + final approval. Every other step
is automation.

---

## 7. Rollout and risks

See [`roadmap.md`](roadmap.md) for the evolutionary v0.1 → v1.0 rollout.
The key rules carried from Gall's Law:

- Each increment is **useful on its own** — a user can adopt Pragma at any
  increment and benefit.
- Each is shipped, dogfooded, and bug-fixed before the next begins.
- Pragma's own repo dogfoods the feature as soon as it lands.

### 7.1 Known risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Claude Code `permissionDecision: deny` bugs let AI edit src/ when LOCKED | Medium | Pre-commit + pre-push re-check; minimum Claude Code version pinned in `pragma doctor` |
| User / AI bypasses via `git commit --no-verify` | High | `pre-push` hook duplicates the check; CI reruns on push; branch protection blocks merge |
| User / AI disables `.claude/hooks/*` | Medium | `.claude/settings.json` hash committed to repo; SessionStart verifies hash; mismatch → `pragma doctor` auto-runs; audit log notes tamper |
| Interactive-prompt pressure exhausts automation | Medium | Decision routing in `core/decisions.py`; >3 decisions per slice triggers "simplify manifest" suggestion |
| Hook latency piles up | Medium | Measure in v0.3 dogfooding; if >200ms/hook, add long-lived daemon or use hook `type: http` against local socket |
| Semgrep / mypy false positives block legitimate edits | High early | Per-rule disables in `config.toml` require `reason:` field; auditable; defaults tuned during v0.4 dogfood |
| AI games discipline budgets (splits 61 LoC into 30+31 LoC) | Low | Budgets are signals, not proofs; we accept some gaming |
| Manifest `touches:` drifts vs. real `src/` | Medium | `pragma verify manifest` cross-checks against `git ls-files src/` |
| Pragma self-brick (bug in `verify` rejects valid state) | Medium | `pragma doctor` ships in v0.1; documents `emergency-unlock` escape hatch |
| Claude Code hook semantics change | Medium | `pragma doctor` checks minimum harness version on SessionStart |

### 7.2 Determinism

`pragma report` on a given git commit produces an identical report every
time it runs, given the same test inputs. This means:

- Report header timestamp is the **commit timestamp**, not wall-clock.
- Span-ordering is canonicalized by
  `(logic_id, permutation, test_nodeid)`.
- Random span / trace IDs are replaced by deterministic hashes in the PIL
  output.
- Test-run order is enforced by `pytest-randomly --seed=<commit_sha[:8]>`.

CI runs `pragma report` twice and diffs — mismatch fails the build.

### 7.3 Schema migration

`pragma migrate` is an explicit CLI command. Every schema change to
`pragma.yaml` or `.pragma/state.json` must ship with a migrator from the
previous `version:` field. v0.1 has the stub; v1.0 has the first real
migrator.

### 7.4 Open questions (deferred beyond v1)

1. Multi-user gate coordination — v1.1.
2. Non-Python target apps — TypeScript SDK, ~2 weeks in v1.1. The core
   (manifest, gate, hooks, narrative, PIL aggregation) is already
   language-agnostic; only the SDK, battery config, and discipline AST
   checks are Python-specific. See §2.2.1.
3. Docker / k8s / IaC scanning — checkov; auto-enable when detected; v1.1.
4. Non-GitHub CI — GitLab / Bitbucket; v1.x on demand.
5. Plugin architecture for gates / reporters — only when real demand
   surfaces.
6. Signed commits / SLSA provenance — right long-term, wrong UX for a
   non-coder now.
7. Per-REQ decision records indexing — wait for the pain.
8. OpenSSF Scorecard, zizmor, actionlint, liccheck — v1.1+ supply-chain
   bundle.
9. `pragma spec review` (Pattern B) and `pragma spec plan-greenfield`
   (Pattern C) — v1.1 + v1.0 respectively; Pattern A is the only v0.x
   surface.
10. Configurable discipline budgets — v1.1; v1 defaults are hard-coded
    until a real user shows the defaults are wrong.

### 7.5 v1.0 done criteria

Pragma v1.0 is done when all of:

1. A non-coder can bootstrap a greenfield Python project from zero to
   first shipped slice in under one hour of chat time.
2. Claude Code's own dogfooding use produces no false-positive hook blocks
   more than 1 per hour.
3. PIL report reviewed by three non-coders who say "I understood this
   without asking what a word means."
4. CI workflow runs on a clean GitHub Actions runner against a fresh
   `pragma init --greenfield` repo, goes empty → green → deployed
   artifact in one PR, zero manual steps beyond chat messages.
5. `pragma report` twice-in-CI produces byte-identical output.
6. `pragma doctor` on a self-bricked repo produces recovery steps without
   requiring Pragma source knowledge.
