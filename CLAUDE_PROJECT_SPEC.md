# CLAUDE_PROJECT_SPEC.md

# AI Circuit Architect

### Multi-Agent Hardware Architecture Assistant for KiCad

### Qwen Cloud Hackathon 2026

---

# 1. Executive Summary

## Vision

AI Circuit Architect is a multi-agent AI assistant that helps electronics engineers transform natural-language hardware requirements into a structured KiCad project scaffold.

The system intentionally **does not attempt to replace an experienced hardware engineer**.

Instead it automates the repetitive early engineering work:

* Requirement analysis
* Architecture creation
* Hierarchical project structure
* Dummy schematic generation
* Engineering TODO generation
* Design assumptions
* Validation
* Documentation

The generated project serves as a high-quality engineering starting point that can later be completed by a human designer inside KiCad.

---

# Elevator Pitch

> AI Circuit Architect is the "Cursor for Hardware Architecture".

Instead of producing a finished schematic, it creates an engineering-grade project scaffold that saves hours of repetitive setup work while keeping the engineer fully in control.

---

# Philosophy

Human engineers make engineering decisions.

AI prepares engineering work.

The AI must never pretend certainty where uncertainty exists.

Whenever confidence is insufficient, the output shall contain

* TODO
* NEEDS HUMAN REVIEW
* ASSUMPTION

instead of fabricated information.

---

# 2. Hackathon Goals

This project is designed specifically for the Qwen Cloud Hackathon.

It demonstrates

* Multi-Agent Collaboration
* Tool Usage
* Engineering Artifact Generation
* Human-in-the-loop Workflow
* Cloud Deployment
* Production-like Software Architecture

The project intentionally solves a real engineering problem instead of being another chatbot.

---

# 3. Product Scope

## Included

✓ Natural language requirements

✓ Requirement clarification

✓ Architecture generation

✓ Hierarchical KiCad project

✓ Placeholder components

✓ Net labels

✓ Power domains

✓ Engineering assumptions

✓ Engineering TODOs

✓ Validation

✓ ZIP export

✓ Agent trace

---

## Explicitly NOT Included

No PCB layout

No routing

No resistor values

No capacitor sizing

No ERC correctness

No BOM optimization

No simulation

No manufacturing release

No "one click finished schematic"

---

# 4. Product Workflow

User

↓

Requirements Agent

↓

System Architect

↓

Design Critic

↓

Arbitration

↓

Human Approval

↓

KiCad Scaffold Generation

↓

Validation

↓

ZIP Download

---

# 5. Human in the Loop

This is a core principle.

No KiCad project shall be generated before the user explicitly approves the architecture.

The engineer remains responsible.

AI assists.

---

# 6. Multi-Agent Architecture

The application shall contain the following logical agents.

---

## Requirements Agent

Role

Senior Systems Engineer

Purpose

Transform ambiguous user input into structured engineering requirements.

Responsibilities

* detect ambiguity

* identify missing information

* propose assumptions

* generate clarification questions

* normalize terminology

Never invent missing requirements.

Output JSON

{
requirements

constraints

questions

assumptions

confidence
}

---

## System Architect Agent

Role

Principal Hardware Architect

Purpose

Create the hardware architecture.

Responsibilities

* identify functional blocks

* identify hierarchical sheets

* identify interfaces

* identify power domains

* identify major signals

* recommend placeholder components

Never generate resistor values.

Never select final ICs unless explicitly requested.

Output JSON

{
blocks

interfaces

signals

power

placeholder_components

notes
}

---

## Design Critic Agent

Role

Senior Hardware Reviewer

Purpose

Critically inspect the proposed architecture.

Responsibilities

Search for

* missing protection

* missing debug

* missing testability

* missing interfaces

* missing power blocks

* missing documentation

The critic never redesigns.

The critic reviews.

Output

{
warnings

risks

missing_blocks

recommendations
}

---

## Arbitration Agent

Role

Chief Engineer

Purpose

Resolve conflicts between Architect and Critic.

Responsibilities

Produce

Approved Architecture

Remaining TODOs

Human Review Items

Output

{
approved_architecture

todo

human_review

accepted_assumptions
}

---

## KiCad Scaffold Agent

Role

CAD Engineer

Purpose

Generate project structure.

Responsibilities

Generate

.kicad_pro

main schematic

hierarchical sheets

placeholder blocks

README

TODO

Architecture Report

Assumptions

Agent Trace

Validation Template

---

## Validation Agent

Role

Quality Engineer

Purpose

Verify internal consistency.

Checks

Sheets exist

Project complete

Important nets exist

Power rails exist

Placeholder components marked

README exists

TODO exists

Architecture exists

Validation report exists

No production-ready claims

---

# 7. Agent Communication Rules

Very important.

Agents NEVER communicate directly.

Architecture

User

↓

Orchestrator

↓

Agent

↓

JSON

↓

Orchestrator

↓

Next Agent

Only the orchestrator owns state.

Every agent is stateless.

This keeps the system deterministic and easy to debug.

---

# 8. System Prompts

Each agent shall contain an explicit System Prompt.

Example

"You are a senior hardware architect.

You never fabricate electronics knowledge.

You never invent component specifications.

When uncertain, create TODO entries.

Prefer modular architectures.

Prefer hierarchical schematics.

Output valid JSON only."

Each agent shall have its own personality and objective.

---

# 9. JSON Contracts

Markdown shall never be exchanged internally.

Only JSON.

Example

Requirements

{
...

}

Architecture

{
...

}

Critic

{
...

}

Validation

{
...

}

Markdown is generated only for the final reports.

---

# 10. KiCad Generation Strategy

Important.

Do NOT synthesize KiCad files from scratch.

Instead

Create template files.

Store them under

/templates

Generate new projects by filling the templates.

Use minimal valid KiCad v9 S-expression templates.

The scaffold only needs to be sufficient to open in KiCad and represent the project hierarchy.

---

# 11. Project Outputs

Generated ZIP

project.kicad_pro

project.kicad_sch

sheets/

power.kicad_sch

mcu.kicad_sch

usb_service.kicad_sch

rs485.kicad_sch

sensor_io.kicad_sch

debug.kicad_sch

architecture.md

todo.md

validation_report.md

assumptions.md

agent_trace.json

README.md

---

# 12. Placeholder Components

Examples

DUMMY_MCU

DUMMY_USB_C

DUMMY_RS485

DUMMY_POWER_STAGE

DUMMY_ESD

DUMMY_CLOCK

DUMMY_DEBUG

These are intentional placeholders.

---

# 13. Important Net Labels

VIN_24V

+5V

+3V3

GND

USB_D+

USB_D-

USB_VBUS

RS485_A

RS485_B

I2C_SCL

I2C_SDA

SWDIO

SWCLK

NRST

STATUS_LED1

STATUS_LED2

---

# 14. Technology Stack

Backend

Python

FastAPI

Pydantic

httpx

Jinja2

Frontend

HTML

CSS

Alpine.js (CDN)

Backend API

REST

Container

Docker

Cloud

Alibaba Cloud

LLM

Qwen Cloud API

---

# 15. Mock Mode

The application must always work.

If

QWEN_API_KEY

is missing

switch automatically into Mock Mode.

The demo shall still function.

---

# 16. Repository Structure

app/

agents/

models/

templates/

generators/

services/

api/

static/

tests/

outputs/

README.md

Dockerfile

docker-compose.yml

requirements.txt

.env.example

LICENSE

---

# 17. Development Rules

Claude shall NOT generate the entire project at once.

Instead implement incremental milestones.

Milestone 1

Repository

Docker

FastAPI

Mock UI

Verify

STOP

Milestone 2

Requirements Agent

Verify

STOP

Milestone 3

Architecture Agent

Verify

STOP

Milestone 4

Critic

Verify

STOP

Milestone 5

Orchestrator

Verify

STOP

Milestone 6

KiCad Generator

Verify

STOP

Milestone 7

Validation

Verify

STOP

Milestone 8

ZIP Export

Verify

STOP

Milestone 9

Deployment

Verify

STOP

Each milestone must compile before continuing.

---

# 18. Definition of Done

The MVP is complete when

✓ User enters requirements

✓ Agents execute

✓ Architecture generated

✓ User approves

✓ KiCad scaffold generated

✓ Validation passes

✓ ZIP downloadable

✓ Docker builds

✓ Mock Mode works

✓ Qwen Mode works

✓ Alibaba deployment documented

---

# 19. Future Roadmap

Version 2

Real KiCad CLI validation

ERC

PDF Export

Real library symbols

Version 3

Review completed schematics

EMC Review

Power Review

Cost Review

DFM Review

Component suggestions

Version 4

PCB generation assistant

Constraint generation

Layout hints

---

# 20. Hackathon Judging Strategy

The demo should emphasize

Problem

↓

Agent collaboration

↓

Human approval

↓

Engineering artifact

↓

Validation

↓

Download

Avoid describing the project as an AI chatbot.

Describe it as

"A multi-agent engineering copilot."

---

# 21. Instructions for Claude Code

You are not only writing code.

You are designing a maintainable engineering product.

Prioritize

* readability
* modularity
* deterministic outputs
* testability
* robustness

Never fabricate electronics knowledge.

Never fabricate KiCad syntax.

Never fabricate component specifications.

When uncertain

produce

TODO

or

NEEDS HUMAN REVIEW

instead.

The repository should be of sufficient quality that it could continue as an open-source project after the hackathon.

End every milestone with a short engineering summary explaining what was implemented, how it was verified, and what remains for the next milestone.
