#!/bin/bash
# CARWASH installer — Linux / Mac / Termux

set -e

echo ""
echo "◈ CARWASH installer"
echo ""

# detect platform
if [ -d "/data/data/com.termux" ]; then
  PLATFORM="termux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="mac"
else
  PLATFORM="linux"
fi

echo "platform: $PLATFORM"
echo ""

# deps
case $PLATFORM in
  termux)
    pkg update -y && pkg install -y python ffmpeg git
    ;;
  mac)
    if ! command -v brew &>/dev/null; then
      echo "installing homebrew..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python ffmpeg
    ;;
  linux)
    apt-get update -qq && apt-get install -y python3 python3-pip python3-venv ffmpeg espeak
    ;;
esac

# clone
if [ ! -d "neonforge-carwash" ]; then
  git clone https://github.com/Kelushael/neonforge-carwash.git
fi
cd neonforge-carwash

# venv
python3 -m venv env
source env/bin/activate
pip install -q -r requirements.txt

echo ""
echo "✓ done"
echo ""
echo "  run the web player:"
echo "  cd neonforge-carwash && source env/bin/activate && python3 server.py"
echo ""
echo "  then open: http://localhost:8888"
echo ""
