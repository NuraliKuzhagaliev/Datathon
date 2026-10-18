"""Draw original geometric JPEG fixtures, without opening any supplied footage."""
import base64
import io
import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

font = Path('C:/Windows/Fonts/arial.ttf')
parser = argparse.ArgumentParser()
parser.add_argument('--language', choices=['ru', 'en'], default='ru')
english = parser.parse_args().language == 'en'
out = Path(__file__).resolve().parents[1] / 'src/mocks/generated'
out.mkdir(exist_ok=True)
frames = []
for event, times in enumerate([[11.4, 12.4, 13.4], [21.0]]):
    group = []
    for index, seconds in enumerate(times):
        im = Image.new('RGB', (464, 848), '#211a22')
        draw = ImageDraw.Draw(im)
        def text(y, value, size, color):
            draw.text((232, y), value, font=ImageFont.truetype(str(font), size), fill=color, anchor='mm')
        text(70, 'SYNTHETIC EXAMPLE' if english else 'СИНТЕТИЧЕСКИЙ ПРИМЕР', 24, '#f9d8e7')
        text(112, f'Demo event {event + 1}' if english else f'Учебное событие {event + 1}', 22, '#d1bec8')
        draw.rounded_rectangle((54, 280, 410, 580), radius=24, outline='#725263', width=2)
        offset = (index - 1) * 28
        draw.rounded_rectangle((132 + offset, 355, 292 + offset, 515), radius=12, outline='#e8a2c1', width=5)
        draw.line((72, 425, 392, 425), fill='#a31551', width=3)
        text(665, f'00:{seconds:04.1f}', 30, '#ffffff')
        text(756, 'NOT REAL FOOTAGE' if english else 'НЕ РЕАЛЬНАЯ СЪЁМКА', 23, '#f9d8e7')
        text(794, 'No model was run' if english else 'Модель не выполнялась', 19, '#d1bec8')
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=88)
        group.append(base64.b64encode(buf.getvalue()).decode('ascii'))
    frames.append(group)
(out / ('frames.en.json' if english else 'frames.json')).write_text(json.dumps(frames), encoding='utf-8')
print('Generated four original synthetic frames in ' + ('English.' if english else 'Russian.'))
