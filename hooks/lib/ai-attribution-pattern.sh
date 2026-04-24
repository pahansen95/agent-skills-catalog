# Single source of truth for the AI-ownership-claim regex.
# Sourced by hooks/commit-msg and hooks/pre-push.
#
# Matches (case-insensitive ERE):
#   - Co-Authored-By: trailers naming AI vendors or AI noreply addresses.
#   - "Generated with/by <vendor>" watermarks.
#   - "🤖 Generated" watermarks.
#
# Add new patterns here; both hooks pick them up automatically.

export AI_ATTRIBUTION_PATTERN='(co-authored-by:.*(claude|gpt|anthropic|openai|copilot|cursor|gemini|noreply@anthropic|noreply@openai))|(generated[[:space:]]+(with|by)[[:space:]]+(claude|gpt|cursor|copilot|anthropic|openai))|(🤖[[:space:]]*generated)'
