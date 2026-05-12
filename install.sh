#!/usr/bin/env bash
# WatchROM — One-Command Installer
# Usage: bash install.sh  OR  bash install.sh --force
set -e
R="\033[0;31m"; G="\033[0;32m"; Y="\033[1;33m"; C="\033[0;36m"
W="\033[1;37m"; DIM="\033[2m"; NC="\033[0m"; BOLD="\033[1m"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${C}\n WatchROM — One Kit to Rule Them All — Installer\n${NC}"

# Python check
if ! command -v python3 &>/dev/null; then
    echo -e "${R}✗ Python 3.8+ required: sudo apt install python3${NC}"; exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${G}✓ Python ${PY_VER}${NC}"

# Bootstrap pip packages needed by setup.py
echo -e "\n${C}→ Bootstrapping pip...${NC}"
python3 -m pip install --break-system-packages -q rich click prompt_toolkit 2>/dev/null \
    || python3 -m pip install -q rich click prompt_toolkit

# Run full Python dependency installer
echo -e "\n${C}→ Running dependency setup...${NC}\n"
FORCE_ARG=""
[[ "$1" == "--force" ]] && FORCE_ARG="--force"
python3 "$SCRIPT_DIR/setup.py" $FORCE_ARG

# Register watchrom CLI
echo -e "\n${C}→ Registering watchrom command...${NC}"
if sudo tee /usr/local/bin/watchrom > /dev/null 2>&1 << WRAP
#!/usr/bin/env bash
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
exec python3 "$SCRIPT_DIR/main.py" "\$@"
WRAP
then
    sudo chmod +x /usr/local/bin/watchrom
    echo -e "  ${G}✓ /usr/local/bin/watchrom${NC}"
else
    mkdir -p "$HOME/.local/bin"
    printf '#!/usr/bin/env bash\nexec python3 "%s/main.py" "$@"\n' "$SCRIPT_DIR" > "$HOME/.local/bin/watchrom"
    chmod +x "$HOME/.local/bin/watchrom"
    echo -e "  ${G}✓ $HOME/.local/bin/watchrom${NC}"
fi

# watchrom-menu alias (TUI only)
sudo tee /usr/local/bin/watchrom-menu > /dev/null 2>&1 << WRAP2 || true
#!/usr/bin/env bash
exec python3 "$SCRIPT_DIR/launcher.py" "\$@"
WRAP2
sudo chmod +x /usr/local/bin/watchrom-menu 2>/dev/null || true

chmod +x "$SCRIPT_DIR/main.py" "$SCRIPT_DIR/launcher.py" "$SCRIPT_DIR/setup.py"

# udev rules
echo -e "\n${C}→ Installing udev USB rules...${NC}"
sudo tee /etc/udev/rules.d/99-watchrom.rules > /dev/null << 'UDEV'
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="1782", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="05c6", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="2a70", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="22d9", MODE="0666", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="2d95", MODE="0666", GROUP="plugdev", TAG+="uaccess"
UDEV
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger 2>/dev/null || true
sudo usermod -aG plugdev "$USER" 2>/dev/null || true
echo -e "  ${G}✓ udev rules installed${NC}"

echo -e "\n${G}${BOLD}╔═══════════════════════════════════════════╗"
echo -e "║  WatchROM installed!  ★                   ║"
echo -e "║                                           ║"
echo -e "║  Run: watchrom                            ║"
echo -e "║  (interactive guided menu launches)       ║"
echo -e "╚═══════════════════════════════════════════╝${NC}\n"
