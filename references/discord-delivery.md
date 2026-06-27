# Stage D - Discord delivery

Stage D delivers the already-published daily briefing to Discord. The
public news channel must receive only real briefing/audio messages, never
cron diagnostics.

**News channel**: Discord `1490344209847287830` (`#fanli-news-daily`)

## Contract

- Stage D is a deterministic `command` cron (`payload.kind=command`), not an
  agent turn. It must not depend on a cognitive model call.
- Cron job `delivery.mode` is `none`.
- Failure alert goes only to management channel `1490362785949814905`.
- Stage D uses exactly one sending path: `openclaw message send --json`, with
  `--account fanli` (only the `fanli` bot can post to the news channel; the CLI
  default account gets `OutboundDeliveryError: Missing Access`).
- Stage D never uses cron announce delivery for the public news channel.
- State is recorded only after the CLI returns a real Discord `messageId`.
- A stale-tolerant lock (`daily/<date>/.stage_d.lock`) serializes senders, so
  the Stage D cron and the watchdog backstop can never double-post.

Delivery resilience: Stage D (07:00) is the primary deliverer, but it is no
longer single-shot. The hourly watchdog re-runs `send` for **today** after 07:00
UTC if all 7 steps are ok but a delivery is still pending — so a transient send
error or a late push is retried automatically (lock-guarded, idempotent). Past
days are never auto-delivered.

The cron runs one command on the Gateway:

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news
python3 scripts/stage_d_delivery.py send --date today
```

`send`:

1. requires `steps.push.status == "ok"` (else prints `skip`, sends nothing);
2. if both deliveries already have a real snowflake, prints `complete`, sends nothing;
3. treats `message_id: "cron-announce"` and other non-snowflakes as invalid, so
   old false-success state cannot block recovery;
4. builds the compact text message from `meta.json` + SQLite in selected
   article order;
5. copies `daily/.../audio.mp3` to
   `/Users/unclejoe/.openclaw/media/manual/<DATE>_audio.mp3`;
6. for each `needed` delivery, calls
   `openclaw message send --channel discord --target channel:1490344209847287830
   --message <text> [--media <mp3>] --json`, parses the real `messageId`, and
   records it with `method: "openclaw_message"`.

It is idempotent (skips deliveries already recorded), single-shot per delivery,
and exits non-zero without recording on any send failure.

## Manual run / recovery

Dry-run first (calls the CLI with `--dry-run`; sends and records nothing):

```bash
python3 scripts/stage_d_delivery.py send --date <DATE> --dry-run
python3 scripts/stage_d_delivery.py send --date <DATE>
```

If a send fails, `send` stops and exits non-zero without recording success. The
cron failureAlert notifies the management channel. Do not post a diagnostic
message to the public news channel.

If old false state exists, clear it explicitly, then re-run:

```bash
python3 scripts/stage_d_delivery.py clear \
  --date today \
  --key discord_text discord_audio
python3 scripts/stage_d_delivery.py send --date today
```

The `record` subcommand still exists for the rare case where a message id is
obtained out of band; the cron does not use it.

## Verification

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news
python3 scripts/daily_pipeline.py --date today --status
python3 scripts/stage_d_delivery.py prepare --date today
```

Successful delivery means:

- `daily_pipeline.py --status` shows all 7 pipeline steps ok;
- `.state.json.deliveries.discord_text.message_id` is a real Discord
  snowflake id;
- `.state.json.deliveries.discord_audio.message_id` is a real Discord
  snowflake id;
- `stage_d_delivery.py prepare` returns `status: "complete"`.

## Hard rules

- Do not convert Stage D back to an agent turn; keep it a `command` cron.
- Do not post `briefing.md` verbatim; it exceeds Discord's message budget.
- Do not record `cron-announce` or any non-snowflake value as a message id.
- Do not mark delivery before `openclaw message send` returns a real message id.
- Do not add `discord_text` or `discord_audio` to pipeline `steps`; they
  remain `state["deliveries"]`.
- Do not retry in a loop. One Stage D run sends each missing delivery once.
