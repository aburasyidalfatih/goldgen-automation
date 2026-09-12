import unittest
from core.comment_filter import is_promotional_spam


class CommentFilterTests(unittest.TestCase):
    def test_decorative_promotions(self):
        self.assertTrue(is_promotional_spam('Super bagus 𝗕𝗨𝗔𝗬𝗔𝗧𝗢𝗧𝗢'))
        self.assertTrue(is_promotional_spam('Bonus 𝐊𝐈𝐍𝐆𝐇𝐎𝐊𝐈𝟒𝐃'))

    def test_real_questions_and_criticism_survive(self):
        for text in ['How do I sample a gold deposit?', 'Hahaha trash ai as always',
                     'Gold is not 20 times denser than river rock.', 'Is this a jackpot?']:
            self.assertFalse(is_promotional_spam(text))
