# Mushin

**Mushin is a deterministic simulation engine for procedural narrative and emergent roleplay.**

The engine keeps authoritative world state in code, applies explicit rules to determine what can happen, and uses language models only where they are useful.

The model does not decide what is true.

State is truth.

Mushin began as an attempt to build a better dating sim and gradually turned into something much more general: a modular engine for worlds where characters, objects, relationships, events, and observations can change over time without requiring every outcome to be scripted in advance.

## What makes Mushin different?

A lot of AI-driven games ask a language model what happens next.

Mushin does not.

The engine separates simulation from narration.

World state is maintained by deterministic code. Rules determine whether actions are valid. Observation can collapse previously unresolved possibilities. NPC behavior can influence future probabilities. The language model can interpret player language or describe committed events, but it does not write directly to canon.

A basic principle of the engine is:

> Missing information is not permission to establish reality.

If the world does not know something yet, that uncertainty remains unresolved until something in the simulation is authorized to resolve it.

## Mushin Lite

Mushin Lite is the small reference implementation.

It is intentionally minimal and currently uses a terminal interface.

The goal is to demonstrate the architecture clearly rather than provide a finished graphical game.

Current systems include:

- authoritative persistent world state
- object interaction
- player movement
- observation and probability collapse
- inventories and object location
- rule-based action eligibility
- NPC state
- NPC dispositions
- episode evaluation
- NPC state transitions
- deterministic debugging and inspection tools
- optional local-model interpretation and narration

The included world is deliberately small so that engine behavior is easy to inspect.

## Example

A player might search a desk.

The engine does not ask a language model what is inside.

Instead, the desk contains an unresolved possibility space defined by the world. Searching it can collapse one of those possibilities according to its configured weights.

Once observed, that result becomes canon.

Later systems must respect it.

Likewise, if two NPCs have an argument, that committed event may alter their dispositions and influence the probability of future interactions.

The result is not a prewritten branching story.

It is a world accumulating history.

## Architecture

At a high level:

```text
player input
    ↓
interpretation
    ↓
normalization
    ↓
eligibility / rules
    ↓
candidate state changes
    ↓
canon commitment
    ↓
simulation state
    ↓
presentation
```

The language model may assist with interpretation or presentation, but the authoritative simulation remains outside the model.

Modules are intended to behave roughly as:

```text
input → rules → output
```

As long as a module can speak the engine's state format, it can potentially be added, replaced, or removed without redesigning the entire system.

## Current interface

Mushin Lite currently uses a terminal UI.

That is partly practical and partly intentional.

The TUI is the reference renderer, not the intended limit of the project.

If you want a proper GUI, web frontend, Unity integration, Godot client, graphical map, or something stranger:

**please build one.**

## Example commands

Ordinary interaction includes commands such as:

```text
look
search desk
take lantern
drop lantern
open book
close book
light lantern
north
south
ask heidi about chris
```

Developer commands expose the simulation underneath:

```text
/facts
/allfacts
/canon
/slots
/objects
/inspect
/world
/worldjson
/room
/packet
/trace
/traceclear
```

Additional development commands may exist depending on the current version.

## Philosophy

Mushin is built around a few principles:

- State is authoritative.
- Rules constrain possibility.
- Observation can resolve uncertainty.
- Committed facts remain committed.
- Models may interpret or narrate, but they do not write canon.
- Unknown does not mean permitted.
- Simulation should produce narrative rather than merely imitate it.

The engine is deliberately subtractive.

Instead of asking:

> What could happen?

Mushin increasingly asks:

> Given everything already known, what is still allowed to happen?

## Why "Mushin"?

*Mushin* (無心) is commonly translated as "no mind."

The name reflects the goal of keeping the central simulation independent from the language model's imagination.

The engine does not need to invent reality continuously.

It maintains reality, constrains it, and allows outcomes to emerge from the system.

## Project status

Mushin is experimental and under active development.

Mushin Lite is intended to become a small, playable demonstration of the engine's core architecture.

It is not intended to be the final form of Mushin.

Future directions may include:

- richer NPC behavior
- schedules and occupations
- relationships and social memory
- dynamic locations
- environmental systems
- larger procedural worlds
- additional renderers
- graphical interfaces
- developer tools
- entirely different games built on top of the engine

## Running Mushin

Clone the repository:

```bash
git clone https://github.com/olechmr/mushin-lite.git
cd mushin-lite
```

Follow the setup instructions for the current version and configure any optional local language model connection.

Mushin is developed primarily on Linux and has also been tested on Raspberry Pi hardware.

## For developers

Mushin is meant to be hacked on.

Fork it.

Replace the renderer.

Add a module.

Build another world.

Make a dating sim.

Make a murder mystery.

Make a shopkeeper who remembers everything you did three weeks ago.

Connect it to a graphical game.

Break it in an interesting way.

The architecture matters more to me than maintaining control over what everyone builds with it.

## License

Mushin is released under the MIT License.

Use it, modify it, fork it, redistribute it, and make something weird.

## Contributing

Bug reports, experiments, architectural criticism, ports, modules, renderers, and strange uses are welcome.

This is a hobby project, not a commercial product.

If one part of Mushin gives you an idea for something better, that counts as success.

---

Created by Matt Olech.
