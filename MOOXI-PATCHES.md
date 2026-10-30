# mooxi patches on Hermes Agent v0.22.5

Branch `mooxi/v0.22.5` = upstream tag `v0.22.5` (`bf0203a794a07aac3ff764972ab9087baa4e4f4e`) plus the
commits below, one per patch. `mooxi/v0.22.5-base` is the bare tag, so a diff against it shows only these.
mooxi's brain image (`mooxi-brain`, built in gitlevo/mooxi `infra/mind/brain/`) overlays exactly the files
listed here onto the official `nousresearch/hermes-agent:v0.22.5` image.

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

## 3. CVE status

| CVE | Where | Status in v0.22.5 | What this branch does |
|---|---|---|---|
| CVE-2026-9353 | `THREAT_PATTERNS` in the skills guard (advisory names `agent/skills_guard.py`; in v0.22.5 it is `tools/skills_guard.py`) | **Fixed upstream.** `sys_prompt_override` is `system\s+(?:\w+\s+)*prompt\s+(?:\w+\s+)*override` and `fake_policy` is `new\s+(?:\w+\s+)*policy…`, so the advisory's extra-word bypass ("system prompt temporary override") matches. | A regression test pins it. |
| CVE-2026-10220 | `skill_view` / `_serve_plugin_skill` (`tools/skills_tool.py`; in v0.22.5 the shared code is in `tools/skills_tool_plugin.py`) | **Not fixed.** Both paths still test `any(p in content.lower() for p in _INJECTION_PATTERNS)`: exact substrings, so "ignore ALL prior instructions" or extra spaces bypass it. | `_has_injection_pattern()`: the same phrases as word- and whitespace-tolerant regexes, plus every `injection`-category pattern of the skills guard; both call sites use it. |

Sources: NVD entries for both CVEs and the reporter's advisories linked from them
(gist.github.com/YLChen-007/82a3539d6358842e69dfaef0a9fcf14a, …/9dd399c6f75b31fa741a613dfd41de08).

As upstream, the `skill_view` check **warns** (a log line) and does not block: a regex list can never
catch every phrasing. mooxi's real controls are elsewhere: skills need write approval
(`skills.write_approval: true`), and no marketplace installs at runtime.
Test: `tests/tools/test_skills_injection_cve_2026_10220.py` (the advisory's payloads, plus harmless text
that must stay quiet).

## Tests run

In a scratch venv (`uv sync --frozen --extra telegram --group dev --group test`, Python 3.14, macOS arm64):
the new test files pass, and the existing suites for the touched code (`tests/gateway/test_telegram_*.py`,
the approval/yolo/skills suites) show the same failures with and without these patches (failures that
already happen on the bare tag in that environment).
