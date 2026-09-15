import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from core.layout_design import DESIGNS, artwork_prompt, execution
from core.poster_renderer import compose_poster, draw_text_box, WIDTH, HEIGHT
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

    def test_artwork_prompt_does_not_instruct_the_model_to_typeset(self):
        p=artwork_prompt({'layout':'MODERN INDUSTRIAL','headline':'River deposits'}, {'labels':['Black sand']})
        self.assertIn('NO TEXT anywhere',p)
        self.assertIn('only if the caption actually discusses it',p)

    def test_all_layout_fallbacks_fit_long_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in DESIGNS:
                topic={'layout':name,'headline':'Reading the geological evidence before choosing sampling locations'}
                plan=fallback_plan(topic)
                plan['fallback_points']=['Compare visible evidence and record observations before interpreting the sample. '*2]*4
                output=Path(tmp)/'poster.png'
                boxes=compose_poster(None,plan,output,'GoldGen field guide')
                with Image.open(output) as im:self.assertEqual((WIDTH,HEIGHT),im.size)
                self.assertTrue(all(b['font_size']>=20 for b in boxes))
                self.assertTrue(all(0<=b['box'][0]<b['box'][2]<=WIDTH and 0<=b['box'][1]<b['box'][3]<=HEIGHT for b in boxes))

    def test_illustration_is_preserved_and_labels_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'image.png';Image.new('RGB',(800,1000),'red').save(path)
            plan=fallback_plan({'layout':'MODERN VECTOR','headline':'Gold movement'})
            plan['labels']=['Compacted sediment beneath the surface of the stream']*4
            compose_poster(path,plan,path)
            with Image.open(path) as im:self.assertEqual((255,0,0),im.getpixel((720,900)))

    def test_long_unbroken_word_wraps_inside_bounds(self):
        draw=ImageDraw.Draw(Image.new('RGB',(400,600)))
        result=draw_text_box(draw,'LongWord'*20,(10,10,390,590),40,'black')
        self.assertGreater(len(result['lines']),1)
