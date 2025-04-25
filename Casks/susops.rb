cask "susops" do
  version "1.0.0-rc4"
  sha256 "9ff183c06529d042586783a679da2abf8c183cced78b9f8da313f818b3da66d0"

  url "https://github.com/mashb1t/susops-mac/releases/download/v#{version}/SusOps.zip"
  name "SusOps"
  desc "MacOS menu bar app for easy website proxying and port forwarding (SSH‑based SOCKS5 proxy + HTTP PAC server)"
  homepage "https://github.com/mashb1t/susops-mac"

  app "SusOps.app"
end
