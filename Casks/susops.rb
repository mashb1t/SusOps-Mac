cask "susops" do
  version "1.0.0-rc5"
  sha256 "f79e84e200be74786360a8c8fc6e46582b7e5ae87e36448fa7f6d25121ce7a3f"

  url "https://github.com/mashb1t/susops-mac/releases/download/v#{version}/SusOps.zip"
  name "SusOps"
  desc "MacOS menu bar app for easy website proxying and port forwarding (SSH‑based SOCKS5 proxy + HTTP PAC server)"
  homepage "https://github.com/mashb1t/susops-mac"

  app "SusOps.app"
end
