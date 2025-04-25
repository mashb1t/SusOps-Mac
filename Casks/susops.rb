cask "susops" do
  version "1.0.0"
  sha256 "ddd9c2140c1a0bce02a598df27e0bf9b1f7c83db742bc6f89b35226c03bb3160"

  url "https://github.com/mashb1t/susops-mac/releases/download/v#{version}/SusOps.zip"
  name "SusOps"
  desc "MacOS menu bar app for easy website proxying and port forwarding (SSH‑based SOCKS5 proxy + HTTP PAC server)"
  homepage "https://github.com/mashb1t/susops-mac"

  app "SusOps.app"
end
