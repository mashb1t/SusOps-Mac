# SusOps Toolbar for macOS 🍏

A tiny, native-feeling **menu-bar companion** for the [**SusOps**](https://github.com/mashb1t/susops) SSH–proxy
toolkit.
Built with [`rumps`](https://github.com/jaredks/rumps), the app lets you start/stop the SusOps SOCKS proxy, add local /
remote port-forwards, and tweak settings without touching a terminal.

> [!IMPORTANT] 
> The core CLI lives in the SusOps repo and is included here as a **git submodule**.  
> Clone with `--recursive` or run `git submodule update --init` after checkout.

---

## Features

| Menu action                         | CLI equivalent              | What it does                                             |
|-------------------------------------|-----------------------------|----------------------------------------------------------|
| **Start / Stop / Restart Proxy**    | `so start / stop / restart` | Launch or tear down SOCKS5+ PAC server via SSH.          |
| **Add Host…**                       | `so add <domain>`           | Add a domain to the PAC file.                            |
| **Add Local Forward…** (from → to)  | `so add -l REMOTE LOCAL`    | Expose a remote service on `localhost:<LOCAL>`.          |
| **Add Remote Forward…** (from → to) | `so add -r LOCAL REMOTE`    | Publish a local port on `ssh_host:<REMOTE>`.             |
| **Status…**                         | `so ps`                     | Show running state and active forwards.                  |
| **Preferences…**                    | edit dot‑files              | GUI for SSH host & port defaults; optional auto‑restart. |
| **Test Host / Test All**            | `so test …`                 | Quick connectivity test dialogs.                         |

---

## Installation (Production)

Download the latest build.

## Installation (Development)

```bash
# 1 – Clone with submodule
git clone --recursive https://github.com/mashb1t/susops-mac.git
cd susops-mac

# 2 – Create a venv & install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional
# 3 – Build the .app bundle
python setup.py py2app

# 4 – Launch
open dist/SusOps.app
```

> The build embeds **`susops.sh`** and all logo assets under `Contents/Resources/`.

---

## Runtime files

| Location                                       | Purpose                         |
|------------------------------------------------|---------------------------------|
| `~/.susops/`                                   | Same config files the CLI uses. |

---

## Requirements (tested with)

* macOS 15.4.1 +
* Python 3.12 + (for building)
* A host with ssh you control 😉

---

## Contributing

1. Fork & clone (remember `--recursive`).
2. Create a feature branch.
3. `python app.py` while hacking UI.
4. `python setup.py py2app` to test the packaged app.
5. Open a PR.

---

## License

MIT © 2025 Manuel Schmid — see `LICENSE`.  
SusOps CLI (submodule) retains its own MIT license.
