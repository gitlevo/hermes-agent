# mooxi patches on Hermes Agent v0.23.0

Branch `mooxi/v0.23.x` = upstream tag `v0.23.0` "Hearth" (`2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`) plus the
commits below, one per patch. `mooxi/v0.23.0-base` is the bare tag, so a diff against it shows only these.
mooxi's brain image (`mooxi-brain`, built in gitlevo/mooxi `infra/mind/brain/`) overlays exactly the files
listed here onto the official `nousresearch/hermes-agent:v0.23.0` image.

Carried from `mooxi/v0.22.7` (gitlevo/mooxi#268): every patch was cherry-picked onto v0.23.0 without a
conflict. Before carrying each one, v0.23.0 was read for an upstream fix of the same thing: none has landed
(the upstream PRs below are still open, and v0.23.0 still has the exact-substring check, no forward filter,
no hub switch, no YOLO lock and no batch split for one-call templates). So all of them stay; none is new.

## 1. Forwarded Telegram messages are never acted on

`plugins/platforms/telegram/adapter.py`. A forwarded message is someone else's words; the allowed user only
pressed "forward". The text, command, location and media handlers drop any forward right after the
authorization check, before an event is built or a group transcript observed: Bot API 7.0 `forward_origin`
(matched by its `MessageOrigin*` type name), the pre-7.0 `forward_*` fields (which PTB keeps in
`api_kwargs`), and `is_automatic_forward`. In a private chat the sender gets one line saying why; in a
group the forward is dropped silently. Always on in this branch (no switch).

Test: `tests/gateway/test_telegram_forwarded_refusal.py`.

## 2. `approvals.allow_yolo` (default `true`, upstream behaviour)

`tools/approval_context.py`, `tools/approval.py`, `tools/approval_yolo.py`, `gateway/slash_commands.py`,
`hermes_cli/config_defaults.py`. With `allow_yolo: false`:

- `--yolo` / `HERMES_YOLO_MODE` is voided where it is frozen at import (every direct reader sees it off),
  and the bypass checks re-read the switch live;
- `/yolo` (gateway, CLI, TUI: they share `toggle_session_yolo`) never turns a bypass on, clears a stored ON,
  and the gateway answers "YOLO is turned off on this machine";
- a restored, launch-seeded or earlier-enabled session bypass reads as off.

`approvals.mode: off` is a separate, explicit config choice and is not affected; hardline blocks and deny
rules are unchanged. Test: `tests/tools/test_approval_allow_yolo.py`.

## 3. `skills.hub_enabled` (default `true`, upstream behaviour)

`tools/skills_hub_search.py`, `hermes_cli/config_defaults.py`. Every hub search, install, update and check
(CLI, TUI, dashboard, the `manage_catalog` chat tool) builds its sources with `create_source_router`. With
`hub_enabled: false` it returns no source, so nothing can arrive from the official index, skills.sh, a URL,
GitHub taps, ClawHub, LobeHub or browse.sh. The switch is read live. Skills already on disk and the agent's own
`skill_manage` (behind `skills.write_approval`) are unaffected. Test: `tests/tools/test_skills_hub_enabled.py`.

## 4. `agent.single_tool_call_models` (default `[]`, upstream behaviour)

`agent/transports/chat_completions.py`, `hermes_cli/config_defaults.py`. gpt-oss's chat template (Harmony)
renders at most one tool call per assistant turn and names each tool result after "the most recent assistant
tool call"; Azure AI Foundry's gpt-oss deployments reject a history in which one assistant message carries
several calls with HTTP 400 "Message has tool role, but there was no previous assistant message with a tool
call!". A primary model that made parallel calls (DeepSeek) therefore made every fallback to gpt-oss fail on
its first request, and the turn was lost (gitlevo/mooxi#70). The pre-call sanitizer does not help: the
history is valid OpenAI Chat Completions, every call is answered.

With model-name markers listed (e.g. `["gpt-oss"]`), `ChatCompletionsTransport.convert_messages` gives a
matching model a wire copy in which each parallel batch becomes one assistant message per call, each followed
by its own result (alias-aware matching; the first keeps the content and reasoning). It runs on every attempt,
fallbacks included, since each attempt rebuilds its kwargs through the transport. Stored history is never
rewritten. The switch is read live. Test: `tests/agent/transports/test_chat_completions_single_tool_call_models.py`
(a replay of the failed request's shape).

## 5. CVE status

| CVE | Where | Status in v0.23.0 | What this branch does |
|---|---|---|---|
| CVE-2026-9353 | `THREAT_PATTERNS` in the skills guard (advisory names `agent/skills_guard.py`; in v0.22.5 it is `tools/skills_guard.py`) | **Fixed upstream.** `sys_prompt_override` is `system\s+(?:\w+\s+)*prompt\s+(?:\w+\s+)*override` and `fake_policy` is `new\s+(?:\w+\s+)*policy…`, so the advisory's extra-word bypass ("system prompt temporary override") matches. | A regression test pins it. |
| CVE-2026-10220 | `skill_view` / `_serve_plugin_skill` (`tools/skills_tool.py`; in v0.22.5 the shared code is in `tools/skills_tool_plugin.py`) | **Not fixed.** Both paths still test `any(p in content.lower() for p in _INJECTION_PATTERNS)`: exact substrings, so "ignore ALL prior instructions" or extra spaces bypass it. | `_has_injection_pattern()`: the same phrases as word- and whitespace-tolerant regexes, plus every `injection`-category pattern of the skills guard; both call sites use it. |

Sources: NVD entries for both CVEs and the reporter's advisories linked from them
(gist.github.com/YLChen-007/82a3539d6358842e69dfaef0a9fcf14a, …/9dd399c6f75b31fa741a613dfd41de08).

As upstream, the `skill_view` check **warns** (a log line) and does not block: a regex list can never
catch every phrasing. mooxi's real controls are elsewhere: skills need write approval
(`skills.write_approval: true`), and no marketplace installs at runtime (`skills.hub_enabled: false`).
Test: `tests/tools/test_skills_injection_cve_2026_10220.py` (the advisory's payloads, plus harmless text
that must stay quiet).

## Tests run

v0.23.0 (2026-11-06, mooxi-01, arm64, as mooxiadmin in a throwaway container): inside the official v0.23.0 image's
own venv (Python 3.14.9), with pytest 9.1.1, pytest-asyncio 1.4.0 and their closure installed by the hashes in this
tag's `uv.lock`. The patches' own tests: 51 passed. The existing suites for the touched code
(`tests/gateway/test_telegram_*.py`, `test_slash*`, the approval, yolo, skills and chat-completions transport suites):
with the patches 1847 passed, 32 failed, 3 skipped; on the bare tag 1795 passed, 33 failed, 3 skipped. The 32 are the
same tests in both (missing test extras in the image); the 33rd on the bare tag is a timing test of the ClawHub source
(`test_enrich_owners_budget_stops_early_and_keeps_partial_results`) that passed in the patched run.
gitlevo/mooxi's Hermes contract tests (`infra/ci/hermes-contract.sh`) pass on v0.23.0, with and without this overlay.

Earlier: v0.22.7 (2026-11-04) the same way: 51 passed; 1704 passed, 32 failed, 3 skipped with and without the patches.

## Upstream status (2026-11-06: all still open, none in v0.23.0)

Each patch is meant to go away once upstream covers it (see gitlevo/mooxi `infra/mind/brain/README.md`).

| Patch | Upstream | Drop when |
|---|---|---|
| 1. Forwarded Telegram messages | PR NousResearch/hermes-agent#146953: opt-in `platforms.telegram.extra.ignore_forwarded_messages` | it merges; mooxi then sets the switch |
| 2. `approvals.allow_yolo` | issue #131038 (tied to the settings-lock PR #106869) asks for the same | that lands |
| 3. `skills.hub_enabled` | PR #81273: `skills.hub.source_policy` (an allowlist; empty = every source off) | it merges; mooxi then sets an empty allowlist |
| 4. `agent.single_tool_call_models` | not covered upstream (no issue or PR for gpt-oss and parallel tool calls in history as of 2026-11-02); to be offered | upstream splits batches for one-call templates; mooxi then drops the switch |
| CVE-2026-10220 | PR NousResearch/hermes-agent#146952 (public under SECURITY.md §3.2; the CVE is on NVD) | it merges |
