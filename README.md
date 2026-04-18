# Axis AI Operating System

A personal AI operating ecosystem built with Python.

## What Axis Does

- Goal orchestration with governed execution states
- Multi-provider LLM: Groq, OpenRouter, 
  HuggingFace, Anthropic (10 models)
- Gmail and Google Calendar integration
- Device pairing and remote access via Tailscale
- Trust and permissions system (desktop-first)
- Supabase PostgreSQL cloud database
- Responsive dashboard — desktop, tablet, mobile
- Voice push-to-talk (browser-native)
- Animated premium dark UI with Three.js background
- 126 passing tests

## Tech Stack

- Backend: Python
- Database: Supabase (PostgreSQL)
- Frontend: Vanilla HTML/CSS/JavaScript + Three.js
- LLM: Groq (Llama 3.3), OpenRouter, 
  HuggingFace, Anthropic
- Auth: Token-based with device RBAC
- Hosting: Render

## Local Setup

1. Clone the repository
2. Copy .env.example to .env and fill in your keys
3. pip install -r requirements.txt
4. python -m jarvis_ai.mobile.server
5. Open http://127.0.0.1:8001/ui

Built by Prince — AI systems developer.
