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

Determinism means that explicit inputs, constraints, configuration, and supplied random state determine a transformation’s result. External model output and other nondeterministic inputs must be treated as explicit inputs, not as canonical authority. This does not require identical prose or repeated sampling to produce identical results without the same inputs and random state.

### Lite and Full

**Mushin Lite is a complete, standalone world simulation engine.** Lite owns canon, possibility constraints, probability resolution, observation collapse, commitment, persistence, and the mechanisms necessary for a functioning world, including baseline NPC archetypes. This defines Lite's architectural responsibility; the current repository implements bounded portions and retains the gaps recorded separately.

**Mushin Full is Lite with the optional Behavior expansion.** Full attempts emergent individuality through interacting low-order primitives, not increasingly elaborate high-order personality statistics. It is experimental: emergent individuality is a research objective, not an established achievement. Removing Behavior returns NPCs to their baseline archetype mechanisms while preserving established world history and perspectives under the lifecycle contract in §7.

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

Insertion is permitted at any compatible declared boundary, not at arbitrary instructions inside a stage. A transformation that changes previously validated material must preserve that validation’s guarantees or route the changed output through the required validation again. External composition may be implemented in ordinary host code; a dynamic registry or plugin loader is not required.

Readable procedural stages, independently composed as input → transform → output, remain appropriate. Do not introduce OOP boilerplate, object hierarchies, or abstractions merely to match conventional architecture. Established programming techniques remain available where they serve the contract.

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

The engine-to-consumer contract must distinguish established facts, unresolved information, authorized presentation material, and diagnostic information where applicable.

Canonical truth and permission to disclose it are distinct. The output contract must identify the intended audience and provide only material authorized for that audience, including explicitly authorized uncertainty or rule-block outcomes. Debugging privileges must not implicitly become player knowledge. A declared disclosure boundary must apply before material reaches an audience-facing conditioner or renderer; this does not require a general testimony or private-knowledge system. Proposals and unresolved possibilities must not be represented as committed events.

The engine must not require knowledge of the prose conditioner, renderer, user interface, or host application.

### Truth and Observer Packets

The intended event output contract establishes one authoritative **truth packet** for a committed event and one **observer packet** (also called a **subjective packet**) for each applicable observer. Observer packets represent established individual perspectives, not alternative prose versions of the truth packet. Their observer identity and subjective status must remain distinguishable from objective event truth. Establishing that an observer holds a perspective does not establish its interpretation as objective reality; perspective establishment still requires the engine's authorization and commitment path.

Audience authorization controls which packets and information an external consumer may receive. No actor inside the world has unrestricted access to the truth packet. The proposed player disclosure records below cover narrowly learned outcomes; they neither implement subjective interpretation nor replace the observer-packet contract. Observer applicability, packet schemas, perspective persistence, and the atomicity of event/perspective commitments remain explicit design work; no schema or simultaneous transaction is implied here.

Packets are presentation-independent native interfaces. They are intended to support LLM prose, TTS, ANSI/TUI, ComfyUI, Unity, and Godot without granting those systems canonical authority. Downstream conditioning and rendering cannot write backward into committed canon. A host may submit a new input only through normal authorization and commitment. Existing Lite dictionaries and command interpretation packets are not evidence that this complete truth/observer packet standard is implemented.

### Prose Conditioner

The prose conditioner transforms structured simulation output into narrative representation.

It may determine wording, tone, detail, and presentation style within the constraints of established simulation truth.

It does not establish, modify, or contradict canonical state.

Truth alone is not permission to reveal it. Conditioning must preserve the supplied disclosure limits and must not turn latent alternatives or diagnostics into narrative assertions. Integrations must define how unauthorized or invalid conditioned output is rejected or replaced with safe authorized output; prompt instructions alone do not demonstrate that guarantee.

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

### Lite Audience Disclosure Contract — Architecture Checkpoint

**Status: specified, not implemented.** The current Lite interpreter and presentation context still receive active canonical facts without audience filtering. This contract does not certify the current runtime as audience-safe. Production integration and its acceptance tests must be completed together before that claim is made.

#### Responsibilities and authority

Canonical commitment establishes world truth. Authorized disclosure commitment records that an audience legitimately acquired a specified part of that truth. Pure audience projection constructs permitted input for interpretation and presentation. These are distinct responsibilities with separate interfaces; disclosure must not become a prerequisite for NPC evaluation, opportunity selection, episode commitment, or historical reuse.

Initially the only supported audience is the exact ID `player`, and the only NPC disclosure scope is `episode_outcome` under `truthful_npc_inquiry_v1`. A disclosure grants neither access to the whole NPC record nor future refinements such as a disagreement initiator. Unknown audiences, scopes, sources, or policy versions fail closed. Neither an LLM, renderer, arbitrary text, nor a caller-supplied knowledge flag can grant disclosure.

The first acquisition mechanism is the existing explicitly bound truthful NPC inquiry. Automatic witnessing is not supported: allowed places are episode permissions, not an established occurrence location; current co-location is not evidence of historical witnessing. Listening to configured ambience does not reveal episode history. Future witnessing, investigation, or evidence policies require independent authorization and may disclose only the aspects they establish. Evidence of a consequence does not automatically disclose its cause, actor, or motive. A momentary observation cannot prove an episode-wide negative outcome.

#### Proposed version-1 storage and references

Persist disclosure inside the existing canonical save, not in a separate knowledge database. The proposed extension is `disclosure = {version: 1, world_generation: <opaque-id>, npc_generation: <opaque-id>, records: [<record>, ...]}`. Generation identities distinguish resets, not time; they are established only by authorized setup, reset, or the first authorized disclosure transaction. Pure projection and loading never create them. Missing extension data means no recorded acquisitions, not public history. Malformed or unsupported extension data must be preserved and rejected, not silently replaced.

Each NPC record has exactly `version`, `audience`, `scope`, `policy`, `reference`, and `source`. `version` is 1; `audience` is `player`; `scope` is `episode_outcome`; `policy` is `truthful_npc_inquiry_v1`. `reference` contains `world_generation`, `npc_generation`, `episode_id`, `event_id`, and `content_sha256`. The digest binds the authorized historical payload: episode ID, event fact ID/type/text, and committed outcome, serialized with an explicitly defined canonical JSON encoding (UTF-8, sorted keys, compact separators, no NaN). Mutable fact status and unrelated resolution extensions are excluded from the content digest but validated separately for disclosure eligibility. `source` identifies the exact installed inquiry binding and respondent ID. Do not store an editable second copy of the outcome as knowledge truth.

The underlying episode resolution and uniquely referenced event must exist and agree. Missing, duplicate, changed, or contradictory references authorize no disclosure. Numeric IDs or matching prose alone are insufficient; generation and content binding are mandatory. Historical payloads must come from committed history, not reconstruction through mutable episode definitions. The disclosure implementation must not rewrite NPC resolutions to represent knowledge.

This schema records acquisition provenance, not a general belief or testimony system. Persisted records are trusted only as canon-owned data validated against their content references. Digests detect content/reference mismatch; they are not signatures and do not protect against a user deliberately editing the save. The trust boundary is the host and its authorized canon operations.

#### Inquiry authorization, freshness, and persistence

A fresh disclosure request must independently validate the exact installed inquiry binding, supported audience/scope/policy, respondent and other participant, episode identity, committed outcome/event reference, and respondent availability at the player's unambiguous canonical location. Shared pure authorization rules may be reused; the disclosure producer or renderer must not be asked to approve its own proposal. Validate freshness again at commitment, including generation, source configuration, reference content, and availability. A generic arbitrary-fact grant endpoint is outside this slice.

External inquiry orchestration validates eligibility before episode activation, obtains a committed or reused episode outcome, then requests disclosure commitment. Only after successful disclosure persistence may the outcome be presented. Episode commitment and disclosure commitment are separate units: disclosure failure must not erase the event or rerun its transitions. An uncommitted outcome is diagnostic material, never learnable history.

A disclosure transaction builds a pending snapshot, validates it, persists it atomically, and only then updates caller memory. A known-safe write failure permits an explicit retry; an uncertain persistence result requires reconciliation. Failure responses to the player contain no outcome, hidden identities, or internal diagnostic details. Existing episode reuse supplies historical truth without new draws or transition replay.

Identical audience/scope/reference/source records are idempotent. A conflicting record must fail rather than replace history. Projection of an existing valid acquisition does not depend on the original provider, current respondent availability, or the continued installation of its inquiry binding. Repeating a live inquiry still requires its current availability/binding authorization; remembering previously learned history does not.

#### Reset and reference lifecycle

A full world reset clears all disclosure records and rotates the world generation as part of the same persisted reset unit. An NPC reset clears NPC-outcome records and rotates the NPC generation in the same unit as the NPC reset; unrelated acquired information must survive. Stale pre-reset proposals cannot be committed afterward, even if an episode ID, fact ID, and text are recreated identically. Load must preserve generations and must never infer them from wall time or fact counters.

Selective fact deletion, corruption, or a reference mismatch invalidates affected disclosures without inventing replacement truth. Undisclosed events remain canonical and causally meaningful. Ordinary state supersession must never transfer a grant from an old fact to its replacement. Reset atomicity is required for this extension; existing memory-before-save reset/setter paths must not be assumed to provide it.

#### Pure player-context projection

The engine constructs a versioned, detached player envelope before any model or renderer receives context. Its declared inputs are authoritative state, the audience ID, approved room/content definitions, and operation-specific authorized turn results. It produces current perception, learned history, and turn results as separate fields. It performs no sampling, disclosure commitment, state mutation, loading, or window advancement. Projection is not acquisition: rendering an envelope must never create knowledge records.

For the initial Lite perception policy, allowlist current-room display name, description, ambience, visible exits, currently accessible entities, inventory, and supported visible properties. Only explicitly declared properties are exposed; current room membership must not grant every entity attribute. Keep ordinary canonical rule validation and commitment on full state. Do not weaken rules by passing a player-filtered world into them.

Room/content definitions require a presentation allowlist. Never pass complete room dictionaries, observation constraints, latent alternatives, future-detail fields, raw facts, whole NPC records, internal dispositions, proposal bases, or transition diagnostics. Learned history includes only the content authorized by valid persisted references. Historical knowledge is labeled historical and must not expose later offscreen state changes or masquerade as current perception.

Both command interpretation and prose conditioning consume this engine-produced envelope. Their adapters must reject legacy raw-canon inputs on player-facing entry points rather than silently treating them as authorized context. A renderer formats supplied material; it cannot query more canon or grant itself disclosure. Optional modules can transform only authorized envelope material and cannot bypass the projection boundary.

Turn-local action results and rule-block messages require typed, operation-specific authorization, not an arbitrary trusted string field. Only the permitted result of the current validated action may be included. User input is untrusted request text, not a canonical assertion. Projection failures use generic safe output; detailed rejection reasons remain developer-only.

Deterministic rendering is the safe baseline. Filtered model inputs prevent canonical secrets from entering those requests; they do not establish that unrestricted generated prose is semantically authorized. Free-form narration needs a separately validated output contract or a safe deterministic fallback before it can receive an audience-safety guarantee.

#### Ordinary gameplay, diagnostics, and migration

Preserve the existing meanings of look, listen, inventory, movement, reference resolution, aliases, search/inspect, lazy collapse, and rule-block outcomes. A current supported perception policy may authorize visible state without a permanent record for every render. Remembered discoveries require acquisition provenance: collapse markers alone do not identify the learned fact, and the current CLI discards discovery IDs/category/source metadata when calling `add_fact`.

Before full integration, specify and implement a narrowly authorized observation acquisition path that retains the selected discovery identity, room/space/verb, and content-bound fact reference. It must validate the permitted discovery and canonical constraints independently of a producer. It must not infer historical causes from optional candidate annotations. This is an ordinary-observation compatibility responsibility, not permission for a general historical-fact grant API or a second NPC disclosure scope. The atomic unit for discovery facts, collapse markers, and acquisition records must be defined and tested; separate memory-before-save `add_fact` calls do not satisfy that requirement. The corresponding bounded action-result handoff must preserve current rule-block precedence and avoid automatic disclosure of unrelated consequences.

Existing saves never silently acquire records on load. Legacy NPC events remain undisclosed until an authorized acquisition. Explicit migration may bind known fixture observations to declared provenance only when the necessary evidence is established; arbitrary active prose must not be classified public from wording or status. Previously printed discoveries cannot generally be reconstructed from current saves, so compatibility must distinguish current perception from unavailable historical acquisition evidence. Preserve unrecognized world and extension data rather than deleting it.

Explicit developer diagnostics may inspect complete canon and previews through a host-selected developer path. They do not create player knowledge. Full-canon logs, raw model packets, preview candidates, and NPC transition diagnostics must not appear automatically in ordinary gameplay or be appended to player model context. This boundary is separate from filesystem access control; the save remains inspectable by its owner.

#### Implementation checkpoint and acceptance gate

This contract is the architecture checkpoint for the disclosure milestone. No production disclosure path is implemented by this documentation update. The integration must cover canon-owned records and resets, independently authorized NPC inquiry, ordinary observation acquisition/atomicity, typed turn results, safe interpreter and presentation inputs, and separated diagnostics. Shipping only an NPC-event filter would leave other disclosure paths open and is not a completed boundary.

Acceptance must demonstrate hidden-event persistence without player/model leakage; scoped authorized inquiry; rejected forged/unavailable/uncommitted acquisition; reload/provider-removal retention; persistence failure without disclosure or premature memory change; fail-closed legacy/corrupt metadata; no inferred witnessing; no disclosure of later state through old knowledge; reset/generation protection; projection purity; and regression coverage for ordinary observation, collapse idempotence, movement, inventory, aliases, and rule-block rendering. Existing NPC regression tests remain required. Keep single-threaded/current-caller-state limitations explicit; this work adds no scheduler, general sensory simulation, testimony, beliefs, deception, or high-resolution Behavior.

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

Orchestration may invoke declared stage interfaces, route explicit results, and enforce lifecycle and ordering requirements. Knowing which implementations are installed is appropriate for the composer, not for the stages it composes. Orchestration must not acquire canonical write authority merely by coordinating stages, and must not hide substantive transformations or authorization decisions between declared boundaries.

## 5. Authority and Canon

Canonical state is authoritative.

Only authorized commitment operations may establish or change canonical facts.

Proposals, evaluations, probabilities, uncommitted interpretations, and narrative descriptions are not canonical truth. An authorized commitment of an observer perspective establishes that perspective, not the objective truth of everything the observer believes.

Previously committed history must constrain subsequent resolution.

Unknown, missing, malformed, or contradictory information must not silently become permission.

Modules must not bypass commitment validation.

### Commitment Contract

Commitment must independently authorize the requested change against current authoritative state and governing constraints. It must not trust a proposal merely because it came from an approved producer, nor require that producer’s implementation to be installed. Shared pure authorization validators and declared infrastructure are permitted; calling a proposal-producing stage to obtain its approval is not a substitute for an independent commitment contract.

Each commitment operation must declare the state on which its authorization depends and validate freshness at the write boundary. A stale proposal must be rejected or handled by an explicitly defined revalidation protocol; it must not silently become a different selection or assignment. Whole-state snapshots, revisions, or other equivalent mechanisms are implementation choices, not mandated storage formats.

Each operation must define its atomic unit, including any inseparable structured resolution and associated event. Validation or persistence failure must not expose a partially applied unit as committed truth. Caller-visible state and durable state must agree on success; uncertain persistence outcomes must be reported explicitly and reconciled before retry. Concurrency and crash guarantees must be stated rather than inferred from the use of a save function.

Separate commitments remain separate unless an explicit contract combines them. Failure of a later disposition transition or presentation step must not roll back, erase, or reinterpret an already committed episode. Multi-step workflows must expose which units committed and which failed.

Retry and reuse behavior must be explicit. Stable resolution identity must prevent duplicate events and rerolling of committed outcomes; conflicting recommitments must fail closed. Loading or looking up history must not silently retry failed follow-up operations. Automatic retries require a declared policy that preserves freshness, identity, and prior truth; there is no general requirement for durable retry machinery.

## 6. Subtractive Simulation

Mushin operates by constraining possibility.

Established facts and rules remove incompatible outcomes from the possibility space.

Probability operates only over permitted candidates.

Observation may resolve previously uncommitted possibilities, but cannot contradict established canon.

Unobserved details need not be generated prematurely.

Committed consequences may exist before their detailed narrative explanation, provided sufficient causal constraints are preserved to prevent retroactive contradictions.

Causal correctness constrains dependencies and permissible history; it does not require inventing a narrative cause for every state change. A simulation policy may use committed information to authorize a state transition without asserting that information as its psychological or narrative cause. Later details may resolve only still-open information consistent with canon; a causal explanation requires its own explicit authorization and, when it establishes world truth, commitment.

An offscreen event can resolve and commit consequences without the player's knowledge. Observation can subsequently reveal those consequences or resolve remaining details.

Mushin primarily models continuity and authorized state changes rather than exhaustive predefined object descriptions. An entity can retain identity without an object-specific code class or complete property definition. Undefined properties remain unresolved until legitimately established; an established property unknown to an observer is a different condition. Prematurely establishing unnecessary properties removes possibilities and can force avoidable contradictions or retcons.

General action and eligibility rules should permit unforeseen interactions without requiring object-specific methods for every action. A chair may move between rooms without a `Chair` class; a player may propose carving a name into a table without a predefined carve-name method. Both changes still require independent authorization. LLM semantic understanding may propose plausible actions, objects, and consequences, but plausibility alone never authorizes them. Current Lite action allowlists are implementation limits, not the target's conceptual limit.

Every committed change preserves the arrow of time and constrains subsequent events. A simulation turn is an ordered slice of an evolving canonical timeline; a general clock is a separate capability. This principle does not implicitly advance the explicit NPC decision windows described in §8.

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

Committed history and constraints must survive removal of the module that produced their proposals. Absence must not erase, reroll, or silently reinterpret that history. If remaining components cannot safely interpret persisted extension data, preserve it and explicitly reject affected operations until a compatible reader or authorized migration is available; unaffected baseline operation must remain coherent. Module removal is not a world reset.

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

### Subjective Interpretation and NPC DNA

Subjective interpretation is fundamental to Lite. Observers may interpret the same committed event differently; one interaction can legitimately leave one NPC angry and another hurt. Objective canon and individual perspectives remain distinct. Archetypes supply low-resolution subjective and behavioral weighting without requiring Behavior. Full attempts higher-resolution individual interpretation and behavior. These are architectural responsibilities, not claims that current episode outcomes or disposition transitions already implement observer perspectives.

The intended Full configuration separates stable **NPC DNA**, defined in YAML, from mutable NPC state and accumulated experience maintained in JSON. Full uses a shared neutral human reference configuration; individual DNA defines deviations from that common baseline. Global baseline adjustments affect the shared mechanism, while individual deltas customize particular NPCs. DNA should rarely change during ordinary simulation. Configuration changes must not reinterpret already committed history or perspectives.

The **individual lens** is produced from the shared baseline, DNA deltas, current state, and history. It refines behavioral possibilities and weights without canonical authority. Its primitives, configuration schema, update rules, and refinement authorization remain future implementation work. Do not substitute a new high-order personality-stat system for this low-order-primitives objective. Lite's existing fixture dispositions are a bounded baseline, not an implementation of NPC DNA or Full's individual lens.

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

The baseline must have a declared activation path independent of player inquiry and of the optional high-resolution Behavior module. A host request, explicit simulation step, or event-driven activation may supply that path; this contract does not mandate clocks, continuous ticks, background execution, or exact offstage location tracking. Activation requests computation, not an assertion that an event occurred, and must still pass the ordinary resolution and commitment boundaries.

Where supported by the installed simulation capabilities, NPCs may initiate interactions with one another and produce persistent consequences outside the player's immediate awareness.

Objective consequences may become canonical before their detailed narrative explanation is generated.

Any later explanation must remain consistent with established history and constraints.

### Lite Host Activation Boundary

`npc_activation.activate_npc_episode(state, episode_id, rng=None)` is external orchestration of one explicitly installed episode. The caller supplies the existing canonical state dictionary (including `facts`, `next_fact_id`, and the NPC namespace), an installed episode ID, and optionally an RNG exposing `random()`. The existing collapse RNG and canon persistence configuration are used otherwise. Importing this module must not load saves, install fixtures, start a CLI, render output, or invoke an LLM.

A request authorizes computation only. Activation must not create episode definitions, select a new episode on its own, or write canonical state directly. Existing evaluation, sampling, and canon authorization/persistence operations retain their responsibilities. Player presence, inquiry, observation, rendering, and LLM availability are not prerequisites.

The returned diagnostic dictionary retains episode ID, feasibility, outcome, sampling/reuse flags, reasons, and `committed`, but excludes the proposal basis. `activation_status` is `committed`, `reused`, or `failed`, describing the episode operation only. A failed commitment can retain a proposed `outcome` for diagnostics; that value is not established truth. Missing/invalid NPC or episode data fails closed through existing validation. Callers must supply the canonical storage envelope; this boundary does not repair corrupt saves. Existing `ValueError`/`OSError` commitment failures are reported in `error`; unexpected dependency exceptions propagate without automatic retry or success substitution.

Only a new successful episode commitment dispatches disposition policies, in registered order and against the latest state after each preceding operation. Ordered `transitions` diagnostics report individual results and errors. A transition failure leaves the episode and earlier successful transitions committed; later independent policies still run. Episode success is not a claim that all follow-ups succeeded. No initiator refinement is implicitly requested.

Repeated activation reuses established episode truth without resampling or replaying transitions, including previously failed transitions. A caller may explicitly retry an uncommitted episode after a known safe failure; it may sample again. Uncertain persistence outcomes require reconciliation before retry. Follow-up recovery remains an explicit separate operation. There is no automatic retry queue.

This boundary supports serialized, single-threaded calls with a current caller-owned state. It adds no concurrent-writer coordination, durable revision check, scheduler, or stronger crash guarantees. Remaining transition/refinement canon-to-evaluator coupling is an implementation gap, not permission to bypass independent authorization.

Explicit episode activation remains distinct from the bounded opportunity-selection path below. Neither implements a scheduler or optional higher-resolution Behavior refinement. Episode outcome evaluation does not select episodes or assert individual intentions.

### Lite Baseline Interaction Archetype

The first baseline is `interaction_v1`, explicitly bound by each participating entity's canonical `archetype` field. Its version-1 configuration is declared in the fixture configuration, not inferred at evaluation time. Setup supplies bindings; loading an older save must not silently assign them. Unresolved episodes with missing/unknown bindings or invalid configuration fail closed. Existing resolved history remains reusable without the provider or its configuration.

This policy reuses canonical `sociability`, `irritability`, installed episode participants/windows/allowed places, and committed prior outcomes. It creates no parallel personality or relationship state. For compatible constraints the weights are: `no_interaction = 1`, `conversation = 2.5 + sum(sociability)`, and `disagreement = 1 + sum(irritability) + applicable prior-disagreement bias`. The bias is one when an explicitly earlier resolved episode of the same pair was a disagreement, independent of record count. Disjoint exhaustive allowed places permit only `no_interaction`; absent constraints are unresolved, never proof of non-interaction.

Baseline evaluation is pure: it produces a weighted-possibility envelope (`version: 1`, `archetype: interaction_v1`) with episode identity, feasibility, reasons, canonical state basis, and policy-configuration basis. It must not sample, write state, persist, or invoke another processing stage. Shared constraint/policy validators may inspect inputs without producing decisions. Core authorization validates both the proposed distribution and selected outcome against current state and the declared policy without importing or calling the provider. Retain every prior episode rejection rule, including disposition/history validation, positive permitted weights, sampling flags, metadata, and freshness.

External orchestration checks for existing history, invokes baseline evaluation, routes its envelope to resolution, and submits a selected proposal to canon. Resolution consumes explicit possibilities and does not invoke the provider. The legacy `collapse_npc_episode` entry point remains a compatibility composition wrapper; the new resolver is a distinct function. Future optional refinement belongs between evaluation and resolution under a separately declared authorization contract. No refinement is installed here; the baseline path is complete without it. Unsupported or forged transformations fail explicitly rather than being accepted as refinements.

The legitimate `no_interaction` outcome establishes only that the named pair did not interact during the installed episode. It does not establish idleness, refusal, motive, or whereabouts. Unresolved/error results commit nothing. A proposal is not an event; only canon commits the outcome and event together. Proposal bases include current NPC state and the versioned policy configuration; stale state/configuration invalidates new writes. Existing keyed outcomes survive provider removal, are never rerolled, and do not replay failed transitions. Persistence, partial-success reporting, explicit retry, and single-threaded limits remain those of the host activation contract.

### Lite Bounded Opportunity Decisions

`activate_npc_opportunity(state, npc_id, rng=None)` is a host-only composer. The host chooses an NPC, never the winning episode. It reads an explicitly established canonical decision window, reuses a stored decision if present, otherwise evaluates opportunities, resolves one choice, independently commits that decision, then invokes `activate_npc_episode` only for a newly committed selection. No player inquiry, observation, renderer, LLM, or optional high-resolution Behavior is required. Importing or evaluating must not load, install, or advance state.

The optional NPC storage extension is `opportunities = {version: 1, current_window: <id>, windows: {<id>: [start, end]}, decisions: {<window_id>: {<npc_id>: <record>}}}`. All window bounds are exact integers with start < end and half-open overlap semantics. `establish_npc_decision_window` is an explicit canon operation: it may initialize the extension or append a new, nonoverlapping window at or after the previous end; the current window must be the latest. Repeating the current ID with identical bounds is a no-op. IDs/bounds cannot be reused, changed, reopened, or moved backwards. Every established window has a decision map, even when empty. The fixture explicitly installs the morning window. Missing extension data is unsupported for opportunity activation, never initialized by load or evaluation. No clock, scheduler, automatic advancement, or new episode creation is implied.

A version-1 record contains exactly `version`, `npc_id`, `window_id`, `window`, `policy`, `choice`, `episode_id`, and `episode`. `policy` identifies `initiation_v1`; `choice` is `no_initiation` or `episode`. An abstention has null episode fields. A selection stores the episode ID and a detached full episode-definition snapshot (participants, window, permissions, and display metadata). Window bounds are also copied into the record. History and participant claims are interpreted from these snapshots, not from mutable catalogue definitions or a provider. Reading/reusing records does not require current dispositions, policy configuration, or episode definitions. Unsupported/corrupt history fails explicitly and is not repaired or erased.

Installed episodes are the sole catalogue. Fresh decisions validate the whole catalogue and all resolutions before selecting: valid distinct participants, dispositions, explicit interaction archetype bindings, metadata, increasing windows, and nonempty permissions are required. Duplicate definitions for the same unordered pair and window are invalid, regardless of IDs. Eligible episodes contain the deciding NPC, exactly match the current decision window, permit a shared place, and are unresolved and unclaimed. Existing selections claim both participants throughout their frozen window, even if episode activation failed or ultimately resolved to `no_interaction`. Overlapping claims block other opportunities; overlapping already-resolved episodes also block selection. These are conservative opportunity-path decision-capacity restrictions, not claims of physical occupancy. The pre-existing explicit episode API retains its separate authorization semantics. Alternatives may overlap before selection. Malformed data is failure, not proof of abstention. Present `current_room` is not evidence of historical presence or a requirement for this interval-based policy; no travel, schedule, relationship preference, or motive is inferred.

`initiation_v1` is separate from unchanged `interaction_v1`. Its explicit configuration supports that archetype and assigns `no_initiation` weight 1 and total initiation weight `1 + deciding NPC sociability`, divided equally among eligible episodes in sorted ID order. The no-initiation candidate is first; episode candidates use a distinct kind and ID, avoiding sentinel collisions. With zero eligible episodes, abstention is deterministic and consumes no random draw. Otherwise resolution consumes one valid draw in [0, 1). Pure evaluation produces a versioned envelope with NPC/window identity, candidates, reasons, whole-NPC basis, and both initiation and interaction policy bases. Shared validators independently check eligibility and weighting; no validator asks the producer to authorize its own result. Optional future refinements need separately declared authorization; no such module is implemented here.

A committed `no_initiation` consumes this NPC's decision for the window, creates no event, and does not establish episode-wide `no_interaction`, idleness, unwillingness to respond, or a motive. It does not claim another participant: the NPC may still be a counterpart in another selection. Selection establishes only a decision to activate the named opportunity, not a conversation, disagreement, or disagreement-initiator role. Episode evaluation and commitment retain their independent authority and existing outcome weights.

Decision commitment and episode commitment are separate atomic units, each persisting before caller-memory mutation. Fresh decision authorization checks the current state/configuration, complete candidates, sampling flag, and selected candidate. Recommitment reuses an identical record and rejects a conflicting choice. The composer checks the committed snapshot against the live episode before handoff and obtains a fresh episode proposal after the decision write. No opportunity stage writes canon directly.

Host results include `decision_status` (`committed`, `reused`, or `failed`), the committed `decision` when available, and `episode_status` (`not_requested`, `activated`, `failed`, or `recovery_required`). Episode/transition diagnostics remain nested and internal. A successful decision followed by an episode exception or failure is reported as partial success; the decision/claim persists. Subsequent calls never resample or reactivate that selection. For a stored selection without an outcome, report `recovery_required`. Explicit recovery requires a host to reconcile persistence, validate the record with `validate_opportunity_handoff`, then deliberately call the existing episode API for that exact episode; no recovery endpoint or retry queue is added. Changed/removed episode definitions or newly conflicting resolved episodes block recovery. Existing episode outcomes and failed follow-ups are never replayed. A safe pre-write failure permits an explicit fresh attempt; uncertain persistence requires reconciliation. No multi-operation transaction or concurrent-writer guarantee is claimed.

This boundary remains single-threaded and host-only. It creates no player-facing disclosure permission. NPC episode events still enter the shared facts list consumed by presentation/model paths; the audience-filtering gap remains unresolved. Do not attach this API to the player loop or claim player-safe offscreen simulation until that boundary is implemented. Optional high-resolution Behavior, general autonomous scheduling, and world time remain future work.

### Lite Bounded Decision-Window Processing

`npc_window.process_npc_decision_window(state, expected_window_id, npc_ids, rng=None)` is import-safe, host-only external orchestration within an already established window. The host owns and retains a finite explicit list or tuple of canonical NPC IDs and supplies the expected current window identity. IDs are exact, not normalized. Duplicate, malformed, unknown, or unauthorized identities reject the whole request before evaluation, sampling, or writes. An empty roster is a valid no-op. Validate the canonical storage envelope and opportunity history, all roster memberships, and shared opportunity authorization inputs for every undecided member before processing. Stored decisions require valid history and current NPC membership, not the original provider or policy configuration. Preflight does not produce or cache possibilities and is not commitment authority.

Process the copied roster in ascending canonical-ID order, invoking `activate_npc_opportunity` sequentially against fresh canonical state. Earlier claims and disposition changes affect later evaluations. The host chooses who receives a decision opportunity, never the episode or outcome. Existing per-NPC/window records, including abstentions, are the only durable progress mechanism; no canonical batch counter, roster, or random-stream checkpoint is added. The host must retain and resupply its roster across interruption; a different roster is a new explicit request. Equivalent inputs and supplied randomness determine order/results, but exact random-stream continuation after a crash is not promised.

Version-1 results contain `status` (`rejected`, `stopped`, or `completed`), `window_id`, `requested_npc_ids` in supplied order (null for a malformed container), `processing_order`, `processed_npc_ids` (including the attempted failing member), `unprocessed_npc_ids`, and ordered `results`. Each member retains existing opportunity/episode/transition diagnostics and adds `followup_status`: `not_requested`, `completed`, `failed`, or `unknown`. `decisions_complete` states whether every requested member has a committed decision in the expected window, including members not attempted in this call; it is null for a rejected request. `processing_complete` is true only when every member was processed without a reported failure. Neither flag asserts completion of the whole world or all historical follow-ups. An episode diagnostic's uncommitted proposed outcome is not canonical truth.

Stop before the next NPC on a failed/unauthorized decision, persistence error, recovery-required selection, episode failure, dependency exception, or reported transition failure. An unresolved transition, error, or proposed transition without successful commitment is a failure; an authorized `no_change` is successful. Preserve all prior commitments, including a decision whose episode failed and an episode whose transition failed. Existing transition dispatch still finishes its ordered policies before returning diagnostics; stopping the roster does not change that internal behavior. Decision, episode, and transition commitments remain separate, with existing provider-independent decision/episode authorization and persistence-before-memory guarantees. The composer never writes canon directly.

Repeated calls reuse committed decisions without resampling or replay. A stored selection without an outcome stops with recovery required; recovery remains an explicit reconciled handoff and episode activation, separate from processing. Safe pre-write failures allow a later explicit attempt for undecided members; uncertain persistence must first be reconciled. Failed transitions never automatically replay. Historical transition diagnostics are not durably stored: reused episodes report `unknown` follow-up completion. Unknown history alone does not stop a new explicit processing request, and a completed call with unknown history does not certify historical transition success. Hosts must retain diagnostics if they need to track/reconcile those failures.

Window establishment, advancement, and retirement remain separate explicit canon operations. Processing never creates or advances a window, closes it, invents opportunities or facts, or attaches to ordinary player actions, inquiry, observation, or rendering. Advancing to a successor retires the old window from fresh decisions; it does not certify roster completion or repair failures. No separate close operation is added. This slice remains single-threaded with current caller-owned state, without concurrent writers, a scheduler, a clock, optional high-resolution Behavior, or stronger crash guarantees. Audience filtering remains unresolved: host diagnostics and canonical offscreen events are not automatically authorized player knowledge.

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

Cartridges define worlds, scenarios, and their particular constraints without owning the engine's internal authority. The house test world is intended to evolve into a standalone whodunnit cartridge. The lucid dream is the intended first public experience, with variable surrealism influencing eligible possibilities and probability weighting within canonical constraints. The neighborhood is the long-term Lite sandbox target. These are project plans and examples, not implemented cartridges or hardcoded engine dependencies.

Mushin remains headless by design. Renderers and external applications may be replaced without changing established canonical outcomes. An outside application may use Mushin as a contained decision-making environment and submit inputs through declared interfaces, but cannot directly mutate its canon.

## 10. Module Lifecycle and Compatibility

Every module contract must define:

- Accepted input and produced output
- Transformation responsibility
- Permitted and forbidden effects
- Required capabilities and dependencies
- Pipeline insertion requirements
- Absence and fallback behavior
- Failure handling, effects already committed, and any retry/reuse policy
- Freshness dependencies and atomicity guarantees for authorized writes
- Persisted-data ownership and behavior after module removal
- Audience/disclosure restrictions where output leaves an authority boundary
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

### Native Vocabulary

Preserve Mushin's native vocabulary in architecture documents, code identifiers, and public documentation. Do not silently substitute conventional software or game-development terms, or add jargon where an existing Mushin term accurately describes the concept. Terminology changes that alter conceptual boundaries require explicit architectural approval; this documentation does not authorize identifier renames.

| Native term | Contract usage |
| --- | --- |
| Canon | Authoritative established simulation reality. |
| Observation collapse | Authorized resolution of previously unresolved possibilities through observation. |
| Truth packet | Objective committed-event output, subject to audience authorization. |
| Observer packet / Subjective packet | An applicable observer's established perspective, distinct from objective event truth. |
| NPC DNA | Stable individual configuration; intended YAML definition. |
| Individual lens | Interpretation/refinement from shared baseline, DNA deltas, state, and history. |
| Archetype | Lite's baseline subjective and behavioral mechanism. |
| Cartridge | A world/scenario and its particular constraints, without engine write authority. |
| Evidence gravity | Retained native term; its precise operational contract is not specified here. Do not invent a weighting algorithm or silently rename it. |
| Prose Conditioner | Authorized packet-to-prose transformation without canonical authority. |

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