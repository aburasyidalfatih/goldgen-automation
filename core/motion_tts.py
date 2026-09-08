"""Gemini TTS adapter for Motion Studio.

Voice generation is opt-in and isolated from the existing image generation
flow. The adapter writes only inside motion_studio/renders.
"""

import os
import base64
import json
import wave
from pathlib import Path

from core.motion_studio import MOTION_RENDERS_DIR
from core.config import CONFIG_PATH


def _write_wav(path: Path, pcm: bytes, channels=1, rate=24000, sample_width=2):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(rate)
        output.writeframes(pcm)


def _configured_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    if CONFIG_PATH.is_file():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return config.get("gemini_api_key") or config.get("gemini_api_key_value")
        except (OSError, ValueError):
            return None
    return None


def generate_voiceover(job_id, text, voice_name="Kore", model=None):
    api_key = _configured_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum dikonfigurasi")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Paket google-genai belum tersedia") from exc

    client = genai.Client(api_key=api_key)
    selected_model = model or os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

    # Urutannya sengaja: generate_content DULU, interactions hanya cadangan.
    #
    # Sebelumnya kebalikannya, dipilih lewat `hasattr(client, "interactions")`.
    # Atribut itu memang ada pada google-genai 1.73.1 yang terpasang, tapi
    # servernya menolak skemanya: "The legacy Interactions API schema is no
    # longer supported ... upgrade to >= 2.0.0". Jadi setiap panggilan berakhir
    # HTTP 400 dan cabang yang benar tidak pernah tereksekusi — voice-over
    # Motion Studio tidak pernah sekali pun berhasil dibuat.
    #
    # Diuji langsung pada SDK yang terpasang: generate_content mengembalikan
    # 159.886 byte audio. Tidak perlu menaikkan versi SDK.
    pcm = None
    kegagalan = []
    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                    )
                ),
            ),
        )
        pcm = getattr(response, "audio", None)
        if not pcm and getattr(response, "candidates", None):
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    pcm = part.inline_data.data
                    break
    except Exception as exc:  # noqa: BLE001 - alasannya dilaporkan di bawah
        kegagalan.append(f"generate_content: {type(exc).__name__}: {exc}")

    if not pcm and hasattr(client, "interactions"):
        try:
            interaction = client.interactions.create(
                model=selected_model,
                input=text,
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice_name}]},
            )
            encoded = getattr(getattr(interaction, "output_audio", None), "data", None)
            if encoded:
                pcm = base64.b64decode(encoded)
        except Exception as exc:  # noqa: BLE001
            kegagalan.append(f"interactions: {type(exc).__name__}: {exc}")

    if not pcm:
        # Sebutkan alasan aslinya. Pesan "tidak mengembalikan audio" saja
        # menyembunyikan HTTP 400 yang justru menjelaskan semuanya.
        rincian = ' | '.join(kegagalan) if kegagalan else 'tidak ada audio pada respons'
        raise RuntimeError(f"Gemini TTS gagal — {rincian}"[:600])
    output = MOTION_RENDERS_DIR / f"{job_id}.wav"
    _write_wav(output, pcm)
    return str(output)
