# GoldGen Educational Content Generator

## Overview
Sistem ini telah diubah dari **posting harga emas** menjadi **konten edukasi tentang gold prospecting** dengan sistem rotasi 10 topik.

## Model AI yang Digunakan

### Caption Generation
- **Model**: `gemini-3.1-pro-preview`
- **Fungsi**: Generate caption edukasi dalam bahasa Inggris
- **Provider**: Google Gemini

### Image Generation
- **Model**: `gemini-3-pro-image-preview` (Nano Banana Pro)
- **Fungsi**: Generate infographic 4K dengan text rendering
- **Provider**: Google Gemini
- **Features**: 4K resolution, advanced text rendering, multimodal processing

## Topik yang Dirotasi

1. **Reading the River** - Inside bends & drop zones
2. **Bedrock Traps** - Natural gold traps
3. **Quartz Indicators** - Rusty vs bull quartz
4. **Iron Staining** - The red flag of gold
5. **Black Sand Secrets** - Heavy mineral indicators
6. **Gold vs Pyrite** - The shatter test
7. **Ancient Channels** - High bench deposits
8. **Placer vs Lode** - Tracking the source
9. **Ruby Companions** - Garnets & gold
10. **False Bedrock** - Clay layer secrets

## Cara Kerja

### Sistem Rotasi
- Setiap kali posting, sistem akan mengambil topik berikutnya secara berurutan (1→2→3...→10→1)
- State disimpan di `data/topic_state.json`
- Setelah topik 10, akan kembali ke topik 1

### Format Konten
- **Caption**: Educational text dalam bahasa Inggris dengan hashtag gold prospecting
- **Image**: Vertical infographic (1080x1920) dengan style National Geographic / Field Guide

### Gaya Visual
Setiap topik memiliki gaya visual berbeda:
- National Geographic Cross-Section
- Survivor Manual
- Vintage Field Guide
- Dark Rock Macro
- Detailed Diagrammatic

## Testing

### Lihat Prompt yang Dihasilkan
```bash
cd /home/ubuntu/goldgen-automation
source venv/bin/activate
python3 test_prompts.py
```

### Test Generate Content
```bash
python3 -c "
from goldgen_service import GoldGenService
import os
os.environ['GEMINI_API_KEY'] = 'your-key'
gs = GoldGenService('your-key')
topic = gs.get_next_topic()
print(f'Topic: {topic[\"headline\"]}')
print(gs.generate_image_prompt(topic))
"
```

## Files Modified

1. **goldgen_service.py** - Core service dengan 10 topik dan prompt generator
2. **auto_poster.py** - Updated untuk menggunakan topik edukasi
3. **test_prompts.py** - Script untuk testing prompt

## Backup

File lama disimpan di:
- `auto_poster.py.backup`

## Dashboard

Akses dashboard di: https://gold.kelasmaster.id

Dashboard masih menampilkan statistik posting (total, success rate, dll) tapi kontennya sudah berubah menjadi edukasi gold prospecting.

## Next Steps

1. Test posting manual dengan `python3 auto_poster.py`
2. Cek hasil di Facebook fanspage
3. Monitor dashboard untuk statistik
4. Adjust prompt jika perlu untuk hasil yang lebih baik
