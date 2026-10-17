"""Draw the code-native CashProof scan mark; no source footage or external assets."""
from pathlib import Path
from PIL import Image, ImageDraw

out = Path(__file__).resolve().parents[1] / "assets"
out.mkdir(exist_ok=True)
im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((4, 4, 252, 252), radius=58, fill="#a31551")
ink = "#ffffff"
for points in [[(94, 66), (66, 66), (66, 94)], [(162, 66), (190, 66), (190, 94)], [(66, 162), (66, 190), (94, 190)], [(162, 190), (190, 190), (190, 162)]]:
    d.line(points, fill=ink, width=13, joint="curve")
d.rounded_rectangle((61, 122, 195, 134), radius=6, fill=ink)
im.save(out / "app.png")
im.save(out / "app.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
