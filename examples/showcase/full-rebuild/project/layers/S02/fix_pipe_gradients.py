import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMP = ROOT / "components"
scene_path = ROOT / "scene.json"
scene = json.loads(scene_path.read_text(encoding="utf-8"))

HOT = [("0", "#ffe7a0"), (".14", "#ffc343"), (".5", "#ff7600"), (".84", "#ff8a08"), ("1", "#ffa020")]
COOL = [("0", "#69f4f5"), (".14", "#32dfe5"), (".5", "#00b6c3"), (".84", "#00a4b2"), ("1", "#29d1db")]

routes = {
    "flow-orange-heater-production": [
        ("M 430 350 V 393", "orange", "vertical", 430, "M 418 350 V 393"),
        ("M 430 393 Q 430 414 451 414", "orange", "horizontal", 414, "M 430 402 Q 430 402 439 402"),
        ("M 451 414 H 700", "orange", "horizontal", 414, "M 451 402 H 700"),
    ],
    "flow-orange-production-exhaust": [
        ("M 1110 414 H 1281", "orange", "horizontal", 414, "M 1110 402 H 1281"),
        ("M 1281 414 Q 1302 414 1302 393 V 361", "orange", "vertical", 1302, "M 1290 393 V 361"),
        ("M 1302 361 Q 1302 340 1323 340", "orange", "horizontal", 340, "M 1302 352 Q 1302 352 1323 352"),
        ("M 1323 340 H 1400", "orange", "horizontal", 340, "M 1323 328 H 1400"),
    ],
    "flow-orange-exhaust-exchanger": [
        ("M 1400 340 V 560", "orange", "vertical", 1400, "M 1388 350 V 560"),
    ],
    "flow-teal-return-loop": [
        ("M 1325 692 H 346", "teal", "horizontal", 692, "M 1325 680 H 346"),
        ("M 346 692 Q 296 692 296 642", "teal", "vertical", 296, "M 308 692 Q 308 680 308 642"),
        ("M 296 642 V 431", "teal", "vertical", 296, "M 284 642 V 431"),
    ],
    "flow-orange-exchanger-side": [
        ("M 1430 594 H 1537", "orange", "horizontal", 594, "M 1430 582 H 1537"),
        ("M 1537 594 Q 1566 594 1566 623 V 665", "orange", "vertical", 1566, "M 1554 623 V 665"),
        ("M 1566 665 Q 1566 694 1537 694 H 1515", "orange", "horizontal", 694, "M 1566 682 Q 1566 682 1537 682 H 1515"),
    ],
}

def gradient_definition(index, family, orientation, center):
    if orientation == "horizontal":
        x1, y1, x2, y2 = 0, center - 19, 0, center + 19
    else:
        x1, y1, x2, y2 = center - 19, 0, center + 19, 0
    stops = HOT if family == "orange" else COOL
    stops_xml = "".join(f'<stop offset="{offset}" stop-color="{color}"/>' for offset, color in stops)
    return f'<linearGradient id="tube{index}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{stops_xml}</linearGradient>'

for name, segments in routes.items():
    definitions = ['<filter id="pipeGlow" x="-20%" y="-30%" width="140%" height="160%"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>']
    body = []
    for i, (path, family, orientation, center, highlight_path) in enumerate(segments):
        definitions.insert(0, gradient_definition(i, family, orientation, center))
        color = "#ff7600" if family == "orange" else "#00c1cb"
        edge = "#c95000" if family == "orange" else "#006b79"
        body.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="52" stroke-linecap="round" stroke-linejoin="round" opacity=".58" filter="url(#pipeGlow)"/>')
        body.append(f'<path d="{path}" fill="none" stroke="{edge}" stroke-width="44" stroke-linecap="round" stroke-linejoin="round"/>')
        body.append(f'<path d="{path}" fill="none" stroke="url(#tube{i})" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>')
        body.append(f'<path d="{highlight_path}" fill="none" stroke="#fff5df" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" opacity=".97"/>')
    title = name.replace("-", " ")
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1672" height="941" viewBox="0 0 1672 941" role="img" aria-label="{title}">
  <title>{title}</title>
  <defs>{''.join(definitions)}</defs>
  {''.join(body)}
</svg>
'''
    (COMP / f"{name}.svg").write_text(document, encoding="utf-8")
    print(f"fixed {name}: {len(segments)} locally shaded tube segments")

scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
