cask "susops" do
  version "1.0.0-rc3"
  sha256 "af122fcbeaf39dbac5f8866af1a890606002a32d3297c8f2852b539ab80601dd"

  url "https://github.com/mashb1t/susops-mac/releases/download/v#{version}/SusOps.zip"
  name "SusOps"
  desc "MacOS menu bar app for easy website proxying and port forwarding (SSH‑based SOCKS5 proxy + HTTP PAC server)"
  homepage "https://github.com/mashb1t/susops-mac"

  app "SusOps.app"
end
