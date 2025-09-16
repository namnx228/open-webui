# VoiceMode Integration Plan for Open WebUI

Date: 2025-09-15

This document details how to plug Open WebUI’s existing Voice Mode UI into the LiveKit-based "voicemode" backend that lives in this repo.

## Overview
- Goal: Use LiveKit (browser WebRTC) for mic publish and assistant audio playback, driven by the existing `voicemode` agent (OpenAI Realtime) while keeping Open WebUI’s current Classic (STT/TTS) voice path as a fallback.
- Scope: Minimal changes to Open WebUI UI/UX. Add a backend proxy for LiveKit token minting and wire a LiveKit branch into `CallOverlay.svelte`.

## Codebase Findings (ground truth)
- voicemode
  - Agent: `voicemode/agent.py` (LiveKit Agents SDK + OpenAI Realtime, server-VAD, voice="coral").
  - Token server: `voicemode/token_server.py` (FastAPI) returns `{ token, url }` for LiveKit room join.
  - Web client example: `voicemode/web/*` (Next.js) joins LiveKit and renders assistant audio via `@livekit/components-react`.
- Open WebUI (Svelte)
  - Voice overlay: `open-webui/src/lib/components/chat/MessageInput/CallOverlay.svelte` (records mic, sends to STT; plays TTS or browser Kokoro).
  - Call button: `open-webui/src/lib/components/chat/MessageInput.svelte` (toggles `showCallOverlay`).
  - Settings toggles: `open-webui/src/lib/components/chat/Settings/Interface.svelte` (voice interruption, emoji in call, etc.).
  - Backend audio APIs: `open-webui/backend/open_webui/routers/audio.py`.
  - No LiveKit code yet; no route to mint LiveKit tokens.

## Architecture Decision
- Primary: LiveKit end-to-end for calls inside the Call Overlay.
- Fallback: Keep Classic Voice (current STT→LLM→TTS path) when LiveKit is disabled or fails.
- Token issuance: via Open WebUI backend proxy → `voicemode/token_server.py` (or direct signing later).

## Backend Changes (Open WebUI)
1) Config/env (add to `open-webui/backend/open_webui/env.py`)
   - `VOICEMODE_ENABLED` (bool)
   - `VOICEMODE_TOKEN_SERVER_URL` (string), e.g. `http://localhost:8000/api/livekit/token`
   - `LIVEKIT_URL` (string), e.g. `ws://localhost:7880` (informational/default)

2) Router (new: `open-webui/backend/open_webui/routers/voicemode.py`)
   - `POST /api/voicemode/token` → forwards `{ identity, room }` to `VOICEMODE_TOKEN_SERVER_URL` using `requests` with Open WebUI auth guard.
   - Response passthrough: `{ token, url }`.

3) Wire router
   - `open-webui/backend/open_webui/main.py` → `include_router(voicemode_router)`.

## Frontend Changes (Open WebUI)
1) Client API helper (new: `open-webui/src/lib/apis/voicemode.ts`)
   - `getLiveKitToken(authToken, identity, room): Promise<{ token: string; url: string }>` → calls `/api/voicemode/token`.

2) Settings UI (edit: `open-webui/src/lib/components/chat/Settings/Interface.svelte`)
   - New select: "Voice Backend" = `classic` | `voicemode`.
   - Optional fields: Room name (default `voice-chat`), Identity (default: username/email), "Auto-join on click".
   - Persist via `saveSettings()` like existing toggles.

3) Call Overlay integration (edit: `open-webui/src/lib/components/chat/MessageInput/CallOverlay.svelte`)
   - Branch by `settings.voiceBackend` and `config.voicemode.enabled`:
     - On overlay mount: fetch token via `getLiveKitToken()`, lazy import `livekit-client`, create `new Room()`, `room.connect(url, token)`, publish mic track (`echoCancellation`, `noiseSuppression`, `autoGainControl` from settings).
     - Subscribe to remote audio (assistant): attach to hidden `<audio>` and `play()`.
     - Map controls:
       - Interrupt: pause remote audio; (Phase 2) send a LiveKit data message to agent.
       - Mute/unmute: `localParticipant.setMicrophoneEnabled(boolean)`.
       - End call: `room.disconnect()` and teardown.
   - Fallback: if LiveKit disabled or connection fails → use existing Classic flow.

4) Call button guard (edit: `open-webui/src/lib/components/chat/MessageInput.svelte`)
   - If `voiceBackend==='voicemode'` but backend disabled, toast a config error.

## Optional Phase 2 — Transcripts & Memory
Two paths for streaming transcripts and responses back to chat UI:
1) LiveKit Data messages
   - Agent (`voicemode/agent.py`): publish JSON events on partial/final transcript and LLM responses.
   - WebUI overlay: `room.on(RoomEvent.DataReceived, ...)` → display captions, and optionally append messages to chat via `submitPrompt({ _raw: true, source: 'voicemode' })`.

2) HTTP callback
   - New backend endpoint `POST /api/voicemode/events` → Open WebUI writes to history (`langgraph_memory.db`, `conversations/*.json`).
   - Agent posts turn events with a `session_id` correlation.

## Security & Ops
- Keep LiveKit API key/secret server-side only; browser gets only short-lived tokens.
- Tighten CORS on `voicemode/token_server.py` in prod (no `*`).
- Token TTL ≤ 120s for session bootstrap.
- TURN/STUN configured in `voicemode/livekit.yaml` for NAT traversal.
- TLS termination for `wss:` and `https:` only in production.

## Testing & Fallbacks
- Browsers: Chrome, Edge, Firefox, Safari.
- Scenarios: connect, publish mic, receive assistant audio, mute/unmute, end call.
- Failure: LiveKit down → overlay shows error; automatically fall back to Classic voice if allowed by settings.
- Latency targets: mic → assistant onset < 1s on LAN; add basic console timings now, metrics later.

## Rollout Plan
Phase 1 (connectivity)
- Backend proxy route and envs.
- Frontend LiveKit branch in overlay; successful join/publish/subscribe; fallback intact.

Phase 2 (transcripts & memory)
- Stream partial/final transcripts to UI and persist to history.
- Post-call summarization appended to conversation metadata.

Phase 3 (hardening)
- Security knobs (CORS, TTL, origin checks), device selection, push-to-talk parity, monitoring.

## Open Questions
1) Token minting: keep separate `voicemode/token_server.py` or sign inside Open WebUI backend?
2) Transcripts: prefer LiveKit data channel or HTTP callback for persistence?
3) Identity/room conventions: mapping to Open WebUI users and multi-tenant rooms?
4) TURN provisioning: self-hosted coturn vs managed; credentials rotation cadence?

## Environment Variables
- `VOICEMODE_ENABLED` (Open WebUI backend)
- `VOICEMODE_TOKEN_SERVER_URL`
- `LIVEKIT_URL` (informational/default)
- (voicemode) `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`

## API Contracts
Browser → Open WebUI
- `POST /api/voicemode/token`
  - Body: `{ identity: string, room: string }`
  - Resp: `{ token: string, url: string }`

Open WebUI → Token Server (`voicemode/token_server.py`)
- `POST /api/livekit/token`
  - Body: `{ identity: string, room: string }`
  - Resp: `{ token: string, url: string }`

## Task Checklist
- [ ] Backend: envs in `env.py`
- [ ] Backend: router `routers/voicemode.py`
- [ ] Backend: wire router in `main.py`
- [ ] Frontend: `lib/apis/voicemode.ts`
- [ ] Frontend: Settings UI additions
- [ ] Frontend: LiveKit branch in `CallOverlay.svelte`
- [ ] Frontend: guard in `MessageInput.svelte`
- [ ] Phase 2: transcript stream + persistence
- [ ] Security: CORS, TTL, TURN, TLS
- [ ] Tests: cross-browser, latency smoke, fallback paths

