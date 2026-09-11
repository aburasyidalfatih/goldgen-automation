import unittest
from core.manual_content_analysis import validate_analysis


class AnalysisValidationTests(unittest.TestCase):
    def test_valid_and_unknown_layout(self):
        for layout in ('UNKNOWN','CROSS-SECTION CUTAWAY'):
            data=dict(layout=layout,topic='Bedrock traps',confidence=0.9,
                      text_density='high',readability='poor')
            self.assertEqual(validate_analysis(data),data)

    def test_invalid_model_output_rejected(self):
        base=dict(layout='UNKNOWN',topic='Bedrock traps',confidence=0.9,
                  text_density='low',readability='good')
        for key,value in [('layout','VIRAL'),('confidence',True),('confidence',float('nan')),
                          ('topic',''),('readability','perfect'),('text_density',3)]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                validate_analysis(dict(base,**{key:value}))
