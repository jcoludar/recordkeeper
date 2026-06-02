# Recovery — <project name>

Stale state: <date>

## Available recovery paths

(Pick the lines that apply; delete the rest. Order: cheapest first.)

- **Cloud-sync version history.** Path: `<absolute path to cloud-sync-linked dir>`. Web UI → right-click → Version history.
- **Local backup snapshot.** Backup target: `<backup volume>`. Snapshots: hourly for past 24h, daily for past month.
- **Git reflog.** Repo root: `<path>`. Reflog horizon: <days>.
- **Re-fetch.** Upstream URL or command: `<...>`.
- **Re-run pipeline.** Command: `<...>`. Wall time: `<...>`.

## What has NO recovery path

(List any directory that is genuinely unrecoverable. Be honest — "we'd notice within a week" is not recovery.)

- ...
