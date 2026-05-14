# AURA Architecture (Voice-Only)

## Design Goal
AURA accepts spoken objectives, reasons over them, plans execution, performs safe actions, and responds only through voice.

## Agent Topology
- Supervisor Agent: orchestrates the full loop
- Planner Agent: decomposes goals and creates executable tasks
- Execution Agent: executes desktop/web/file actions
- Safety Agent: enforces risk checks and approval gates
- Memory Agent: persists user/project/action history
- Critic Behavior: on failure, planner replans alternative steps

## Voice-Only Loop
1. Listen for wake word and objective
2. Convert speech to text (Faster-Whisper)
3. Generate structured plan (LLM)
4. Announce top plan steps (TTS)
5. Execute low-risk steps automatically
6. Ask spoken confirmation for high-risk steps
7. Log outcomes and update memory
8. Replan on failure and continue

## Risk Policy
High-risk action categories require explicit spoken approval:
- send_email
- purchase_item
- delete_path
- publish_post

## Data Flow
- Input: microphone audio
- STT output: objective transcript
- Planner output: typed task list with risk tags
- Execution output: result objects and logs
- Memory output: user profile, projects, action history
- Output voice: ElevenLabs or local fallback

## Extensibility
- Add calendar/email/messaging adapters in Execution Agent
- Replace rule-based action parser with LLM tool selection
- Add app-specific desktop controllers (Outlook, Excel, etc.)
- Add realtime stream mode for continuous wake-word listening
- Add confidence scoring and critic quality checks
