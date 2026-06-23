# Sample MIKU Trace

This trace demonstrates a full Study Mode run followed by music recovery.

## Trace 1: Start Study Mode

```json
{
  "timestamp": "2026-06-22T12:00:00",
  "raw_input": "start study mode",
  "input_type": "voice",
  "gesture": "one_finger",
  "transcript": "start study mode",
  "intent": "study_mode",
  "retrieved_context": {
    "preferred_music": null,
    "music_query": "lofi study music",
    "timer": "https://pomofocus.io",
    "notes": "https://docs.google.com/document/create",
    "checklist": "https://keep.google.com"
  },
  "plan": [
    "search YouTube for lofi study music",
    "open Pomofocus timer",
    "open notes",
    "open checklist"
  ],
  "tool_calls": [
    {
      "tool": "youtube_search_random_top3",
      "args": {"query": "lofi study music"},
      "result": "opened YouTube search results (fallback: top-3 selection simulated)"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://pomofocus.io"},
      "result": "opened https://pomofocus.io"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://docs.google.com/document/create"},
      "result": "opened https://docs.google.com/document/create"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://keep.google.com"},
      "result": "opened https://keep.google.com"
    }
  ],
  "observations": [
    "music attempted",
    "timer opened",
    "notes opened",
    "checklist opened"
  ],
  "recovery_steps": [],
  "response": "Okay! Starting Study Mode. I'll open your music, timer, notes, and checklist.",
  "errors": []
}
```

## Trace 2: Wrong Music Recovery

```json
{
  "timestamp": "2026-06-22T12:02:00",
  "raw_input": "jazz",
  "input_type": "voice",
  "gesture": null,
  "transcript": "jazz",
  "intent": "recovery_music_answer",
  "retrieved_context": {
    "preferred_music": null,
    "pending_music_recovery": true
  },
  "plan": [
    "search YouTube for jazz study music",
    "randomly pick one of top 3 results",
    "ask user if music is better",
    "save preferred_music if approved"
  ],
  "tool_calls": [
    {
      "tool": "youtube_search_random_top3",
      "args": {"query": "jazz study music"},
      "result": "opened YouTube search results (fallback: top-3 selection simulated)"
    }
  ],
  "observations": [
    "music recovery: searched for jazz study music"
  ],
  "recovery_steps": [
    "detected music complaint",
    "parsed desired genre: jazz",
    "searched YouTube for jazz study music"
  ],
  "response": "Got it. I'll search YouTube for jazz study music and try one. Is this better?",
  "errors": []
}
```
