# AI transcripts

This folder is the record of the AI interactions that produced the WhisperKey
submission. Per the challenge rules, the Trojan and exploit were generated with AI;
these logs are the evidence. A submission missing them may be disqualified.

- `transcript_whisperkey_raw.pdf` — **the raw chat transcript** (primary log): the
  actual prompts and AI responses, exported from the conversation. Non-project personal
  messages have been removed for privacy; **all AI prompts and responses related to
  WhisperKey are preserved.**
- `transcript_whisperkey.md` — an organized, stage-by-stage write-up of the same work
  (a guide to navigating the raw log).
- `ai_interaction_log.md` — a short summary of the workflow.

Model used: Claude (Anthropic), conversational session driving the scripted
insert/test pipeline (`../tools/pipeline.py`). No API keys or credentials are stored.
