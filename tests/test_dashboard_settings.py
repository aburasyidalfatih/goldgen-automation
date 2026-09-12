import unittest
from pathlib import Path


class DashboardSettingsTests(unittest.TestCase):
    def test_settings_form_only_reads_controls_that_exist(self):
        template = (
            Path(__file__).parents[1] / "templates" / "dashboard_schedule.html"
        ).read_text(encoding="utf-8")

        removed_control_ids = (
            "settingsIgEnabled",
            "settingsTwApiKey",
            "settingsPinToken",
            "settingsThreadsToken",
        )
        for control_id in removed_control_ids:
            self.assertNotIn(control_id, template)

        self.assertIn("showSettingsToast('Settings berhasil disimpan.'", template)
        self.assertIn("saveButton.disabled = true", template)


if __name__ == "__main__":
    unittest.main()
