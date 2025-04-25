cask "susops" do
  version "1.0.0-rc8"
  sha256 "fbbbae883ec57565e1055aee3d7d040fdc7abb393ed3cd0a2461a71caff5f1bc"

  url "https://github.com/mashb1t/susops-mac/releases/download/v#{version}/SusOps.zip"
  name "SusOps"
  desc "MacOS menu bar app for easy website proxying and port forwarding (SSH‑based SOCKS5 proxy + HTTP PAC server)"
  homepage "https://github.com/mashb1t/susops-mac"

  app "SusOps.app"
end
