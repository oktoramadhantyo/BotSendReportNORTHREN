import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

JAKUT_STO = ["CIL", "MRD", "KLG", "KTX", "KTZ", "MKR", "PDM", "STR", "TPR"]
JAKBAR_STO = ["CKG", "TGA", "KPK", "JIA", "KSB", "PLM", "KDY", "MRY", "SLP", "SMI", "DTG", "SDM"]

STO_TO_REGION = {}
for _sto in JAKUT_STO:
    STO_TO_REGION[_sto] = "JAKUT"
for _sto in JAKBAR_STO:
    STO_TO_REGION[_sto] = "JAKBAR"

NAMA_WILAYAH = {"JAKUT": "JAKARTA UTARA", "JAKBAR": "JAKARTA BARAT", "NORTHREN": "NORTHREN"}
LABEL_WILAYAH = {
    "JAKUT": "Jakarta Utara (JAKUT)",
    "JAKBAR": "Jakarta Barat (JAKBAR)",
    "NORTHREN": "Northren (JAKUT & JAKBAR)",
}

API_BASE = "https://api.telegram.org/bot{token}"

GROUP_FILE = BASE_DIR / "groups.json"


class GroupStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else GROUP_FILE
        self.data = {"JAKBAR": None, "JAKUT": None, "NORTHREN": None}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for region in self.data:
                        if region in raw:
                            self.data[region] = raw.get(region)
            except Exception:
                pass
        for region in self.data:
            if region not in ("JAKBAR", "JAKUT", "NORTHREN"):
                self.data.pop(region, None)
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, region):
        return self.data.get(region)

    def all_target_ids(self):
        return {str(v) for v in self.data.values() if v}

    def set(self, region, chat_id):
        if region not in self.data:
            return
        self.data[region] = str(chat_id)
        self.save()

    def clear(self, region):
        if region not in self.data:
            return
        self.data[region] = None
        self.save()