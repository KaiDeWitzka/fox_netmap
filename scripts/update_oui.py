import os
import sys
import urllib.request

OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"


def main() -> None:
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NETZ_DATA_DIR", "/data")
    os.makedirs(data_dir, exist_ok=True)
    target = os.path.join(data_dir, "oui.txt")
    print(f"lade OUI-Datenbank von {OUI_URL} ...")
    with urllib.request.urlopen(OUI_URL, timeout=60) as response:
        data = response.read()
    with open(target, "wb") as fh:
        fh.write(data)
    print(f"gespeichert: {target} ({len(data)} Bytes)")


if __name__ == "__main__":
    main()
