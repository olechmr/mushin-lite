# Mushin Lite — Architecture Gap Register

**Status:** Draft for review
**Companion:** `ARCHITECTURE.md` (target architecture, proposed v0.1)
**Purpose:** Record observed differences between the target architecture and Mushin Lite, without redefining the target.

## Interpretation and change control

- **The architecture contract is authoritative.** This register describes implementation status; it does not weaken or replace any invariant.
- **A gap is not automatically a defect or an instruction to refactor.** Lite is a limited reference implementation, and target features may be intentionally deferred.
- **Documentation is not implementation authorization.** No code changes, new dependencies, or architectural migrations are approved by this register.
- Entries marked **Observed** are supported by the inspected `master` source files. **Partial** means some relevant mechanisms exist but full conformity has not been demonstrated. **Not demonstrated** means the review did not establish that a mechanism exists; it does not prove absence. **Future target** means explicitly planned capability, not a failure of the prototype.
- This initial register is based on read-only inspection of `README.md`, `main.py`, `behavior.py`, `collapse.py`, `canon.py`, `renderer.py`, `world.py`, `packet_interpreter.py`, `rules.py`, `llm_adapter.py`, and `npc_fixture.py` during the contract drafting session. It is **not** an exhaustive call-graph, test, or runtime audit. Recheck the repository revision before using an observation to authorize engineering work.

## Gap register

| ID | Target contract area | Lite evidence and observed difference | Assessment | Follow-up verification (not an instruction to implement) |
| --- | --- | --- | --- | --- |
| G-01 | §2, §4 — independently composed stages | `main.py` directly imports and coordinates interpretation, rule application, commitment, presentation, and NPC episode processing. The intended external pipeline composer and generic stage contracts are not demonstrated. | **Partial** | Map current call paths and identify actual stage boundaries, including distinct player, observation, and NPC paths. |
| G-02 | §2, §4 — stage-to-stage isolation | `collapse.py` directly imports `evaluate_episode` and `OUTCOMES` from `behavior.py`. This couples named processing implementations instead of routing only through a declared stage boundary. | **Observed gap** | Inventory other processing-stage imports and distinguish them from shared schema or infrastructure imports. |
| G-03 | §3 — independent engine/conditioner/renderer | `renderer.py` imports functions from `world.py` and `collapse.py`, and imports `map_data`. The current terminal-facing presentation code is not fully independent of simulation internals. | **Observed gap** | Identify a structured engine-output envelope that can be consumed without direct state-module access; distinguish renderer, formatter, and prose-conditioning functions. |
| G-04 | §3 — structured external handoff | The README describes simulation separate from narration; `main.py` also assembles presentation contexts and invokes renderer/narration functions. A versioned, presentation-independent external output schema was not established in this review. | **Partial / not demonstrated** | Trace what fields downstream consumers require and what distinguishes committed results, unresolved information, presentation material, and diagnostics. |
| G-05 | §4 — arbitrary compatible insertion boundaries | Current NPC and observation flows contain function-specific wiring; no general registration/composition mechanism for inserting an unknown future transformation at a compatible boundary was demonstrated. | **Not demonstrated** | Look for an existing dispatcher, stage registry, typed packet interface, or composition API before designing one. |
| G-06 | §7–§8 — archetype-driven NPC baseline independent of optional Behavior | `behavior.py` currently evaluates fixed NPC episodes using dispositions and history; the inspected `npc_fixture.py` defines a small controlled fixture. A general archetype baseline capable of initiating NPC actions without high-resolution Behavior was not demonstrated. | **Future target / not demonstrated** | Define the minimal baseline behavior contract, then verify it can operate with optional Behavior absent. |
| G-07 | §7–§8 — one decision path, enhancement before probability | `behavior.py` evaluates episode outcome weights; `collapse.py` samples from those results. This separates some responsibilities, but uses direct implementation coupling rather than a general optional refinement boundary. | **Partial** | Test that archetype-only and Behavior-enhanced paths would feed one canonical candidate/weight contract without duplicate decisions. |
| G-08 | §5–§6 — committed state is authoritative | `canon.py` contains explicit NPC commitment operations, stale-basis checking, proposal re-evaluation, and persistence handling. `behavior.py` evaluates possibilities without directly sampling or persisting. This is meaningful evidence of the intended authority separation in the NPC prototype, not proof that all action paths comply. | **Partially demonstrated conformity** | Audit every state mutation and verify proposal/validation/commit boundaries, especially observations and map updates. |
| G-09 | §6, §8 — offscreen consequences and deferred explanation | The NPC fixture supports episode evaluation/resolution and stores an objective outcome independently of the rendered inquiry. General autonomous offscreen initiation and later, causally constrained narrative detail remain target capabilities rather than demonstrated full systems. | **Partial / future target** | Distinguish objective event commitment, discovery/knowledge, and deferred narrative resolution in an eventual interface contract. |
| G-10 | §7, §10 — explicit absence and failure semantics | Some local fallbacks and fail-closed checks exist. A uniform module-level distinction between intentionally absent, incompatible, and runtime-failed components was not demonstrated. | **Not demonstrated** | Document actual failure handling at each boundary and which states can safely invoke a baseline or pass-through. |
| G-11 | §9 — world-, genre-, and host-agnostic core | README states this intention. Current Lite includes specific rooms, objects, and NPC fixtures, and `main.py` knows some fixture-specific commands. These are acceptable in a demonstration but require clear separation from reusable engine interfaces in the target. | **Partial** | Classify code as engine, cartridge/fixture, adapter, or host, without assuming that every demo-specific function is a violation. |
| G-12 | §10–§12 — versioned module contracts and conformance checks | No complete, independent set of stage/module input-output specifications or architecture conformance tests was established by this limited inspection. | **Not demonstrated** | Inventory current schemas and tests; prioritize contract tests only after the relevant interfaces are defined and approved. |

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

## Maintenance procedure

When an architectural decision is approved:

1. Update `ARCHITECTURE.md` to express the target requirement.
2. Reassess any affected gap entry here; mark observations with the repository revision or tests used when available.
3. Keep **observed behavior**, **inference**, **future target**, and **open question** distinct.
4. Do not modify code merely to make this register look complete.
5. Treat implementation proposals, test plans, and commits as separately authorized work.

**Initial review conclusion:** Mushin Lite exhibits important foundations for canonical-state authority and bounded NPC evaluation, but the target's general-purpose stage isolation, module composition, application-level decoupling, and archetype fallback are not yet established by the inspected implementation.
