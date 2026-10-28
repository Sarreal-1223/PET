"""One-time atlas extraction, body registration and review artifacts."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

ASSETS = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
          else Path(__file__).resolve().parents[2]) / "assets"
CANVAS = (192, 208)
ANCHOR = (96, 201)
SLEEP_FRAME_COUNT = 32
SLEEP_TICK_MS = 100


def make_sleep_loop(base):
    """Cache a gentle breath from one pose; keep the floor fixed throughout."""
    frames = []
    for index in range(SLEEP_FRAME_COUNT):
        # Cosine has matching position and velocity at the loop boundary.
        stretch = 1.0 + 0.018 * (1-math.cos(2*math.pi*index/SLEEP_FRAME_COUNT))/2
        image = QImage(*CANVAS, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(0, ANCHOR[1])
        painter.scale(1, stretch)
        painter.translate(0, -ANCHOR[1])
        painter.drawPixmap(0, 0, base)
        painter.end()
        frames.append(QPixmap.fromImage(image))
    return frames


def pixels(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = bytes(image.constBits())
    stride = image.bytesPerLine()
    points = [(x, y) for y in range(image.height()) for x in range(image.width())
              if data[y * stride + x * 4 + 3] > 8]
    return points


def bounds(points):
    if not points:
        return None
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def clean_subject(image):
    """Discard detached matte speckles; keep the largest alpha component."""
    points = set(pixels(image))
    largest = set()
    while points:
        start = points.pop()
        component, stack = {start}, [start]
        while stack:
            x, y = stack.pop()
            for point in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if point in points:
                    points.remove(point)
                    component.add(point)
                    stack.append(point)
        if len(component) > len(largest):
            largest = component
    result = image.convertToFormat(QImage.Format.Format_ARGB32)
    for x, y in pixels(image):
        if (x, y) not in largest:
            result.setPixelColor(x, y, QColor(0, 0, 0, 0))
    return result


def load_library(remove_matte):
    sheets = {name: QImage(str(ASSETS / filename)) for name, filename in (
        ("main", "calico_spritesheet.png"), ("pose", "calico_pose_sheet.png"),
        ("sleep", "calico_sleep_sheet.png"))}
    specs = {"idle": (0, 6), "walk_right": (1, 8), "walk_left": (2, 8),
             "paw": (3, 4), "bounce": (4, 5), "blink": (5, 8),
             "tilt": (6, 6), "knead": (7, 6), "look_down": (8, 6),
             "look_up": (9, 8), "look_side": (10, 8)}
    raw, processed, records = {}, {}, {}
    expected = {"main": (1536, 2288), "pose": (1536, 1170), "sleep": (1774, 887)}
    for name, sheet in sheets.items():
        if not sheet.isNull() and (sheet.width(), sheet.height()) != expected[name]:
            raise ValueError(f"Unexpected {name} atlas size: {sheet.size()}; re-inspect crop manifest")

    def extract(name, sheet_name, rects):
        sheet = sheets[sheet_name]
        raw[name], processed[name], records[name] = [], [], []
        if sheet.isNull():
            return
        for index, rect in enumerate(rects):
            image = sheet.copy(QRect(*rect))
            if sheet_name == "pose":
                image = remove_matte(image)
            original_bounds = bounds(pixels(image))
            raw[name].append(image.copy())
            if sheet_name == "sleep":
                image = clean_subject(image)
            box = bounds(pixels(image))
            record = dict(source=sheet_name, source_index=index, crop=rect,
                          raw_bbox=original_bounds, bbox=box,
                          touches_crop_edge=bool(box and (box[0] == 0 or box[1] == 0 or box[2] == image.width() or box[3] == image.height())),
                          excluded=("upright tail" if name == "sleep" and index == 6 else None))
            records[name].append(record)
            processed[name].append(image)

    for name, (row, count) in specs.items():
        extract(name, "main", [(col*192, row*208, 192, 208) for col in range(count)])
    for name, rows in (("turn_around", (1, 2)), ("zoom_turn", (3, 4))):
        extract(name, "pose", [(col*192, row*234+26, 192, 208)
                               for row in rows for col in range(8)])
    # Inspected transparent gutters, explicit boundaries rather than width // 4.
    xs, ys = (0, 450, 894, 1342, 1774), (0, 450, 887)
    extract("sleep", "sleep", [(xs[c], ys[r], xs[c+1]-xs[c], ys[r+1]-ys[r])
                                for r in range(2) for c in range(4)])
    frames = {}
    for name, images in processed.items():
        valid = [(im, rec) for im, rec in zip(images, records[name]) if rec["bbox"]]
        if not valid:
            frames[name] = []
            continue
        anchors = []
        for image, rec in valid:
            left, top, right, bottom = rec["bbox"]
            points = pixels(image)
            # Register the lower torso, not the ears/tail or whole alpha centroid.
            band_top = bottom - (bottom-top) * (0.45 if name.startswith("walk") else 0.30)
            band_bottom = bottom - (bottom-top) * 0.12
            band = [x for x, y in points if band_top <= y <= band_bottom]
            center = median(band) if band else (left+right)/2
            # Lower body contact ignores sparse shadows/whiskers.
            rows = {}
            for x, y in points:
                if abs(x-center) < (right-left)*0.28:
                    rows[y] = rows.get(y, 0)+1
            baseline = max((y for y, count in rows.items() if count >= (right-left)*0.12), default=bottom-1)
            if name.startswith("walk"):
                # Back/torso registration: tucked feet are not a ground anchor.
                # A fixed torso strip excludes both the raised tail and head.
                back = [min(y for x, y in points if x == xx) for xx in range(75, 116)]
                # Calibrated back-to-ground distance of the planted poses.
                baseline = median(back) + (83 if name == "walk_right" else 84)
                center = 96
            anchors.append((center, baseline))
        limit = (174, 132) if name == "sleep" or name.startswith("walk") else (128, 158)
        included = [rec for _, rec in valid if not rec["excluded"]]
        scale = min(limit[0] / max(rec["bbox"][2]-rec["bbox"][0] for rec in included),
                    limit[1] / max(rec["bbox"][3]-rec["bbox"][1] for rec in included))
        # Also reserve space for all registered extents, including the jump arc.
        scale = min(scale, *[(94 / max(ax-rec["bbox"][0], rec["bbox"][2]-ax, 1))
                              for (_, rec), (ax, ay) in zip(valid, anchors) if not rec["excluded"]])
        frames[name] = []
        for (image, rec), (ax, ay) in zip(valid, anchors):
            index = rec["source_index"]
            dy = (0, -12, -28, -18, 0)[index] if name == "bounce" else 0
            # Keep a small explicit gait bob; never derive scale from each frame.
            if name.startswith("walk"):
                dy = (0, 1, -1, 0, 0, 1, -1, 0)[index]
            tx, ty = ANCHOR[0]-ax*scale, ANCHOR[1]-ay*scale+dy
            canvas = QImage(*CANVAS, QImage.Format.Format_ARGB32)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.translate(tx, ty)
            painter.scale(scale, scale)
            painter.drawImage(0, 0, image)
            painter.end()
            rec.update(anchor=[ax, ay], scale=scale, translation=[tx, ty], bob=dy)
            rec["processed_bbox"] = bounds(pixels(canvas))
            if not rec["excluded"]:
                frames[name].append(QPixmap.fromImage(canvas))
    return frames, raw, records, sheets


def export_review(directory, library):
    frames, raw, records, sheets = library
    frames, raw, records = dict(frames), dict(raw), dict(records)
    if frames.get("sleep"):
        breathing = make_sleep_loop(frames["sleep"][0])
        frames["sleep_breathing"] = breathing
        raw["sleep_breathing"] = [frame.toImage() for frame in breathing]
        records["sleep_breathing"] = [dict(source="sleep source 1", source_index=i,
            bbox=bounds(pixels(frame.toImage())), excluded=None, duration_ms=SLEEP_TICK_MS,
            generated="floor-anchored breath, horizontal scale fixed; vertical stretch 1.000 to 1.018")
            for i, frame in enumerate(breathing)]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, images in raw.items():
        for kind, items in (("raw", images), ("aligned", frames[name])):
            contact = QImage(4*240, ((len(items)+3)//4)*240 or 240, QImage.Format.Format_ARGB32)
            contact.fill(QColor("#c7cdd2"))
            painter = QPainter(contact)
            for i, item in enumerate(items):
                image = item.toImage() if isinstance(item, QPixmap) else item
                x, y = (i % 4)*240, (i//4)*240
                display = image if kind == "aligned" else image.scaled(216, 208, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                painter.drawImage(x+(240-display.width())//2, y+24, display)
                painter.setPen(QColor("#303030"))
                rec = records[name][i] if kind == "raw" else [r for r in records[name] if r["bbox"] and not r["excluded"]][i]
                painter.drawText(x+8, y+18, f'{name} source {rec["source_index"]+1} {rec["excluded"] or ""}')
                if kind == "aligned":
                    painter.setPen(QColor("#b72a52"))
                    painter.drawLine(x+120, y+24, x+120, y+232)
                    painter.drawLine(x+12, y+225, x+228, y+225)
                    image.save(str(directory / f"{name}_{rec['source_index']+1:02}.png"))
            painter.end()
            contact.save(str(directory / f"{name}_{kind}.png"))
    metadata = {n: dict(width=s.width(), height=s.height(), alpha=s.hasAlphaChannel()) for n, s in sheets.items()}
    (directory / "frames.json").write_text(json.dumps(dict(sheets=metadata, animations=records), indent=2), encoding="utf-8")
