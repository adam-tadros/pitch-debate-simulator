#!/usr/bin/env python3
"""
Pitch Debate Simulator
======================
A multi-agent tool that simulates a panel Q&A for a pitch or presentation.
Feed it your pitch materials and a set of evaluator personas — it runs
question-surfacing rounds, a back-and-forth debate, then synthesizes insights.

Usage:
    python pitch_simulator.py --pitch pitch.txt --personas personas.json
    python pitch_simulator.py --pitch pitch.txt --personas personas.json --output transcript.json
    python pitch_simulator.py --help

Requires: ANTHROPIC_API_KEY environment variable
"""

import anthropic
import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path


# ─── Formatting helpers ───────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
GREEN   = "\033[32m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
RED     = "\033[31m"

PERSONA_COLORS = [CYAN, YELLOW, MAGENTA, BLUE, RED]


def header(text: str, color: str = BOLD) -> None:
    width = 64
    print(f"\n{color}{'═' * width}{RESET}")
    print(f"{color}{text.center(width)}{RESET}")
    print(f"{color}{'═' * width}{RESET}\n")


def speaker_label(name: str, color: str = CYAN) -> str:
    return f"{BOLD}{color}[{name}]{RESET}"


def wrap_text(text: str, indent: int = 2) -> str:
    prefix = " " * indent
    paragraphs = text.split("\n")
    wrapped = []
    for p in paragraphs:
        if p.strip() == "":
            wrapped.append("")
        else:
            wrapped.append(textwrap.fill(
                p, width=80,
                initial_indent=prefix,
                subsequent_indent=prefix,
                break_long_words=False
            ))
    return "\n".join(wrapped)


def section(title: str) -> None:
    print(f"\n{DIM}{'─' * 64}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{DIM}{'─' * 64}{RESET}\n")


# ─── Agents ───────────────────────────────────────────────────────────────────

class PitchAgent:
    """Represents the person defending the pitch."""

    def __init__(self, client: anthropic.Anthropic, pitch: str, model: str):
        self.client = client
        self.pitch = pitch
        self.model = model
        self.system = (
            "You are the presenter defending this pitch or proposal:\n\n"
            f"{'━' * 48}\n{pitch}\n{'━' * 48}\n\n"
            "Rules:\n"
            "- Answer questions directly and specifically. Avoid vague platitudes.\n"
            "- Be confident but intellectually honest. Acknowledge real weaknesses when pressed.\n"
            "- Do NOT make up data or statistics you don't have.\n"
            "- If you don't know something, say so honestly.\n"
            "- Adapt your register to the questioner.\n"
            "- Keep answers focused."
        )

    def respond(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            system=self.system,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()


class PersonaAgent:
    """Represents one evaluator/panel member with their own perspective."""

    def __init__(self, client: anthropic.Anthropic, persona: dict,
                 model: str, color: str):
        self.client = client
        self.name = persona["name"]
        self.model = model
        self.color = color
        self.persona = persona

        role        = persona.get("role", "Evaluator")
        background  = persona.get("background", "")
        concerns    = persona.get("concerns", "General evaluation")
        style       = persona.get("style", "Professional and direct")
        priorities  = persona.get("priorities", "")

        self.system = (
            f"You are {self.name}, {role}.\n\n"
            f"BACKGROUND: {background}\n\n"
            f"YOUR CONCERNS GOING IN: {concerns}\n\n"
            f"YOUR PRIORITIES: {priorities}\n\n"
            f"YOUR STYLE: {style}\n\n"
            "Rules:\n"
            "- Stay in character. Ask the questions YOUR background would lead you to ask.\n"
            "- Be specific — reference actual claims from the pitch when challenging them.\n"
            "- Don't just be a cheerleader. Push where it matters.\n"
            "- Keep questions focused. One main question per turn.\n"
            "- If the pitcher gave a good answer to your last question, "
            "acknowledge it briefly before pivoting."
        )

    def ask(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=self.system,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()


# ─── Simulator ────────────────────────────────────────────────────────────────

class PitchDebateSimulator:
    """Orchestrates the full multi-agent pitch simulation."""

    def __init__(
        self,
        pitch: str,
        personas: list,
        model: str = "claude-opus-4-8",
        question_rounds: int = 2,
        debate_rounds: int = 6,
        verbose: bool = True,
    ):
        self.client = anthropic.Anthropic()
        self.pitch = pitch
        self.personas_cfg = personas
        self.model = model
        self.question_rounds = question_rounds
        self.debate_rounds = debate_rounds
        self.verbose = verbose
        self.transcript = []

        # Build agents
        self.pitch_agent = PitchAgent(self.client, pitch, model)
        self.persona_agents = [
            PersonaAgent(self.client, p, model, PERSONA_COLORS[i % len(PERSONA_COLORS)])
            for i, p in enumerate(personas)
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log(self, phase, round_num, speaker, role, content):
        self.transcript.append({
            "phase": phase,
            "round": round_num,
            "speaker": speaker,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _print(self, name, color, text):
        if self.verbose:
            print(speaker_label(name, color))
            print(wrap_text(text))
            print()

    # ── Phase 1: Question surfacing ───────────────────────────────────────────

    def phase_1_question_surfacing(self):
        header("PHASE 1  —  QUESTION SURFACING", CYAN)
        all_questions = {p.name: [] for p in self.persona_agents}

        for round_num in range(1, self.question_rounds + 1):
            section(f"Round {round_num} of {self.question_rounds}")

            for persona in self.persona_agents:
                if round_num == 1:
                    prompt = (
                        f"Here is the pitch you are evaluating:\n\n{self.pitch}\n\n"
                        "Based on your background and priorities, what are your top 3 questions "
                        "or concerns? Number them. Be specific — reference actual claims in the "
                        "pitch where possible."
                    )
                else:
                    others = "\n\n".join(
                        f"• {name} asked:\n{qs[round_num - 2]}"
                        for name, qs in all_questions.items()
                        if name != persona.name and len(qs) >= round_num - 1
                    )
                    prompt = (
                        f"You've seen these concerns from your colleagues:\n\n{others}\n\n"
                        "What additional questions do you have that haven't been raised yet? "
                        "Focus on angles from YOUR specific background. 2-3 questions."
                    )

                response = persona.ask(prompt)
                all_questions[persona.name].append(response)
                self._log("question_surfacing", round_num, persona.name, "persona", response)
                self._print(persona.name, persona.color, response)

        return all_questions

    # ── Phase 2: Debate ───────────────────────────────────────────────────────

    def phase_2_debate(self, initial_questions):
        header("PHASE 2  —  DEBATE", YELLOW)
        debate_history = []

        # Opening statement
        section("Opening Statement")
        compiled_qs = "\n\n".join(
            f"{name}:\n{qs[0]}"
            for name, qs in initial_questions.items()
            if qs
        )
        opening_prompt = (
            "The panel has reviewed your pitch and surfaced these initial questions:\n\n"
            f"{compiled_qs}\n\n"
            "Give a brief opening statement (2-3 paragraphs) addressing the most important "
            "underlying concern. Signal you're ready to take questions."
        )
        opening = self.pitch_agent.respond(opening_prompt)
        debate_history.append(f"PITCH AGENT: {opening}")
        self._log("debate", 0, "Pitch Agent", "pitcher", opening)
        self._print("Pitch Agent", GREEN, opening)

        # Debate rounds
        for round_num in range(1, self.debate_rounds + 1):
            persona = self.persona_agents[(round_num - 1) % len(self.persona_agents)]
            section(f"Round {round_num} of {self.debate_rounds}  —  {persona.name}")

            # Recent context (last 6 entries = 3 exchanges)
            recent = "\n\n".join(debate_history[-6:])

            # Persona questions / pushes back
            persona_prompt = (
                f"Recent exchange:\n\n{recent}\n\n"
                "It is your turn. Based on your concerns and what the pitch agent just said, "
                "ask your sharpest follow-up question or push back on something specific. "
                "Don't repeat what others have already asked well."
            )
            persona_response = persona.ask(persona_prompt)
            debate_history.append(f"{persona.name}: {persona_response}")
            self._log("debate", round_num, persona.name, "persona", persona_response)
            self._print(persona.name, persona.color, persona_response)

            # Pitch agent responds
            pitch_prompt = (
                f"Recent conversation:\n\n{recent}\n\n"
                f"{persona.name} just said:\n\n{persona_response}\n\n"
                "Respond directly and specifically to this."
            )
            pitch_response = self.pitch_agent.respond(pitch_prompt)
            debate_history.append(f"PITCH AGENT: {pitch_response}")
            self._log("debate", round_num, "Pitch Agent", "pitcher", pitch_response)
            self._print("Pitch Agent", GREEN, pitch_response)

    # ── Phase 3: Synthesis ────────────────────────────────────────────────────

    def phase_3_synthesis(self):
        header("PHASE 3  —  SYNTHESIS", MAGENTA)

        full_transcript = "\n\n".join(
            f"[{t['speaker']} | {t['phase'].upper()} round {t['round']}]\n{t['content']}"
            for t in self.transcript
        )
        persona_list = "\n".join(
            f"- {p['name']}: {p.get('role', '')}"
            for p in self.personas_cfg
        )

        synthesis_prompt = (
            "You observed a full pitch debate simulation.\n\n"
            f"EVALUATORS:\n{persona_list}\n\n"
            f"FULL TRANSCRIPT:\n{full_transcript}\n\n"
            "Provide a sharp, specific synthesis using this structure:\n\n"
            "## STRONGEST POINTS\n"
            "What arguments landed? Reference specific moments.\n\n"
            "## KEY OBJECTIONS  (ranked by severity)\n"
            "Group by theme. Quote or paraphrase specific challenges.\n\n"
            "## UNANSWERED / WEAKLY ANSWERED QUESTIONS\n"
            "What did the pitcher dodge, fumble, or fail to address adequately?\n\n"
            "## BLIND SPOTS\n"
            "What concerns weren't raised but should have been?\n\n"
            "## WHAT TO FIX BEFORE THE REAL PITCH\n"
            "Specific, actionable recommendations — not generic advice.\n\n"
            "## PERSONA VERDICTS\n"
            "One sentence per evaluator: how they likely feel leaving this room.\n\n"
            "Be concrete. Reference actual moments from the transcript. No filler."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=(
                "You are a sharp pitch coach and strategic advisor. "
                "You give direct, specific, actionable feedback. "
                "You don't soften bad news. You don't pad good news."
            ),
            messages=[{"role": "user", "content": synthesis_prompt}]
        )
        synthesis = response.content[0].text.strip()
        self._log("synthesis", 0, "Synthesis Agent", "analyst", synthesis)

        if self.verbose:
            print(synthesis)
            print()

        return synthesis

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        if self.verbose:
            header("PITCH DEBATE SIMULATOR", BOLD)
            print(f"  Model:            {self.model}")
            print(f"  Evaluators:       {', '.join(p.name for p in self.persona_agents)}")
            print(f"  Question rounds:  {self.question_rounds}")
            print(f"  Debate rounds:    {self.debate_rounds}")
            print()

        initial_questions = self.phase_1_question_surfacing()
        self.phase_2_debate(initial_questions)
        synthesis = self.phase_3_synthesis()

        return {
            "metadata": {
                "model": self.model,
                "question_rounds": self.question_rounds,
                "debate_rounds": self.debate_rounds,
                "personas": [p["name"] for p in self.personas_cfg],
                "timestamp": datetime.utcnow().isoformat()
            },
            "transcript": self.transcript,
            "synthesis": synthesis
        }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def load_pitch(path_or_text: str) -> str:
    p = Path(path_or_text)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return path_or_text.strip()


def load_personas(path_or_json: str) -> list:
    p = Path(path_or_json)
    if p.exists() and p.is_file():
        raw = p.read_text(encoding="utf-8")
    else:
        raw = path_or_json

    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "personas" in data:
        return data["personas"]
    raise ValueError("Personas must be a JSON array or {\"personas\": [...]}.")


def validate_personas(personas: list) -> None:
    for i, p in enumerate(personas):
        if "name" not in p:
            raise ValueError(f"Persona {i} is missing required field 'name'.")


def main():
    parser = argparse.ArgumentParser(
        prog="pitch_simulator",
        description=(
            "Multi-agent pitch debate simulator.\n\n"
            "Simulates a panel Q&A: personas surface questions over multiple rounds,\n"
            "debate the pitcher back-and-forth, then a synthesis agent extracts\n"
            "actionable insights."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Basic run with files
  python pitch_simulator.py --pitch pitch.txt --personas personas.json

  # Fewer rounds, different model
  python pitch_simulator.py --pitch pitch.txt --personas personas.json \\
      --debate-rounds 4 --model claude-sonnet-4-6

  # Save full transcript to JSON
  python pitch_simulator.py --pitch pitch.txt --personas personas.json \\
      --output results.json

  # Quiet mode (no console output, only saves JSON)
  python pitch_simulator.py --pitch pitch.txt --personas personas.json \\
      --output results.json --quiet
        """
    )

    parser.add_argument(
        "--pitch", required=True,
        help="Path to pitch/presentation text file, or the pitch text itself."
    )
    parser.add_argument(
        "--personas", required=True,
        help="Path to personas JSON file, or a JSON string."
    )
    parser.add_argument(
        "--model", default="claude-opus-4-8",
        help="Anthropic model to use (default: claude-opus-4-8)."
    )
    parser.add_argument(
        "--question-rounds", type=int, default=2,
        help="Number of question-surfacing rounds before the debate (default: 2)."
    )
    parser.add_argument(
        "--debate-rounds", type=int, default=6,
        help="Number of back-and-forth debate rounds (default: 6)."
    )
    parser.add_argument(
        "--output", default=None,
        help="Optional path to save full transcript + synthesis as JSON."
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress console output (useful with --output)."
    )

    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    try:
        pitch = load_pitch(args.pitch)
    except Exception as e:
        print(f"Error loading pitch: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        personas = load_personas(args.personas)
        validate_personas(personas)
    except Exception as e:
        print(f"Error loading personas: {e}", file=sys.stderr)
        sys.exit(1)

    if len(personas) < 1:
        print("Error: at least one persona is required.", file=sys.stderr)
        sys.exit(1)

    simulator = PitchDebateSimulator(
        pitch=pitch,
        personas=personas,
        model=args.model,
        question_rounds=args.question_rounds,
        debate_rounds=args.debate_rounds,
        verbose=not args.quiet,
    )

    try:
        results = simulator.run()
    except anthropic.APIError as e:
        print(f"\nAPI error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        if not args.quiet:
            print(f"\n{GREEN}✓ Full transcript saved to {output_path}{RESET}")


if __name__ == "__main__":
    main()
