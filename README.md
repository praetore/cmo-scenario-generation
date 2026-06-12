# CMO scenario generation

Generate and play **Command: Modern Operations** scenarios using **Cursor** (AI assistant) plus Python tooling.

---

## What is Command: Modern Operations?

[Command: Modern Operations](https://www.matrixgames.com/game/command-modern-operations) (CMO) is a real-time military wargame. You place ships, aircraft, submarines, and land units on a map, assign missions, and run what-if conflicts.

CMO includes a **Lua scripting API** so you can build a full scenario from a script instead of placing every unit by hand. This repository uses that API — plus checks against CMO’s equipment database — to turn a scenario idea into a file you can load in the game.

---

## What is this project?

Open this repo in **Cursor**, describe a scenario in chat, and let the agent build a ready-to-load Lua file for you. Database checks (wrong aircraft/loadout pairs, units on land, bad timing, etc.) run automatically — you do not run a separate validate step.

Scenarios are written to **`generated/`** on your machine (gitignored). Player briefings live separately in **`generated/src/`** (e.g. `generated/src/my_scenario_briefing.txt`) and are injected into the scenario when the agent builds it.

---

## Install

### 1. Command: Modern Operations

Install CMO from [Steam](https://store.steampowered.com/app/1076160/Command_Modern_Operations/) or your usual source. The game ships large SQLite database files (e.g. **DB3K 515**) that the tooling uses to verify unit IDs and loadouts.

### 2. Python

Install **Python 3.10 or newer**. The scripts use only the standard library plus your local CMO install.

### 3. Cursor

Install [Cursor](https://cursor.com) and open this repository as a folder (**File → Open Folder**).

### 4. Point the tools at your game

From the repository root:

```bash
copy cmo_config.example.ini cmo_config.ini
```

Edit `cmo_config.ini` and set `cmo_install_dir` to your CMO install folder, for example:

```ini
[cmo]
cmo_install_dir = C:/Program Files (x86)/Steam/steamapps/common/Command Modern Operations
```

`cmo_config.ini` is gitignored — it stays on your machine only.

---

## Generate and run a scenario

Do this in **Cursor Agent** (chat with Agent mode enabled). The repo’s `.cursor/rules/` files tell the agent how to write valid CMO Lua.

### 1. Ask Cursor to generate a scenario

Paste something like this into Cursor chat (change the idea if you like):

> Make a Cuba scenario — rising US–Cuba tensions in the Caribbean after a disputed shipping incident.

The agent writes the scenario, runs the build tooling, and gives you **`generated/<name>.lua`** — that is the file you load in the game. 
For the Cuba example, you might get a US naval presence offshore, Cuban patrol aircraft, and coastal defenses on alert. To change what players read at scenario start, edit the briefing in **`generated/src/<name>_briefing.txt`** and ask Cursor to rebuild.

### 2. Run the scenario in CMO

1. Copy **`generated/<name>.lua`** into your CMO **`Lua`** folder (under the game install; subfolders are fine).
2. Launch **Command: Modern Operations** → **Scenario Editor**.
3. Open the **Lua Script Console** and run your script.
4. Watch the in-game message log for setup output and any errors.
5. Press **Play** and run the scenario.
6. Optionally **Save** as a `.scen` file so you can reopen it without re-running the script.

### Example end-to-end

| Step | Where | What |
|------|--------|------|
| Describe scenario | **Cursor** chat | Example query above |
| Build | **Cursor** Agent | Produces `generated/<name>.lua` (briefings in `generated/src/`) |
| Load script | **CMO** Scenario Editor | Run `generated/<name>.lua` from the Lua console |
| Play | **CMO** | Start the scenario on the map |

---

## License

MIT — see [LICENSE](LICENSE).
