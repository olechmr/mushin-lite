# Mushin Lite — Architecture Gap Register

**Status:** Draft for review
**Companion:** `ARCHITECTURE.md` (target architecture)
**Purpose:** Record observed differences between the target architecture and Mushin Lite, without redefining the target.

## Interpretation and change control

- **The architecture contract is authoritative.** This register describes implementation status; it does not weaken or replace any invariant.
- **A gap is not automatically a defect or an instruction to refactor.** Lite is a limited reference implementation, and target features may be intentionally deferred.
- **Documentation is not implementation authorization.** No code changes, new dependencies, or architectural migrations are approved by this register.
- Entries marked **Observed** are supported by the inspected `master` source files. **Partial** means some relevant mechanisms exist but full conformity has not been demonstrated. **Not demonstrated** means the review did not establish that a mechanism exists; it does not prove absence. **Future target** means explicitly planned capability, not a failure of the prototype.
- Evidence below was rechecked against `master` at `150cabbf5a08333e31691df8242c31be238af4b9` (`Fix disabled local conditioning fallback`). Source inspection covers the relevant functions in `main.py`, `behavior.py`, `collapse.py`, `canon.py`, `renderer.py`, `world.py`, `packet_interpreter.py`, `rules.py`, `llm_adapter.py`, `npc_fixture.py`, and `map_data.py`. This is not an exhaustive runtime, concurrency, crash-durability, or test audit. Recheck the revision before authorizing engineering work.
- **Contract clarifications** belong in `ARCHITECTURE.md`; **observed implementation deviations**, **unimplemented future architecture**, and **open design questions** are distinguished below. A demonstrated local safeguard does not establish system-wide conformity.

## Host activation slice provenance

This slice builds on `353f5f949b418d51ceb17b2bf1b08eeb352c2898`. The §8 host activation contract was recorded before production extraction. The bounded changes below concern orchestration and its tests; unchanged observations retain the earlier evidence revision. Host activation does not implement autonomous selection/initiation, archetypes, or optional high-resolution Behavior.

## Gap register

| ID | Target contract area | Lite evidence and observed difference | Assessment | Follow-up verification (not an instruction to implement) |
| --- | --- | --- | --- | --- |
| G-01 | §2, §4 — external composition | `npc_activation.activate_npc_episode` exposes import-safe single-episode host orchestration; `main.py::resolve_npc_episode` remains a compatibility wrapper. Observation and ordinary command paths still share CLI and presentation responsibilities. This bounded entry point is not a general composition system. | Partial / future architecture | Separate legitimate orchestration from transformations hidden in the host; map each actual boundary before proposing changes. |
| G-02 | §2, §4–§5 — stage isolation and independent authorization | `collapse.py::collapse_npc_episode` and `collapse_disagreement_initiator` call behavior evaluators. `canon.py::commit_npc_resolution`, `commit_npc_transition`, and `commit_disagreement_initiator` also import and call behavior evaluators to reauthorize proposals. The safeguards are useful but commitment depends on the producer implementation. Shared constants or pure schema validators are not equivalent to this processing dependency. | Observed deviation | Identify independently specified authorization checks without weakening recomputation, freshness, or forbidden-outcome checks. |
| G-03 | §3 — independent presentation components | `renderer.py::build_presentation_context` projects facts using `world.py` and reads `map_data`; `render_room` uses `collapse.is_observation_collapsed`; `narrate_state` imports the LLM adapter. Engine-output construction, formatting, and conditioning are not independently composed throughout. | Observed deviation | Distinguish those responsibilities before specifying an external handoff; do not classify every formatting helper as a separate stage. |
| G-04 | §3 — output and authorized disclosure | `main.py` supplies `committed_states` and turn-local `rule_block_text`; `handle_npc_inquiry` presents committed/reused outcomes. These are useful bounded handoffs. `renderer.py::build_presentation_context` also retains active facts in context, which `narrate_state` forwards to `llm_adapter.narrate_scene`. That function prompts against invention but returns model text without a semantic validation boundary. A versioned audience-filtered envelope is not demonstrated. | Partial / observed disclosure gap | Specify audience-authorized material separately from all canonical truth; define validation or safe fallback without granting narration authority. |
| G-05 | §2, §4 — compatible insertion boundaries | `main.py` wires normalization → reference resolution → eligibility → candidates → rules → commitment directly; NPC and observation paths have their own wiring. Candidate generation consumes the eligibility-approved packet without re-normalization. A general independently composable interface at these boundaries is not demonstrated. | Partial / future architecture | Preserve approved-packet authority when defining insertion contracts. A dynamic registry is one option, not a contract requirement; compatible host composition is sufficient. |
| G-06 | §7–§8 — baseline NPC activation | `behavior.py::evaluate_episode` evaluates fixture episodes using dispositions and history. `npc_activation.activate_npc_episode` permits explicit host calls without player presence or inquiry; CLI inquiries and `/npcresolve` delegate to it. Transition dispatch follows new episode commitment. There is no demonstrated archetype-only activation path with optional high-resolution Behavior absent. Developer-triggered offscreen resolution is not itself an autonomous baseline decision model. | Future target / not demonstrated | Define baseline inputs, outputs, and an inquiry-independent activation contract without presupposing clocks or continuous simulation. |
| G-07 | §7–§8 — coherent refinement path | Behavior evaluation supplies permitted weighted outcomes; `collapse.py` selects them. Ordered transition policies are evaluated and committed sequentially by `npc_activation.process_npc_transitions_for_episode`. This demonstrates bounded separation, not an interchangeable archetype/enhancement interface. | Partial / future architecture | Verify a single decision path with or without optional enhancement; retain fresh state for sequential proposals. |
| G-08 | §5 — freshness, atomicity, failure, and retry | NPC canon operations use whole-NPC basis checks and `_save_npc_commit` (temporary file, file fsync, replace) before updating caller memory; episode resolution and its event share a snapshot. In contrast, `canon.py::add_fact` supersedes/appends facts and advances the ID before `save_state` writes directly to the destination. Ordinary candidate loops and observation reveal/collapse-marker loops call `add_fact` separately. `map_data.py` persists exits separately in `map.json`; `rules.py` reads exits, but its `add_exit` import alone is not evidence of a rule-path map write. | Partial conformity / observed persistence deviation | Define each required atomic unit and audit failure effects. Do not claim concurrent-writer safety or full crash durability from atomic replacement alone; map ownership and cross-store consistency need explicit contracts. |
| G-09 | §6, §8 — deferred detail and causal independence | `canon.py::commit_npc_resolution` persists keyed objective truth plus an event. `commit_disagreement_initiator` adds a participant ID separately without another event. Disposition setters/transitions create no causal prose. These support bounded deferred detail; general autonomous initiation and causal-detail constraints are not implemented. | Partial / future architecture | Keep current availability, historical constraints, actor refinement, disposition, and audience knowledge distinct; no broader causal inference follows from this prototype. |
| G-10 | §7, §10 — absence and failure | Commit `150cabb` fixes the disabled-local-conditioning `UnboundLocalError` in `llm_adapter.py::get_local_conditioning`. Disabled conditioning returns `unknown / none`, intent `local conditioning disabled`, confidence `low`; runtime exceptions return the separate unavailable fallback. `chat` returns the packet into the ordinary pipeline. There is still no alternative ordinary-language interpreter on this path; direct deterministic commands remain available. Fail-closed rejection is not equivalent to replacing that interpretation capability. | Specific defect fixed / remaining capability limitation | Define which interpretation capability is baseline. Distinguish disabled, unavailable, malformed/recoverable, and incompatible results; the broad runtime exception fallback does not provide a uniform typed failure contract. |
| G-11 | §9 — engine, fixture, and host separation | `npc_fixture.py` holds fixed entities, episodes, policies, and inquiry bindings; `behavior.py` imports fixture policy/disposition definitions. `main.py` has fixture setup/refinement commands; `map_data.py` contains demo room and observation content. Demo content is legitimate, but reusable engine/cartridge boundaries are incomplete. | Partial / future architecture | Classify responsibility and data ownership before moving anything; no removal of fixture features is implied. |
| G-12 | §10–§12 — versioned contracts and conformance | The NPC storage envelope has version 1 and operation-specific validation; this is not a versioned set of processing-stage contracts. `test_npc_initiator.py` covers the bounded refinement; `test_npc_activation.py` covers host activation, import isolation, ordering, failures, reuse, and CLI compatibility. These are not a complete architecture conformance suite. | Not demonstrated | Inventory actual validation and tests separately from schema versions; define approved interfaces before proposing conformance work. |
| G-13 | §2, §4 — explicit rule results | `rules.py::apply_rules` returns candidates but also sets global `LAST_RULE` and `LAST_RULE_TYPE`. `main.py` uses those globals to capture block text and report results; adapter logging also reads rule state. The turn-local presentation fix avoids event-deduplication dependence, but the rule result still crosses a hidden mutable channel. | Observed deviation | Specify the full rule-result boundary while preserving existing precedence and exact block wording; no cleanup is authorized here. |
| G-14 | §5, §7, §10 — removal and follow-up lifecycle | `npc_activation.activate_npc_episode` dispatches transitions only after a new successful commitment. Per-policy failures are reported and later independent policies continue; reuse/load does not replay them. This preserves episode truth and permits explicit manual recovery. Removing behavior code is not a supported independent lifecycle: collapse and commitment still import it. A persisted extension-data retention/migration contract is not demonstrated. | Partial conformity / future lifecycle gap | Preserve the no-implicit-retry semantics and committed history; specify unsupported-data handling before optional-module removal is implemented. |

## Important distinctions

### The prototype `behavior.py` is not the complete proposed Behavior expansion

The current file is a bounded NPC episode and transition evaluator. The **Behavior module** described by the contract is a larger optional high-resolution system. Sharing a name must not be treated as evidence that the full architecture exists, or that the file must necessarily be discarded.

### Separation into files is not equivalent to airgapping

The target requires independently composable transformations with declared interfaces. A distinct Python module can still be coupled to another stage through imports, callbacks, or private state access. Conversely, shared non-processing schemas and approved infrastructure are permitted by the contract.

### A future target is not an immediate task

The goal of this document is architectural visibility. Decisions about sequence, implementation design, testing, and changes to code require separate review and authorization.

## Open questions for subsequent architecture work

1. What are the stable data envelopes between the engine and external consumers, and between major internal transformations?
2. How will orchestration expose compatible insertion points without exposing stage internals or making pipeline ordering arbitrary where causality forbids it?
3. Which capabilities are fundamental baseline responsibilities, and which are specialized cartridge/module features that can simply be absent?
4. How is the NPC archetype baseline represented, and how does optional Behavior refine it without producing a second independent resolution path?
5. What is the minimal distinction among committed events, unresolved possibilities, actor knowledge, disclosure, presentation data, and diagnostics?
6. What state and side effects are allowed for adapters, shared infrastructure, and orchestration code?
7. What are each operation’s freshness dependencies, atomic units, concurrency/crash guarantees, and explicit retry or reconciliation policies?
8. Which shared authorization contracts let commitment validate independently of proposal-producing implementations?
9. How are persisted extension data retained and interpreted when their optional module is absent?
10. Which audience/knowledge policy filters engine output, and how are invalid conditioned results detected or safely replaced?
11. What host or simulation-step interface activates baseline NPC decisions independently of player inquiry?

## Maintenance procedure

When an architectural decision is approved:

1. Update `ARCHITECTURE.md` to express the target requirement.
2. Reassess any affected gap entry here; mark observations with the repository revision or tests used when available.
3. Keep **observed behavior**, **inference**, **future target**, and **open question** distinct.
4. Do not modify code merely to make this register look complete.
5. Treat implementation proposals, test plans, and commits as separately authorized work.

**Review conclusion at `150cabb`:** Mushin Lite exhibits important foundations for canonical-state authority and bounded NPC evaluation, but the target's general-purpose stage isolation, module composition, application-level decoupling, and archetype fallback are not yet established by the inspected implementation.
