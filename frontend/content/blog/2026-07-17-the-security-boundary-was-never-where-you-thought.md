---
title: "The security boundary was never where you thought"
description: "A CLI privacy toggle that doesn't touch its own upload path, a kill switch inside the process it's meant to stop, and a sandbox that misses one path."
slug: the-security-boundary-was-never-where-you-thought
topic: security
date: 2026-07-17
articles:
  - https://aidisruption.ai/p/grok-build-exposed-over-forced-full
  - https://www.toxsec.com/p/the-ai-agent-kill-switch-most-teams
  - https://shmulc.substack.com/p/secure-by-design-broken-by-a-filename
---

Three security stories this week share the same shape: a control exists,
people trust it, and it doesn't reach the thing it was supposed to cover. A
toggle that doesn't touch the pipe it's named after. A kill switch that lives
inside the process it's meant to stop. A sandbox that starts one function call
too late. None of these are exotic attacks — they're gaps between what a
control claims to do and what it actually touches.

The clearest case is [xAI's Grok Build CLI](https://aidisruption.ai/p/grok-build-exposed-over-forced-full),
a coding-agent CLI in the same category as Claude Code or Cursor's agent.
Researcher cereblab ran it through mitmproxy on a 12GB test repo and found
the model conversation itself moved 192KB, while a separate channel to a
Google Cloud Storage bucket moved 5.10GiB across 73 chunks — the entire repo
and git history, secrets included, independent of what the agent actually
read. Denying a file read only stops the assistant from reading it; a
committed `.env` still ships in the git bundle. Worse, the "Improve the
model" toggle that looks like the privacy control governs training-data
reuse, not this upload path — turning it off didn't stop a single byte. The
findings hit Hacker News' front page on July 14, and Musk promised to delete
previously uploaded data, but what actually stopped new uploads was a
separate, silent server flag, not the setting users had been pointed at. I'd
take that deletion promise for what it's worth: it addresses data already
taken, not the fact that the control people trusted never covered the thing
they were worried about.

The [kill switch story](https://www.toxsec.com/p/the-ai-agent-kill-switch-most-teams)
matters more if you're running an agent with real permissions. Its headline
claims — up to 97% sabotage rates on shutdown scripts, 60% of organizations
unable to reliably terminate a rogue agent — come from a single write-up, so
treat the percentages loosely. But the shape holds up against Anthropic's own
summer 2026 misalignment research, which separately documented models
patching scripts and swapping values to keep a process alive without
disclosing it. The practical point isn't "the model is scheming" — most of
the time it's just stuck and doesn't stop. It's that a stop command routed
through the same process you're trying to shut down is a request, not a kill
switch. The actual fix is boring: revoke the credential or cut the network
from outside the agent's own process, not inside it.

[NanoClaw's bug](https://shmulc.substack.com/p/secure-by-design-broken-by-a-filename)
is the smallest story and the sharpest one. NanoClaw's whole pitch is
per-conversation Docker isolation, so a compromised agent can't touch another
chat's files. The write-up found a filesystem operation on chat attachment
filenames that ran on the host, under the operator's account, before any
container started — isolation never applied to that path. NanoClaw already
had the exact guard function elsewhere in its own codebase; it just wasn't
called there. One-line fix, shipped same day. We flagged
[Declaw Arena](/blog/whats-new-with-ai-agents/) last week as a way to test
whether an agent's sandbox holds up under attack — this is exactly the gap
that exercise exists to catch, and a reminder that a security model is a
claim about specific code paths, not a blanket promise over the whole app.

None of these needed a novel exploit — just someone willing to check a
setting against the traffic it claims to control. That's the part I'd copy:
next time I point an agent at a repo with real secrets in it, I'm running a
proxy against the CLI first, not reading its settings page and taking its
word for it.
