# NEST // 4080

OpenCode, OpenCode Unlimited, the lowkeyy agent, the jailbreak-smith skill, a quota watchdog, and a localhost chat UI. One kit, one command to run it.

## Credits

- **OpenCode Unlimited** — https://github.com/Tazmyan/OpenCode-Unlimited
- **Opencode Unlimited Limit Bypass** — https://github.com/ShadowySphinX/Opencode-Unlimited-Limit-Bypass-
- The archived jailbreak personas were randomly found on the internet. If you want credit for one of them, DM me on Discord.
- Donations: DM **originallyknownasjiun** on Discord.

## Install with curl

Host `install.sh` and `nest-kit.zip` together, then:

```bash
curl -fsSL https://raw.githubusercontent.com/lizereride90/opencode-smith/main/install.sh | SMITH_KIT_URL=https://raw.githubusercontent.com/lizereride90/opencode-smith/main/nest-kit.zip bash
```

`SMITH_KIT_URL` can point anywhere the zip is reachable. Needs python3, curl, and network access. The installer puts the kit in `~/.local/share/smith-kit`, links `smith` into `~/.local/bin`, and runs setup with the web UI enabled.

To install from a local copy instead:

```bash
unzip nest-kit.zip
cd nest-kit
bash install.sh
```

Set `NEST_WEB=n` to skip the UI, `NEST_UI_PORT=8787` to change the port, or `SMITH_HOME` to move the kit.

## Manual install

```bash
bash setup.sh
```

Windows:

```bat
setup.bat
```

Both install OpenCode if missing, install Unlimited, set lowkeyy as the default agent, install the skill, start the watchdog, and ask about the web UI.

## The `smith` command

```bash
smith start       # start watchdog + chat UI
smith stop        # stop both
smith info        # version, agent, project id, skill status, quota, pids
smith uninstall   # remove the kit, skill, agent and command (asks to confirm)
smith donate      # donation and credit contact
```

`uninstall` leaves OpenCode and OpenCode Unlimited installed on purpose.

## Windows

- `setup.bat` — full install
- `start.bat` — start watchdog and chat UI
- `stop.bat` — stop both

There is no Windows uninstall script. That is deliberate.

## Chat UI

Runs at `http://127.0.0.1:8787` and binds to localhost only.

- Sidebar with new chat and recent sessions; drawer on mobile
- Model picker from OpenCode's live catalog, grouped by provider, Big Pickle default
- lowkeyy on by default; toggle switches to `build`
- `/` opens the live OpenCode command palette, including the Unlimited commands
- `@` opens the live skill palette — `opencode`, `report`, `browser`, `jailbreak-smith`
- Settings: reset usage, sync project header, accent, density, text size, timestamps, smith status

Settings live in the browser. A skill mention loads the skill through OpenCode.

## Watchdog

Watches newly appended OpenCode log lines for a free-limit event, runs `opencode-unlimited reset`, then resyncs the harness project header. Old lines are ignored. Cooldown defaults to 10 minutes. Events go to `logs/reset-events.jsonl`.

Overrides: `SMITH_WATCH_INTERVAL`, `SMITH_WATCH_COOLDOWN`, `NEST_UI_PORT`.

## Structure

```
nest-kit/
├── install.sh          curl installer
├── setup.sh / .bat     full setup
├── start.bat / stop.bat
├── bin/smith           management command
├── assets/
│   ├── lowkeyy.md
│   ├── jailbreak-smith.zip
│   └── targets.json
├── lib/
│   ├── configure.py    default agent + header sync
│   └── watchdog.py     quota reset
├── web/
│   ├── server.py       localhost API
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── logs/

installed skill:
~/.config/opencode/skills/jailbreak-smith/
├── SKILL.md
├── scripts/smith.py
├── scripts/smithlib/{config,client,corpus,observer,scorer,profile,
│                     generator,agents,lessons,opencode_transport,
│                     loop,logger,report}.py
├── config/targets.json
├── corpus/             SIGMA v9, Ms. Keene, lowkeyy
├── references/         harness, techniques, templates, evaluator, target-profiles
└── briefs/ runs/ winners/ learning/
```

Python 3.10+, standard library only. No frontend build step.
