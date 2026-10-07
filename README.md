# Codewalk Agent

An interactive repository understanding agent that helps developers analyze GitHub repositories, understand project structure, and ask questions about the codebase.

## Objective

The Codewalk Agent allows developers to provide a public GitHub repository and understand its structure, technologies, modules, execution flow, and relevant source code through an interactive interface.

## Features

- Public GitHub repository URL input
- Repository analysis
- Project purpose detection
- File structure visualization
- Main module identification
- Technology detection
- Execution flow overview
- Developer question input
- Relevant file identification
- Relevant source code display
- Error handling for invalid repositories

## User Flow

GitHub Repository URL

↓

Analyze Repository

↓

Repository Overview

↓

Ask Question

↓

Answer

↓

Relevant Code

## Technology Stack

- Python
- Gradio
- GitHub REST API
- LangChain
- Gemini

## Project Structure

```text
codewalk-agent/
│
├── app.py
├── requirements.txt
└── README.md
