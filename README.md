<p align="center">
    <img src="images/logos/icon.png" alt="Menu" height="200" />
</p>

# SusOps for macOS - SSH Utilities & SOCKS5 Operations

A native-feeling **menu-bar app** for the [**SusOps CLI**](https://github.com/mashb1t/susops-cli) SSH–proxy and forwarding toolkit. 
**SusOps CLI** is already bundled, no need to manually download it (again).

Built with [rumps](https://github.com/jaredks/rumps), the app lets you start/stop the SusOps SOCKS proxy, add
local / remote port-forwards, and tweak settings without touching a terminal.

<img src="screenshots/menu.png" alt="Menu" height="400"/>

## Features

| Menu action                      | CLI equivalent                                              | What it does                                             |
|----------------------------------|-------------------------------------------------------------|----------------------------------------------------------|
| **Status**                       | `so ps`                                                     | Show running state and active forwards.                  |
| **Settings…**                    | edit dot‑files                                              | GUI for SSH host & port defaults; optional auto‑restart. |
| **Add Host…**                    | `so add <domain>`                                           | Add a domain to the PAC file.                            |
| **Add Local Forward…**           | `so add -l REMOTE LOCAL`                                    | Expose a remote service on `localhost:<LOCAL>`.          |
| **Add Remote Forward…**          | `so add -r LOCAL REMOTE`                                    | Publish a local port on `ssh_host:<REMOTE>`.             |
| **Start / Stop / Restart Proxy** | `so start`<br/>`so stop`<br/>`so restart`                   | Launch or tear down SSH SOCKS5 Proxy and PAC server.     |
| **Test Host / Test All**         | `so test …`                                                 | Quick connectivity test dialogs.                         |
| **Launch Browser**               | `so firefox`<br/>`so chrome`<br/>`so chrome-proxy-settings` | Open a browser preconfigured with the PAC file.          |
| **Reset All**                    | `so reset`                                                  | Remove all domains and port-forwards.                    |

## Requirements

The app may be compatible with older versions of macOS, but it is not tested.

* macOS 15.4.1+
* Python 3.12+ (for building only)
* A remote host you have ssh access to

## Setup

### 1. Install via Homebrew

```bash
brew tap mashb1t/susops
brew install --cask susops
```

For updating, simply run these commands:

```bash
brew update
brew install --cask susops
```

> [!NOTE]
> When using `brew upgrade --cask susops`, homebrew tries to upgrade SusOps in-place, which fails due to a rumps incompatibility with swift.
> You will get an error like `error: redefinition of module 'SwiftBridging'`.
> Please manually delete the app and install it again with `brew install --cask susops`. No data is lost in the process.

### OR install manually

1. Download the SusOps.zip file from the [latest release](https://github.com/mashb1t/susops-mac/releases)
2. Unzip the file
3. (Optional) Move the SusOps app to your Applications folder

### 2. Configure

1. Launch the application
2. Set up your SSH host and ports in the **Settings** menu 
3. Start the proxy (menu bar icon should turn green)
4. Add domains (requires browser [proxy settings reload](chrome://net-internals/#proxy)) or port-forwards (requires proxy restart)


## Build from source (development)

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

> [!IMPORTANT]
> The [**SusOps CLI**](https://github.com/mashb1t/susops-cli) lives in its own repository and is included here as a **git submodule**.  
> Make sure you clone with `--recursive` or run `git submodule update --init` after checkout.

The build embeds **`susops.sh`** and all logo assets under `Contents/Resources/`.

## Runtime files

| Location     | Purpose                         |
|--------------|---------------------------------|
| `~/.susops/` | Same config files the CLI uses. |

## How To Use Susops As Docker Proxy

See [SusOps CLI Readme](https://github.com/mashb1t/susops-cli?tab=readme-ov-file#how-to-use-susops-as-docker-proxy)

## Troubleshooting

| Problem                                                         | Solution                                                                                                                                                                                                                                                                                                                                                       |
|-----------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **SusOps won't start after installation**                       | You may need to allow its startup in **System Settings** > **Privacy & Security** or run `xattr -rd com.apple.quarantine /Applications/SusOps.app`                                                                                                                                                                                                             |
| **SusOps starts, but doesn't show up in menu bar**              | MacOS only displays so many menu bar apps. Ensure you don't have too many other items open.                                                                                                                                                                                                                                                                    |
| **SusOps in state "error"**                                     | Ensure you have set up a connection and the directory `~/.susops` exists                                                                                                                                                                                                                                                                                       |
| **Proxy doesn't start**                                         | Open the config and ensure that you can manually connect to the SSH host. Also check if another app is already using your connection port with `lsof -nP -iTCP:<port> \| grep LISTEN`. <br/><br/>If you have protected your private key with a passphrase, please create a separate key without passphrase, as SusOps can't handle interactive password input. |
| **Chrome doesn't pick up my added domains**                     | Make sure you completely close Chrome and open it again using the **Launch Browser** menu item. Then, open the Chrome Proxy settings and click **Re-apply settings**.                                                                                                                                                                                          |
| **Firefox doesn't pick up my added domains**                    | Make sure you completely close Firefox and open it again using the **Launch Browser** menu item.                                                                                                                                                                                                                                                               |
| **Clicked "Don't Allow" for Login Items when opening settings** | You can manually re-enable the **System Events** in **System Settings** > **Privacy & Security** > **Automation** > **SusOps**. Check **Launch at Login**, save the config and you should find it in **System Settings** > **General** > **Login Items & Extensions**                                                                                          |
| **Docker Desktop doesn't use the domains configured in SusOps** | See [SusOps CLI Readme](https://github.com/mashb1t/susops-cli?tab=readme-ov-file#how-to-use-susops-as-docker-proxy)                                                                                                                                                                                                                                            |
| **Everything else**                                             | see [Troubleshooting Guide SusOps CLI](https://github.com/mashb1t/susops-cli?tab=readme-ov-file#troubleshooting) or [Report a Bug](https://github.com/mashb1t/susops-mac/issues/new).                                                                                                                                                                          |

## Contributing

1. Set up the project as described above in "Build from source (development)".
2. Create a feature branch.
3. `python app.py` while hacking UI.
4. `python setup.py py2app` to test the packaged app.
5. Open a [PR](https://github.com/mashb1t/susops-mac/pulls).

## License

MIT © 2025 Manuel Schmid — see [LICENSE](LICENSE).
[**SusOps CLI**](https://github.com/mashb1t/susops-cli) (submodule) retains its own [license](https://github.com/mashb1t/susops-cli/blob/main/LICENSE.txt).
