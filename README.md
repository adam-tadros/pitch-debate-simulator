# Pitch Debate Simulator

A multi-agent CLI tool to stress-tests a pitch or presentation by simulating a panel Q&A. 
## How It Works

```
┌─────────────────────────────────────────────────────┐
│                   YOUR INPUTS                        │
│   pitch.txt  +  personas.json                        │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────▼──────────────┐
         │  PHASE 1: QUESTION       │  Each persona independently surfaces
         │  SURFACING (2 rounds)    │  their top concerns about the pitch.
         │                          │  Round 2: they see each other's questions
         └───────────┬──────────────┘  and fill in uncovered angles.
                     │
         ┌───────────▼──────────────┐
         │  PHASE 2: DEBATE         │  Pitch agent gives an opening statement.
         │  (6 rounds back+forth)   │  Personas rotate asking follow-up questions.
         │                          │  Pitch agent responds to each in turn.
         └───────────┬──────────────┘
                     │
         ┌───────────▼──────────────┐
         │  PHASE 3: SYNTHESIS      │  An analyst agent reads the full transcript
         │                          │  and surfaces: strongest points, key objections,
         │                          │  blind spots, and what to fix.
         └──────────────────────────┘
```

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/pitch-debate-simulator
cd pitch-debate-simulator
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_key_here"
```

## Quick Start

```bash
python pitch_simulator.py \
  --pitch examples/example_pitch.txt \
  --personas examples/example_personas.json
```

## Usage

```
python pitch_simulator.py --pitch PITCH --personas PERSONAS [options]

Required:
  --pitch PITCH           Path to pitch text file, or the pitch text itself
  --personas PERSONAS     Path to personas JSON file, or a JSON string

Options:
  --model MODEL           Anthropic model (default: claude-opus-4-8)
  --question-rounds N     Question surfacing rounds before debate (default: 2)
  --debate-rounds N       Back-and-forth debate rounds (default: 6)
  --output FILE           Save full transcript + synthesis as JSON
  --quiet                 Suppress console output (use with --output)
  --help                  Show this message
```

### Examples

```bash
# Use a cheaper/faster model
python pitch_simulator.py \
  --pitch pitch.txt --personas personas.json \
  --model claude-sonnet-4-6

# Shorter session (4 debate rounds, save output)
python pitch_simulator.py \
  --pitch pitch.txt --personas personas.json \
  --debate-rounds 4 --output results.json

# Pipe pitch text directly
python pitch_simulator.py \
  --pitch "We're building X to solve Y for Z..." \
  --personas personas.json

# Batch/headless mode
python pitch_simulator.py \
  --pitch pitch.txt --personas personas.json \
  --output results.json --quiet
```

## Persona Format

Personas are defined as a JSON array. Only `name` is required; all other fields enrich the simulation.

```json
[
  {
    "name": "Sarah Kim",
    "role": "Partner at a Series A VC fund focused on enterprise software",
    "background": "Former CTO, 10 years investing in B2B SaaS. Has seen 500+ pitches.",
    "concerns": "Skeptical of TAM claims. Wants to see evidence of repeatable sales motion.",
    "priorities": "Capital efficiency, clear ICP, path to $10M ARR.",
    "style": "Direct and numerical. Asks for specific numbers, not ranges."
  },
  {
    "name": "Marcus Webb",
    "role": "Potential enterprise customer (VP of Operations at a mid-size company)",
    "background": "Has evaluated and rejected 8 SaaS tools in the last 2 years.",
    "concerns": "Integration complexity, switching costs, ROI timeline.",
    "priorities": "Easy adoption, measurable outcome within 90 days.",
    "style": "Pragmatic. Cuts through features to ask 'what does this change for my team?'"
  }
]
```

### Persona Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Display name |
| `role` | — | Job title / context (strongly recommended) |
| `background` | — | What they know, what they've seen |
| `concerns` | — | Their specific worries going in |
| `priorities` | — | What they most need to hear |
| `style` | — | How they communicate (skeptical, enthusiastic, quantitative…) |

The richer the persona definition, the more distinct and realistic the simulation.

## Output

When run with `--output results.json`, the file contains:

```json
{
  "metadata": {
    "model": "claude-opus-4-8",
    "question_rounds": 2,
    "debate_rounds": 6,
    "personas": ["Sarah Kim", "Marcus Webb"],
    "timestamp": "2026-06-13T..."
  },
  "transcript": [
    {
      "phase": "question_surfacing",
      "round": 1,
      "speaker": "Sarah Kim",
      "role": "persona",
      "content": "...",
      "timestamp": "..."
    },
    ...
  ],
  "synthesis": "## STRONGEST POINTS\n..."
}
```

## Prompting Tips

**Pitch file:** Write your pitch the way you'd actually present it. The more specific it is (with real numbers, claims, and positioning), the more targeted the questions will be. Vague pitches produce vague questions.

**Personas:** The most impactful field is `concerns` — tell the persona what they're worried about *going in*. A VC who's "skeptical of the distribution strategy" will probe very differently than one who's "excited but worried about technical feasibility."

**Number of personas:** 2–4 works best. With one persona, the debate becomes monotonous. With five or more, each persona gets fewer turns and the synthesis becomes harder to read.

**Debate rounds:** 6 (default) gives each persona ~2 turns in a 3-persona panel. Increase to 8-10 for a more thorough grilling.

## Architecture

The simulator uses three agent types:

- **Pitch Agent** — Has the full pitch in its system prompt. Answers all questions.
- **Persona Agents** — One per evaluator. Each has distinct background, concerns, and style baked into their system prompt. They do not share context with each other between turns (simulating independent thinking).
- **Synthesis Agent** — Reads the full transcript at the end. Produces structured analysis.

All agents use the same model but different system prompts. The orchestrator (the `PitchDebateSimulator` class) manages turn order and passes relevant context windows to each agent.

## License

MIT
