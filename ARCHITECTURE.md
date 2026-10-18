# Mushin — Architecture Contract

**Status:** Draft for review
**Authority:** Target architecture
**Scope:** Mushin Engine and its integration with external components

## 1. Fundamental Principle

Mushin is a deterministic, modular simulation engine built from independent transformations.

**State is truth.**

The engine establishes and maintains authoritative simulation state. Rules constrain what can happen. Probability resolves permitted uncertainty. Observation establishes previously unresolved possibilities.

Language models may interpret, propose, or narrate. They do not independently establish canonical reality.

Missing information is not permission to invent facts.

Probability may determine which authorized outcome becomes established. Once committed, that outcome is canonical and must not be independently rerolled. Reproducibility of sampling is distinct from persistence of the selected result.

## 2. Composable Isolation

Mushin is constructed from independent, composable processing stages.

### Isolation

Every stage operates according to the same fundamental pattern:

**Input → Transformation → Output**

A stage must not require knowledge of the identity, implementation, or existence of its upstream or downstream neighbors.

Stages communicate through explicit, versioned data contracts, not hidden dependencies or shared mutable state.

Airgapping refers to architectural isolation. It does not necessarily require separate processes, machines, or programming languages.

Processing stages must not directly import, invoke, or access the private state of other processing stages. Cross-stage coordination belongs to the composition mechanism and occurs through declared interfaces.

Shared schemas, validators, and explicitly defined infrastructure or service interfaces are permitted, provided they do not create hidden dependencies on another processing stage or grant unauthorized state access.

### Composability

Pipeline composition, ordering, and routing are managed externally to individual stages.

Every compatible stage boundary is a potential insertion point for future modules, including modules not yet conceived.

Stages may be inserted, removed, or replaced without rewriting unrelated components.

Compatibility is determined by interface contracts, authority restrictions, and causal requirements—not by the identity of neighboring modules.

### Graceful Degradation

Optional modules must have defined absence behavior.

Removing an optional module must preserve coherent baseline operation within the capabilities supported by the remaining system.

A module may increase simulation resolution, sophistication, or specificity without becoming a mandatory dependency.

A compatible pass-through or baseline implementation must exist wherever an optional stage would otherwise leave a required processing responsibility unfulfilled.

### Authority Independence

A stage's authority is defined by its contract, not by its position in the pipeline.

Insertion into a pipeline does not grant permission to modify canonical state.

Only authorized commitment operations may establish or change simulation truth.

All transformations remain subject to applicable rules and canonical constraints.

## 3. Application-Level Architecture

Mushin's intended application-level chain is:

**Mushin Engine → Prose Conditioner → Renderer**

Each component is independently replaceable and operates through explicit input and output contracts.

### Mushin Engine

The engine owns authoritative simulation state, constraints, probability resolution, and canonical commitment.

Its output describes simulation results in a structured, presentation-independent format.

The engine-to-consumer contract must distinguish established facts, unresolved information, authorized presentation material, and diagnostic information where applicable. Proposals and unresolved possibilities must not be represented as committed events.

The engine must not require knowledge of the prose conditioner, renderer, user interface, or host application.

### Prose Conditioner

The prose conditioner transforms structured simulation output into narrative representation.

It may determine wording, tone, detail, and presentation style within the constraints of established simulation truth.

It does not establish, modify, or contradict canonical state.

The prose conditioner must not require knowledge of the engine's internal implementation or the renderer receiving its output.

### Renderer

The renderer presents received output through a chosen interface.

Possible interfaces include a terminal, graphical application, web client, or another compatible presentation system.

The renderer must not require access to engine internals or canonical storage.

Rendering must not change simulation truth.

### Independent Composition

The application chain is a reference composition, not a mandatory three-component dependency.

A host application may consume structured engine output directly, omit prose conditioning, substitute another compatible transformation, or provide its own renderer.

Compatible transformations may be inserted at defined boundaries without requiring changes to unrelated components.

Each component must remain independently usable wherever its input contract is satisfied.

No component may assume that another specific component exists upstream or downstream.

The external application and the internal engine pipelines follow the same principles of isolation, composability, and explicit authority.

## 4. Internal Engine Pipeline

The engine itself consists of independently composable processing stages.

Its responsibilities include:

- Input interpretation and normalization
- Context and candidate construction
- Eligibility and possibility constraints
- Optional candidate and probability-weight transformations
- Probability resolution and observation collapse
- Rule validation
- Canonical commitment
- Structured output

This is a responsibility inventory, not a frozen execution order.

Actual stage ordering must preserve causal correctness and state authority.

Every meaningful transformation boundary must support future compatible insertion without requiring changes to unrelated stages.

Optional modules may refine available options and weights, but cannot independently authorize impossible outcomes or commit canonical state.

### Internal Pipeline Composition and Boundaries

The engine must support independently composed processing pipelines rather than a single permanently hardcoded sequence.

Every stage has a defined input contract, output contract, responsibility, and authority level.

Pipeline composition is external to individual stages. No stage calls its next stage directly or relies on the identity of its predecessor.

Every stage boundary is a potential insertion point for a compatible future transformation, subject to schema compatibility, causal ordering, and authority restrictions.

Pipelines may differ according to the operation being performed. Modules need not participate in operations outside their responsibilities.

Candidate generation, probability weighting, probability resolution, rule validation, and canonical commitment are conceptually distinct responsibilities, even where Mushin Lite currently combines them.

A module may refine or constrain possibilities only within its declared authority. It must not restore candidates prohibited by authoritative rules, fabricate canonical facts, or bypass commitment validation.

A pipeline's stages must produce explicit outputs rather than communicating through hidden shared mutable state.

Where an optional module is absent, the pipeline must supply the defined baseline implementation or compatible pass-through behavior.

An expansion point is a property of the interface between stages, not a hardcoded location reserved for one named module.

Pipeline ordering is a responsibility of the composition mechanism and must preserve all applicable architectural invariants.

## 5. Authority and Canon

Canonical state is authoritative.

Only authorized commitment operations may establish or change canonical facts.

Proposals, evaluations, probabilities, interpretations, and narrative descriptions are not canonical truth.

Previously committed history must constrain subsequent resolution.

Unknown, missing, malformed, or contradictory information must not silently become permission.

Modules must not bypass commitment validation.

## 6. Subtractive Simulation

Mushin operates by constraining possibility.

Established facts and rules remove incompatible outcomes from the possibility space.

Probability operates only over permitted candidates.

Observation may resolve previously uncommitted possibilities, but cannot contradict established canon.

Unobserved details need not be generated prematurely.

Committed consequences may exist before their detailed narrative explanation, provided sufficient causal constraints are preserved to prevent retroactive contradictions.

An offscreen event can resolve and commit consequences without the player's knowledge. Observation can subsequently reveal those consequences or resolve remaining details.

## 7. Graceful Degradation

**Mushin comes already degraded.**

The engine must provide a coherent baseline simulation without requiring optional high-resolution modules.

Optional modules refine, extend, or increase the resolution of existing capabilities. They must not become hidden prerequisites for baseline operation.

### Baseline Operation

Every fundamental simulation responsibility must have a defined baseline implementation.

Specialized capabilities introduced solely by optional modules need not have baseline equivalents. Their absence must preserve coherent operation of the declared baseline system, rather than requiring a reduced version of every possible extension.

The baseline may be simpler, less detailed, or less context-sensitive than an enhanced implementation, but it must remain internally coherent and respect canonical state.

Low-resolution simulation is a legitimate operating mode, not an error condition.

### Optional Module Removal

Removing or disabling an optional module must not require unrelated modules to be rewritten.

The pipeline must continue using its defined baseline implementation or a compatible pass-through where appropriate.

A pass-through is valid only when the omitted transformation is not itself necessary to preserve the baseline responsibility.

Optional module removal must not create contradictory state, bypass validation, or transfer authority to another component implicitly.

### Resolution and Refinement

Higher-resolution modules may refine candidate generation, decision factors, probability weights, and other simulation processes within their declared authority.

They must preserve established constraints and produce outputs compatible with the downstream contract.

The enhanced implementation must not operate as a competing, independent authority alongside the baseline implementation.

Where baseline and enhanced decision-making cover the same responsibility, the composition mechanism must establish one coherent authoritative decision path.

### Failure and Unavailability

Optional module absence, incompatibility, and runtime failure are distinct conditions.

Expected absence must follow the documented baseline behavior.

Incompatibility or failure must be reported or handled explicitly according to the module contract.

Fallback must never silently invent facts, bypass constraints, or conceal a failed canonical commitment.

Graceful degradation does not imply silent recovery from arbitrary failures. A fallback is permitted only when its triggering conditions and state-safety guarantees are defined by the contract.

### Architectural Requirement

Every optional module contract must identify:

- The baseline behavior available without the module
- What additional resolution or capability the module supplies
- How its output integrates with the existing pipeline
- What happens when it is removed or unavailable
- Which responsibilities and authorities remain unchanged

Graceful degradation must be considered during module design, not retrofitted after implementation.

## 8. NPC Archetypes and Behavior

Mushin must support NPCs as autonomous simulated actors rather than entities whose existence and activity depend on player interaction.

**The player is not the main character.**

### Archetype Baseline

Every NPC has a baseline behavioral model defined by its archetype and applicable world constraints.

Archetypes provide low-resolution behavioral decisions, including the possibility of initiating interactions and responding to events.

An NPC must not become passive merely because the optional Behavior module is absent.

Archetype-driven decisions remain subject to the same probability resolution, rule validation, and canonical commitment requirements as enhanced decisions.

### Optional Behavior Module

Behavior is an optional high-resolution expansion of the NPC decision-making system.

It may refine behavioral possibilities using dispositions, context, prior events, relationships, motivations, and other supported primitives.

Behavior operates at the appropriate upstream boundaries before the relevant decisions and probabilities are resolved.

It must not independently select canonical outcomes, commit state, or bypass governing rules.

The module must remain replaceable and removable without requiring changes to unrelated pipeline stages.

### Unified Decision Path

Archetypes and Behavior must not operate as competing decision-making authorities.

When Behavior is installed, its authorized refinements are incorporated into a single coherent decision path.

When Behavior is absent, the archetype baseline supplies the required decision information.

Both operating modes must produce compatible downstream output.

### Independent NPC Activity

NPC activity must not require player observation, player participation, or narrative presentation.

Where supported by the installed simulation capabilities, NPCs may initiate interactions with one another and produce persistent consequences outside the player's immediate awareness.

Objective consequences may become canonical before their detailed narrative explanation is generated.

Any later explanation must remain consistent with established history and constraints.

### World Independence

NPC behavior must not assume romance, friendship, hostility, or any particular genre as its default purpose.

Social interaction is one possible expression of simulated behavior, not the engine's organizing principle.

Cartridges and optional modules may introduce specialized behavioral systems without making those systems mandatory for other worlds.

### Implementation Independence

This section defines architectural responsibilities, not a required class hierarchy, specific algorithm, or fixed list of dispositions.

The behavioral architecture must remain open to future primitives, transformations, and replacement implementations.

## 9. World and Player Agnosticism

Mushin must not assume a particular genre, setting, narrative structure, or application.

The engine must not require the player to be the organizing principle of the simulated world.

NPCs and other actors may participate in events independently of player observation, according to installed capabilities.

Player observation may determine when unresolved details are established, but does not grant authority to rewrite previously committed consequences.

Cartridges supply world-specific content, rules, and configuration without imposing those assumptions on the engine core.

## 10. Module Lifecycle and Compatibility

Every module contract must define:

- Accepted input and produced output
- Transformation responsibility
- Permitted and forbidden effects
- Required capabilities and dependencies
- Pipeline insertion requirements
- Absence and fallback behavior
- Failure handling
- Compatibility and version requirements

Module installation must not silently transfer canonical authority.

Incompatible modules must fail explicitly rather than produce unvalidated state.

## 11. Architectural Change Control

This contract governs the intended architecture.

Current implementation details do not automatically supersede it.

Substantive architectural decisions must be recorded when agreed upon and reviewed before implementation.

Proposed revisions must identify affected invariants and explain the reason for change.

Implementation gaps are maintained separately from the contract.

Architectural deviations do not authorize refactoring without explicit approval.

## 12. Development Review Requirements

Before implementing a change, determine:

1. Which processing stage owns the responsibility?
2. Which input and output contracts are affected?
3. Does the change introduce hidden upstream or downstream coupling?
4. Can compatible future modules still be inserted at the relevant boundaries?
5. Does the system still operate when optional modules are absent?
6. Does the change preserve canon authority and fail-closed behavior?
7. Are existing commitments being preserved or deliberately revised?

Architecture compliance must be reviewed alongside functional correctness.

---

**Guiding principle:** Mushin is not a monolithic game engine with optional extensions. It is a composition of independent transformations whose capabilities and resolution can be expanded without sacrificing its authoritative simulation core.