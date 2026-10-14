# Journeys

Each file is one guided programme, loaded by `lumina.journey.catalog`. A guided session works on
one step: the step's `goal` and `guidance` go into the system prompt, and the LLM fits the wording
to the person. `opener` is how Lumina introduces the step at the start of a session.

- `themes` are the pain-point macros (`lumina/nlp/lexicons/pain_points.py`, `MACRO_MAP`). The planner
  uses them to recommend a journey that fits what the person has been talking about.
- `order` breaks ties when two journeys fit equally well.
- Keep steps small enough for one conversation. Steps never ask about self-harm, and they are never
  used on a crisis turn.
