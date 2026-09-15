import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from core.layout_design import DESIGNS, poster_prompt, execution
from core.poster_renderer import compose_poster, stamp_watermark, draw_text_box, WIDTH, HEIGHT
from core.visual_plan import fallback_plan


class LayoutDesignTests(unittest.TestCase):
    def test_every_catalog_layout_has_an_exact_design(self):
        names={x['name'] for x in json.loads(Path('data/layouts.json').read_text())}
        self.assertEqual(names,set(DESIGNS))
        vector=execution({'layout':'MODERN VECTOR'})
        self.assertIn('FLAT VECTOR',vector)
        self.assertNotIn('Clean, technical, high-resolution photography',vector)

    def test_no_layout_trips_the_preflight_filter_with_its_own_words(self):
        """THE PROSPECTOR'S MAP dulu memuat frasa "guaranteed deposits".

        Frasa itu persis salah satu istilah yang dipindai _preflight_image_plan,
        jadi layout itu menjegal dirinya sendiri: arahan seni ditolak, prompt
        dasar ditolak, jatuh ke poster PIL, lalu ditahan gerbang publikasi.
        Setiap postingan pada layout itu gagal total, tanpa satu pun pesan yang
        menyebut bahwa penyebabnya adalah deskripsi layout itu sendiri.
        """
        from core.content_quality import FORBIDDEN_IMAGE_TERMS
        for name in DESIGNS:
            teks = execution({'layout': name}).lower()
            kena = [t for t in FORBIDDEN_IMAGE_TERMS if t in teks]
            self.assertEqual([], kena, f'{name} memuat {kena}')

    def test_poster_prompt_asks_the_model_to_render_the_approved_copy(self):
        """Pemilik memilih model gambar yang menyusun seluruh tipografi.

        Perjanjian lama justru kebalikannya ("NO TEXT anywhere"), jadi kalau
        kalimat itu muncul lagi, dua arahan yang bertentangan akan dikirim
        bersamaan dan model memilih salah satu secara acak.
        """
        topic={'layout':'MODERN INDUSTRIAL','headline':'READ THE CONTACTS',
               'subtitle':'Gold hates a smooth ride.','list_header':'FIELD SIGNS',
               'list_points':['Target the seam','Follow the iron']}
        p=poster_prompt(topic,{})
        self.assertIn('READ THE CONTACTS',p)
        self.assertIn('Gold hates a smooth ride.',p)
        self.assertIn('- Target the seam',p)
        self.assertNotIn('NO TEXT anywhere',p)
        self.assertIn('only if the caption actually discusses it',p)

    def test_poster_prompt_protects_the_headline_from_the_feed_crop(self):
        """Judul di luar area 4:5 tidak pernah terlihat sebelum orang mengetuk,
        padahal judul itulah yang membuat orang mengetuk."""
        p=poster_prompt({'layout':'CROSS-SECTION CUTAWAY','headline':'X'},{})
        self.assertIn('middle 4:5',p)

    def test_every_layout_builds_a_poster_prompt(self):
        for name in DESIGNS:
            p=poster_prompt({'layout':name,'headline':'X','list_points':['a']},{})
            self.assertIn('MANDATORY ART DIRECTION',p,name)

    def test_all_layout_fallbacks_fit_long_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in DESIGNS:
                topic={'layout':name,'headline':'Reading the geological evidence before choosing sampling locations'}
                plan=fallback_plan(topic)
                plan['fallback_points']=['Compare visible evidence and record observations before interpreting the sample. '*2]*4
                output=Path(tmp)/'poster.png'
                boxes=compose_poster(plan,output,'GoldGen field guide')
                with Image.open(output) as im:self.assertEqual((WIDTH,HEIGHT),im.size)
                self.assertTrue(all(b['font_size']>=20 for b in boxes))
                self.assertTrue(all(0<=b['box'][0]<b['box'][2]<=WIDTH and 0<=b['box'][1]<b['box'][3]<=HEIGHT for b in boxes))

    def test_watermark_stamping_keeps_the_generated_poster_intact(self):
        """Hanya watermark yang ditambahkan. Menimpakan tipografi PIL di atas
        poster yang sudah bertekst akan mencetak judulnya dua kali."""
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'image.png';Image.new('RGB',(1152,2048),'red').save(path)
            stamp_watermark(path,path,'Miners 24')
            with Image.open(path) as im:
                self.assertEqual((WIDTH,HEIGHT),im.size)
                self.assertEqual((255,0,0),im.getpixel((720,900)))
                self.assertEqual((255,0,0),im.getpixel((WIDTH-100,HEIGHT-70)))
                self.assertNotEqual((255,0,0),im.getpixel((100,HEIGHT-74)))

    def test_long_unbroken_word_wraps_inside_bounds(self):
        draw=ImageDraw.Draw(Image.new('RGB',(400,600)))
        result=draw_text_box(draw,'LongWord'*20,(10,10,390,590),40,'black')
        self.assertGreater(len(result['lines']),1)
