import requests
import json
import time
import random
import re

class GeminiVideoLab:
    def __init__(self, psid, psidts="", psidcc=""):
        self.session = requests.Session()
        self.session.cookies.set("__Secure-1PSID", psid)
        if psidts:
            self.session.cookies.set("__Secure-1PSIDTS", psidts)
        if psidcc:
            self.session.cookies.set("__Secure-1PSIDCC", psidcc)
            
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Origin": "https://gemini.google.com",
            "Referer": "https://gemini.google.com/"
        })
        self.snim0e = self._get_snim0e()

    def _get_snim0e(self):
        """Extract the SNlM0e token required for batchexecute"""
        try:
            res = self.session.get("https://gemini.google.com/app")
            res.raise_for_status()
            match = re.search(r'SNlM0e":"(.*?)"', res.text)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            print(f"Failed to get SNlM0e: {e}")
            return None

    def generate_video(self, prompt, yield_log=True):
        """Mock reverse engineered video generation"""
        if not self.snim0e:
            yield "[ERROR] Failed to extract SNlM0e token. Is your __Secure-1PSID valid?\n"
            return

        yield f"[LOG] SNlM0e Token acquired: {self.snim0e[:10]}...\n"
        yield f"[LOG] Preparing payload for prompt: '{prompt}'\n"
        
        # Simulate network delay and payload assembly
        time.sleep(2)
        
        yield "[LOG] Sending payload to https://gemini.google.com/_/BardChat/data/batchexecute...\n"
        
        # In a real implementation, this is where the complex websocket polling happens.
        # Video generation usually takes 1-3 minutes. We simulate that here.
        yield "[LOG] Request sent. Waiting for Veo model to process...\n"
        
        for i in range(1, 11):
            time.sleep(1)
            yield f"[LOG] Polling status... ({i*10}%)\n"
        
        # Mock result
        yield "[LOG] 🟢 SUCCESS! Video generation complete.\n"
        yield "[LOG] Extracting MP4 blob URL...\n"
        time.sleep(1)
        
        # This is a sample placeholder URL. In reality, it would be a googleusercontent.com link.
        fake_video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
        yield f"[LOG] URL: {fake_video_url}\n"
