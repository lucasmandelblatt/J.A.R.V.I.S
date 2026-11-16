#!/bin/bash
# Builds Jarvis.app (by default into ~/Applications). Only needed when app/*.swift or the icon change;
# the interface (static/), personality (prompts/) and memory (the vault) update without a rebuild.
#
# Where it goes and how it is signed come from config.json, or from the environment (which wins):
#   app_path      / JARVIS_APP        where the app is installed       default ~/Applications/Jarvis.app
#   bundle_id     / JARVIS_BUNDLE_ID  the app's bundle identifier       default local.jarvis-voz
#   sign_identity / JARVIS_SIGN_ID    code-signing certificate's name   default "Jarvis Local Signing"
# macOS ties the Microphone and Screen Recording permissions to the bundle id and the certificate: change either and
# it asks for them again. README.md explains how to create the certificate.
set -euo pipefail
cd "$(dirname "$0")"
PROJECT="$(cd .. && pwd)"

setting() {   # setting <config.json key> <default>: the value in config.json (or $JARVIS_CONFIG), else the default
  local py="$PROJECT/.venv/bin/python"; [ -x "$py" ] || py=/usr/bin/python3
  "$py" -c 'import json, os, pathlib, sys
cfg = pathlib.Path(os.environ.get("JARVIS_CONFIG") or sys.argv[3])
value = (json.loads(cfg.read_text()) if cfg.exists() else {}).get(sys.argv[1]) or sys.argv[2]
print(os.path.expanduser(value))' "$1" "$2" "$PROJECT/config.json"
}
OUT="${JARVIS_APP:-$(setting app_path "$HOME/Applications/Jarvis.app")}"
BUNDLE_ID="${JARVIS_BUNDLE_ID:-$(setting bundle_id local.jarvis-voz)}"
SIGN_ID="${JARVIS_SIGN_ID:-$(setting sign_identity "Jarvis Local Signing")}"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$BUILD/Jarvis.app/Contents/MacOS" "$BUILD/Jarvis.app/Contents/Resources"
swiftc -O -o "$BUILD/Jarvis.app/Contents/MacOS/Jarvis" main.swift Jarvis.swift Claps.swift MuteKey.swift -framework Cocoa -framework Carbon -framework WebKit -framework AVFoundation
swiftc -O -parse-as-library -o "$BUILD/Jarvis.app/Contents/MacOS/jarvis-gravar" Gravar.swift -framework ScreenCaptureKit -framework CoreMedia -framework AppKit

# Icon
swift icon.swift "$BUILD/icon.png"
mkdir "$BUILD/Jarvis.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$BUILD/icon.png" --out "$BUILD/Jarvis.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$BUILD/icon.png" --out "$BUILD/Jarvis.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$BUILD/Jarvis.iconset" -o "$BUILD/Jarvis.app/Contents/Resources/Jarvis.icns"

cat > "$BUILD/Jarvis.app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Jarvis</string>
  <key>CFBundleDisplayName</key><string>Jarvis</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>Jarvis</string>
  <key>CFBundleIconFile</key><string>Jarvis</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>$(date +%Y%m%d%H%M)</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>O Jarvis usa o microfone para conversar com você por voz.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>JarvisProject</key><string>$PROJECT</string>
</dict></plist>
EOF

# Sign with a fixed local certificate, not ad hoc. macOS ties the Screen Recording (and microphone) permission
# to the signature: an ad hoc one changes on every build, so the switch in System Settings stayed "on" for an
# old build and the new one was refused. With a fixed certificate the permission survives every rebuild.
if security find-identity -p codesigning | grep -qF "\"$SIGN_ID\""; then
  codesign --force --deep --sign "$SIGN_ID" "$BUILD/Jarvis.app"
else
  echo "Aviso: certificado \"$SIGN_ID\" não encontrado; assinando ad hoc (a permissão de tela cai a cada build). Veja o README."
  codesign --force --deep --sign - "$BUILD/Jarvis.app"
fi
mkdir -p "$(dirname "$OUT")"
rm -rf "$OUT"
mv "$BUILD/Jarvis.app" "$OUT"
echo "Instalado em $OUT ($BUNDLE_ID, assinado com: $SIGN_ID)"
