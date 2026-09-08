import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import motion_qa, motion_studio, motion_tts


class FakePart:
    def __init__(self, data):
        self.inline_data = SimpleNamespace(data=data)


def fake_response(data=b'PCMDATA'):
    content = SimpleNamespace(parts=[FakePart(data)])
    return SimpleNamespace(audio=None, candidates=[SimpleNamespace(content=content)])


class VoiceoverPathTests(unittest.TestCase):
    """The installed SDK exposes .interactions, but the API rejects that
    schema, so preferring it silently disabled voice-over entirely."""

    def _client(self, generate_content):
        client = SimpleNamespace()
        client.models = SimpleNamespace(generate_content=generate_content)
        client.interactions = SimpleNamespace(
            create=lambda **kwargs: self.fail('interactions must not be tried first'))
        return client

    def test_generate_content_is_used_even_when_interactions_exists(self):
        calls = []

        def generate_content(**kwargs):
            calls.append(kwargs['model'])
            return fake_response()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(motion_tts, 'MOTION_RENDERS_DIR', Path(temp_dir)), \
                    patch.object(motion_tts, '_configured_api_key', return_value='k'), \
                    patch('google.genai.Client', return_value=self._client(generate_content)):
                path = motion_tts.generate_voiceover('job1', 'hello')
            self.assertTrue(Path(path).is_file())
        self.assertEqual(1, len(calls))

    def test_failure_reports_the_underlying_reason(self):
        def generate_content(**kwargs):
            raise RuntimeError('400 legacy schema no longer supported')

        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        with patch.object(motion_tts, '_configured_api_key', return_value='k'), \
                patch('google.genai.Client', return_value=client):
            with self.assertRaises(RuntimeError) as ctx:
                motion_tts.generate_voiceover('job2', 'hello')
        # The old message hid the cause behind "did not return audio".
        self.assertIn('legacy schema', str(ctx.exception))


class AudioQualityGateTests(unittest.TestCase):
    def _probe(self, streams):
        return {'ok': True, 'data': {'streams': streams}, 'errors': []}

    VIDEO = {'codec_type': 'video', 'width': 1080, 'height': 1920, 'duration': '60.0'}

    def _validate(self, streams, expect_audio):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            video = base / 'v.mp4'
            video.write_bytes(b'0' * 2048)
            manifest = base / 'v.manifest.json'
            manifest.write_text('{}', encoding='utf-8')
            (base / 'v.srt').write_text('1\n', encoding='utf-8')
            with patch.object(motion_qa, 'inspect_media', return_value=self._probe(streams)):
                return motion_qa.validate_render(video, manifest, expect_audio=expect_audio)

    def test_silent_video_is_allowed_when_no_voiceover_was_made(self):
        result = self._validate([self.VIDEO], expect_audio=False)
        self.assertTrue(result['ok'])
        self.assertFalse(result['has_audio'])

    def test_missing_audio_fails_when_a_voiceover_exists(self):
        result = self._validate([self.VIDEO], expect_audio=True)
        self.assertFalse(result['ok'])
        self.assertTrue(any('Voice-over' in e for e in result['errors']))

    def test_audio_track_satisfies_the_gate(self):
        result = self._validate([self.VIDEO, {'codec_type': 'audio'}], expect_audio=True)
        self.assertTrue(result['ok'])
        self.assertTrue(result['has_audio'])


class TopicCatalogTests(unittest.TestCase):
    def test_motion_studio_only_offers_curated_topics(self):
        topics = [{'id': 1, 'headline': 'KEEP'}, {'id': 2, 'headline': 'DROP'}]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'topics.json'
            path.write_text(json.dumps(topics), encoding='utf-8')
            with patch.object(motion_studio, 'TOPICS_PATH', path), \
                    patch('core.topic_catalog.allowed', side_effect=lambda t: t['id'] == 1):
                offered = motion_studio.list_topics()
        self.assertEqual([1], [t['id'] for t in offered])


if __name__ == '__main__':
    unittest.main()
