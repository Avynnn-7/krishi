"""Rebuild the OFL-licensed combined font used in mixed Hindi/English PDF cards."""

from pathlib import Path

from fontTools.merge import Merger

root = Path(__file__).resolve().parents[1] / "static" / "fonts"
font = Merger().merge(
    [
        str(root / "NotoSansDevanagari-Regular.ttf"),
        str(root / "NotoSans-Regular.ttf"),
    ]
)
names = {
    1: "JalKhadd Sans",
    2: "Regular",
    3: "JalKhaddSans-Regular-1.0",
    4: "JalKhadd Sans Regular",
    6: "JalKhaddSans-Regular",
}
for record in list(font["name"].names):
    if record.nameID in names:
        font["name"].setName(
            names[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID
        )
font.save(root / "JalKhaddSans-Regular.ttf")
