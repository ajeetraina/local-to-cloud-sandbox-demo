# Instructor notes

## Timing (about 75 minutes)

| Part | Minutes |
| --- | --- |
| Prerequisites and setup | 10 |
| Lab 1: Create a local sandbox with a kit | 10 |
| Lab 2: Start the catalog job locally | 10 |
| Lab 3: Move the sandbox to the cloud | 10 |
| Lab 4: Prove it moved and resume | 10 |
| Lab 5: What moves and what doesn't | 10 |
| Lab 6: Bring results home and clean up | 10 |
| Optional: [bonus agent demo](BONUS-AGENT-DEMO.md) | 15 |

## Checklist: run the full lab once, a day before

These points could not be tested outside a real sbx install:

- [ ] `shell` works with `--kit` and starts without any model key
- [ ] `sbx cp` and `sbx exec` work on a local sandbox, and a `nohup` job keeps running after `sbx exec` returns
- [ ] The kit installs on the workshop network (it needs pypi.org and files.pythonhosted.org)
- [ ] `--on-timeout hibernate` is accepted for your accounts (the only values are `hibernate` and `delete`)
- [ ] The sandbox hostname changes after the move, so the report's laptop and cloud split is visible. If not, prefix the cloud run with `JOB_SITE=cloud`
- [ ] Attendees have the Agentic Platform plan or workshop credits before the session
- [ ] For the bonus demo: your Anthropic key is set locally and in the cloud store

## Already tested outside sbx

`tests/simulate_move.sh` runs the job, hard-kills it mid-run, copies its data folder (what `sbx move` does to the filesystem), and resumes it under a different host label. It checks that:

- the job seeds 500 products the same way every time
- a hard kill at any point, including during seeding, does not break the resume
- the job continues from the last finished product
- the report shows the laptop and cloud split, and all 500 products

Run it with Python 3 and the same SurrealDB SDK version the kit installs:

```
pip install 'surrealdb==2.0.0'
bash tests/simulate_move.sh
```

## Talking points

- A sandbox is the agent's workspace, not where your app runs. The app stays on the laptop.
- Move when work outlives your laptop session: long runs, travel, or many agents at once.
- A move copies files only. Processes, secrets, local network rules, and mounted folders stay behind.
- A cloud destination keeps the `--name` you give it, adding a unique suffix only if that name is already taken. Read the exact name or ID from `sbx --cloud ls`.
- Cloud sandboxes have a TTL (15s to 24h). Use `--on-timeout hibernate` so nothing is deleted by surprise.
