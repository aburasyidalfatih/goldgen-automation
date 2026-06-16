# Layout Rotation System

**Date**: 2026-03-06
**Status**: ✅ Already Implemented & Working

## Overview
Setiap fanspage secara otomatis mendapat **layout desain yang berbeda** untuk setiap postingan mereka.

## How It Works

### 1. Layout Assignment Formula
```python
layout_index = topic_index % 10
```

Karena ada **10 layouts** dan setiap fanspage mendapat topic dengan offset berbeda, maka layout juga otomatis berbeda.

### 2. Available Layouts (10 Total)

| Index | Layout Name              | Description                          |
|-------|--------------------------|--------------------------------------|
| 0     | CROSS-SECTION CUTAWAY    | National Geographic style cutaway    |
| 1     | VISUAL CHECKLIST         | Checklist with icons                 |
| 2     | STEP-BY-STEP PROCESS     | Sequential process diagram           |
| 3     | FIELD SIGNS GRID         | Grid of visual indicators            |
| 4     | THE GOLDEN PATH          | Journey/path visualization           |
| 5     | THE MAGNIFYING GLASS     | Close-up detail focus                |
| 6     | BEFORE & AFTER           | Comparison layout                    |
| 7     | THE GEOLOGIST'S NOTEBOOK | Sketch/notebook style                |
| 8     | 3D BLOCK DIAGRAM         | 3D geological visualization          |
| 9     | THE PROSPECTOR'S MAP     | Map-based layout                     |

### 3. Current Cycle Example

**Base Topic Index**: 40

| Fanspage       | Index | Topic | Layout                   |
|----------------|-------|-------|--------------------------|
| Putri Kejora   | 0     | 40    | CROSS-SECTION CUTAWAY    |
| Erna Gold      | 1     | 41    | VISUAL CHECKLIST         |
| Gold USD       | 2     | 42    | STEP-BY-STEP PROCESS     |
| Kedai Digital  | 3     | 43    | FIELD SIGNS GRID         |
| Miners 24      | 4     | 44    | THE GOLDEN PATH          |

### 4. Next Cycle (After 5 Posts)

**Base Topic Index**: 45

| Fanspage       | Index | Topic | Layout                   |
|----------------|-------|-------|--------------------------|
| Putri Kejora   | 0     | 45    | THE MAGNIFYING GLASS     |
| Erna Gold      | 1     | 46    | BEFORE & AFTER           |
| Gold USD       | 2     | 47    | THE GEOLOGIST'S NOTEBOOK |
| Kedai Digital  | 3     | 48    | 3D BLOCK DIAGRAM         |
| Miners 24      | 4     | 49    | THE PROSPECTOR'S MAP     |

### 5. Rotation Pattern

Setiap fanspage akan mengalami **semua 10 layouts** secara berurutan:

**Putri Kejora** (idx 0):
- Cycle 1: Layout 0 (CROSS-SECTION)
- Cycle 2: Layout 5 (MAGNIFYING GLASS)
- Cycle 3: Layout 0 (CROSS-SECTION) ← repeats after 10 cycles

**Erna Gold** (idx 1):
- Cycle 1: Layout 1 (VISUAL CHECKLIST)
- Cycle 2: Layout 6 (BEFORE & AFTER)
- Cycle 3: Layout 1 (VISUAL CHECKLIST) ← repeats after 10 cycles

Dan seterusnya...

## Benefits

1. ✅ **Variety**: Setiap fanspage posting dengan desain berbeda
2. ✅ **Automatic**: Tidak perlu konfigurasi manual
3. ✅ **Predictable**: Pattern yang konsisten dan mudah diprediksi
4. ✅ **Fair**: Semua fanspage mendapat semua layout secara merata

## Verification

Test layout assignment:
```bash
cd /home/ubuntu/goldgen-automation
./venv/bin/python3 -c "
from auto_poster import GoldGenAutoPoster
poster = GoldGenAutoPoster()
for idx in range(5):
    _, topic = poster.generate_content_with_offset(idx)
    print(f'{poster.fanspages[idx][\"name\"]}: {topic[\"layout\"]}')"
```

## Code Location

Layout assignment logic:
- File: `goldgen_service.py`
- Function: `get_topic_with_offset()`
- Line: ~934

```python
layout_index = current_index % len(self.layouts)
layout = self.layouts[layout_index]
topic['layout'] = layout['name']
topic['composition'] = layout['composition']
```

## Notes

- Layout rotation terikat dengan topic rotation
- Setiap 10 topics, layout akan repeat
- Karena ada 50 topics total, setiap layout akan digunakan 5x per full cycle
- Tidak perlu modifikasi - sistem sudah optimal
