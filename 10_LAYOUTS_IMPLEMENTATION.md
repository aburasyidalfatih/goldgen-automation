# 10 Layout Designs Implementation

## Overview
Sistem sekarang menggunakan 10 desain layout yang berbeda untuk setiap konten yang dihasilkan. Layout digunakan secara bergantian otomatis melalui sistem rotasi topic.

## 10 Layout Designs

### 1. CROSS-SECTION CUTAWAY (Potongan Melintang)
**Konsep:** Menampilkan irisan samping dari dasar sungai atau tanah.
**Fungsi:** Memperlihatkan apa yang terjadi di bawah permukaan air/tanah, seperti lapisan kerikil, batuan dasar (bedrock), dan bagaimana nugget emas terperangkap di celah-celah terdalam.
**Composition:** National Geographic style cross-section dengan water velocity, gravel layers, dan educational labels.

### 2. VISUAL CHECKLIST (SPLIT SCREEN) (Daftar Periksa Visual)
**Konsep:** Layar terbagi dua (Kiri vs Kanan).
**Fungsi:** Membandingkan secara langsung antara "Batuan Mandul" dengan "Batuan Berisi Emas". Efektif untuk mengajarkan identifikasi cepat.
**Composition:** Survivor Manual aesthetic dengan rough wood/dirt background, rugged illustration.

### 3. STEP-BY-STEP PROCESS (Proses Langkah-demi-Langkah)
**Konsep:** Alur vertikal atau horizontal yang menceritakan urutan kejadian.
**Fungsi:** Menjelaskan siklus geologi (emas lepas → erosi → sungai → endapan).
**Composition:** Vintage Field Guide aesthetic dengan aged parchment, hand-drawn scientific illustration.

### 4. FIELD SIGNS GRID (Grid Tanda Lapangan)
**Konsep:** Tampilan kotak-kotak (grid 2x2 atau 2x3).
**Fungsi:** Menampilkan foto close-up dari 4 indikator kunci secara bersamaan (Pasir Hitam, Karat Besi, Pecahan Kuarsa, Pyrite).
**Composition:** Dark Rock Macro style dengan extreme close-up, high contrast lighting.

### 5. THE GOLDEN PATH (Jalur Emas)
**Konsep:** Ilustrasi sungai dilihat dari atas (top-down view).
**Fungsi:** Menggunakan panah untuk menunjuk lokasi spesifik di mana arus melambat dan emas jatuh (tikungan dalam, belakang batu).
**Composition:** Detailed Diagrammatic style dengan split screen, arrows indicating flow.

### 6. THE MAGNIFYING GLASS (Kaca Pembesar) ✨ NEW
**Konsep:** Tampilan makro atau zoom ekstrem.
**Fungsi:** Fokus pada tekstur batuan atau butiran mineral yang sangat kecil. Melihat melalui kaca pembesar geologis untuk menemukan inklusi emas mikroskopis.
**Composition:** Extreme macro zoom dengan circular lens frame, ultra-detailed texture, microscopic gold inclusions.

### 7. BEFORE & AFTER (Sebelum & Sesudah) ✨ NEW
**Konsep:** Pemandangan lanskap yang terbagi untuk menunjukkan perubahan waktu.
**Fungsi:** Menunjukkan kondisi sungai normal vs setelah banjir besar, di mana lapisan tanah baru terbuka dan zona endapan emas berpindah.
**Composition:** Split vertical composition dengan clear dividing line, labeled sections, exposed bedrock comparison.

### 8. THE GEOLOGIST'S NOTEBOOK (Buku Catatan Geolog) ✨ NEW
**Konsep:** Gaya sketsa tangan dengan catatan tertulis.
**Fungsi:** Memberikan kesan otentik seperti jurnal lapangan. Gambar batuan atau tebing disertai panah, lingkaran, dan catatan tangan.
**Composition:** Hand-drawn field journal style dengan sketched illustrations, handwritten annotations, aged paper texture, coffee stains.

### 9. 3D BLOCK DIAGRAM (Diagram Blok 3D) ✨ NEW
**Konsep:** Potongan tanah berbentuk kubus isometrik.
**Fungsi:** Memberikan perspektif 3 dimensi yang jelas tentang kedalaman. Menunjukkan bagaimana urat emas (vein) menembus lapisan tanah dari permukaan hingga ke dalam bumi.
**Composition:** Isometric 3D cutaway block dengan earth layers, surface terrain, gold veins cutting through, technical illustration.

### 10. THE PROSPECTOR'S MAP (Peta Prospektor) ✨ NEW
**Konsep:** Peta kontur atau topografi dari atas.
**Fungsi:** Seperti peta harta karun teknis. Menunjukkan garis kontur lembah, aliran air, dan memberikan tanda "X" pada lokasi pengambilan sampel yang strategis.
**Composition:** Topographic map view dengan contour lines, elevation markers, stream lines, X marks, legend box, grid coordinates.

## Distribution

**Total Topics:** 50
**Layouts:** 10
**Distribution:** 5 topics per layout (perfectly balanced)

Setiap layout muncul tepat 5 kali dalam rotasi 50 topics, memastikan variasi visual yang konsisten.

## Rotation System

Layout digunakan secara otomatis melalui sistem rotasi topic:
- File state: `data/topic_state.json`
- Tracking: `current_topic_index` (0-49)
- Auto-increment setiap posting
- Loop kembali ke 0 setelah topic 49

## Example Next Posts

Berdasarkan current index (17), next posts akan menggunakan:
1. THE GEOLOGIST'S NOTEBOOK - GREENSTONE BELTS
2. 3D BLOCK DIAGRAM - SLATE BELTS
3. THE PROSPECTOR'S MAP - GLACIAL GOLD
4. CROSS-SECTION CUTAWAY - DESERT PROSPECTING
5. VISUAL CHECKLIST - BEACH PLACERS

## Files Modified

1. `goldgen_service.py` - Updated all 50 topics with new layout distribution
2. `update_compositions.py` - Script untuk update composition (one-time use)

## Testing

Test layout baru:
```bash
cd goldgen-automation
./venv/bin/python -c "
from goldgen_service import GoldGenService
import json

with open('data/config.json', 'r') as f:
    config = json.load(f)

service = GoldGenService(config['gemini_api_key'])
topic = service.get_next_topic()
print(f'Layout: {topic[\"layout\"]}')
print(f'Topic: {topic[\"headline\"]}')
"
```

## Implementation Date
23 Februari 2026, 16:47 WIB
