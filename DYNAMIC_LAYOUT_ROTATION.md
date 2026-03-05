# Dynamic Layout Rotation - Implementation

## Update: 23 Feb 2026, 16:52 WIB

## Changes

### Before
- Layout hardcoded di setiap topic
- Layout sama digunakan untuk 5 topics berturut-turut
- Perlu 50 posting untuk melihat semua 10 layouts

### After ✅
- Layout assigned dinamis berdasarkan topic index
- **Layout berganti setiap topik**
- Setiap 10 posting, layout cycle lengkap

## How It Works

```
Topic Index → Layout Index (modulo 10)

Topic 0  → Layout 0 (CROSS-SECTION CUTAWAY)
Topic 1  → Layout 1 (VISUAL CHECKLIST)
Topic 2  → Layout 2 (STEP-BY-STEP PROCESS)
...
Topic 9  → Layout 9 (THE PROSPECTOR'S MAP)
Topic 10 → Layout 0 (CROSS-SECTION CUTAWAY)  ← Loop
Topic 11 → Layout 1 (VISUAL CHECKLIST)
...
```

## Formula

```python
layout_index = topic_index % 10
```

## Example Sequence

```
Post 1: Topic 21 → Layout 1 [VISUAL CHECKLIST]
Post 2: Topic 22 → Layout 2 [STEP-BY-STEP PROCESS]
Post 3: Topic 23 → Layout 3 [FIELD SIGNS GRID]
Post 4: Topic 24 → Layout 4 [THE GOLDEN PATH]
Post 5: Topic 25 → Layout 5 [THE MAGNIFYING GLASS]
Post 6: Topic 26 → Layout 6 [BEFORE & AFTER]
Post 7: Topic 27 → Layout 7 [THE GEOLOGIST'S NOTEBOOK]
Post 8: Topic 28 → Layout 8 [3D BLOCK DIAGRAM]
Post 9: Topic 29 → Layout 9 [THE PROSPECTOR'S MAP]
Post 10: Topic 30 → Layout 0 [CROSS-SECTION CUTAWAY]  ← Loop back
```

## Implementation Details

### 1. Layouts Array
Layouts sekarang disimpan terpisah di `self.layouts[]` dengan 10 entries:
- name
- composition

### 2. Topics Array
Topics hanya berisi content data:
- headline
- subtitle
- list_header
- list_points

**Tidak ada** field `layout` atau `composition` yang hardcoded.

### 3. Dynamic Assignment
Method `get_next_topic()` melakukan:
1. Ambil topic berdasarkan current_index
2. Hitung layout_index = current_index % 10
3. Assign layout dan composition secara dinamis
4. Return topic yang sudah lengkap

## Benefits

✅ Layout berganti setiap posting (bukan setiap 5 posting)
✅ Lebih mudah maintain (layouts terpisah dari topics)
✅ Cycle lengkap hanya 10 posting (bukan 50)
✅ Variasi visual lebih cepat terlihat

## Testing

```bash
cd goldgen-automation
./venv/bin/python -c "
from auto_poster import GoldGenAutoPoster

poster = GoldGenAutoPoster()

for i in range(3):
    caption, topic = poster.generate_content()
    print(f'{i+1}. {topic[\"layout\"]} - {topic[\"headline\"]}')
"
```

## Files Modified

- `goldgen_service.py` - Added layouts array, updated get_next_topic()
- `auto_poster.py` - Fixed fallback to use get_next_topic()

## Result

Setiap posting sekarang menggunakan layout yang berbeda, memberikan variasi visual maksimal untuk audience.
