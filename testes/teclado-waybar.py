#!/usr/bin/env python3
"""Confere o recurso sob a regra de recoloração do GTK, sem sessão gráfica."""

import json
from pathlib import Path
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parent.parent
svg_path = repo / "waybar/icones/input-keyboard-symbolic.svg" if (repo / "waybar/icones/input-keyboard-symbolic.svg").exists() else repo / "shell/waybar/icones/input-keyboard-symbolic.svg"
svg = ET.parse(svg_path).getroot()
assert svg.attrib["viewBox"] == "0 0 32 32"
assert svg.attrib["width"] == svg.attrib["height"] == "32"
# GTK impõe fill em rect, circle e path; áreas vazias precisam ser geometria.
assert all(element.tag.endswith("}path") for element in svg)
assert all(element.attrib["fill"] == "currentColor" for element in svg)
assert svg[0].attrib["fill-rule"] == "evenodd"
cfg_path = repo / "waybar/config.jsonc" if (repo / "waybar/config.jsonc").exists() else repo / "shell/waybar/config.jsonc"
config = json.loads("\n".join(
    line for line in cfg_path.read_text().splitlines()
    if not line.lstrip().startswith("//")
))
assert config["tray"]["icon-size"] == 16
assert "Fcitx" not in config["tray"].get("icons", {})
assert "keyboard" not in config["modules-right"]
