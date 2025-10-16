import os
from datetime import datetime, timedelta
from .version_service import version_service
import logging


def env_bool(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


class BrowserConfigState:

    def __init__(self):
        self.data = {
            "chrome": {
                "stable_target_major":
                int(os.getenv("CHROME_STABLE_TARGET_MAJOR", "130")),
                "min_version":
                os.getenv("CHROME_MIN_VERSION", ""),
                "approved_at":
                datetime.utcnow()
            },
            "edge": {
                "stable_target_major":
                int(os.getenv("EDGE_STABLE_TARGET_MAJOR", "130")),
                "min_version":
                os.getenv("EDGE_MIN_VERSION", ""),
                "approved_at":
                datetime.utcnow()
            }
        }
        self.grace_days = int(os.getenv("GRACE_DAYS_STABLE_MAJOR", "3"))
        self.auto_promote = env_bool("AUTO_PROMOTE")

    async def build_config(self, browser: str, ring: str,
                           auto_update_check_minutes: int):
        versions = await version_service.fetch()
        if browser not in versions:
            raise ValueError("Unsupported browser")
        latest = versions[browser]
        target_major = self.data[browser]["stable_target_major"]
        if ring == "fast":
            prefix = ""  # 最新許容
        else:
            prefix = f"{target_major}."
        return {
            "browser": browser,
            "ring": ring,
            "targetVersionPrefix": prefix,
            "minVersion": self.data[browser]["min_version"],
            "latestStable": latest["latestStable"],
            "latestStableMajor": latest["latestStableMajor"],
            "nextStableMajor": latest["nextStableMajorGuess"],
            "policy": {
                "autoUpdateCheckMinutes": auto_update_check_minutes,
                "graceDaysForStableMajor": self.grace_days
            },
            "approvedAt": self.data[browser]["approved_at"].isoformat() + "Z"
        }

    async def maybe_auto_promote(self):
        if not self.auto_promote:
            return
        versions = await version_service.fetch()
        for browser, latest in versions.items():
            if latest["latestStableMajor"] > self.data[browser][
                    "stable_target_major"]:
                if datetime.utcnow(
                ) - self.data[browser]["approved_at"] > timedelta(
                        days=self.grace_days):
                    self.data[browser]["stable_target_major"] = latest[
                        "latestStableMajor"]
                    self.data[browser]["approved_at"] = datetime.utcnow()
                    logging.info(
                        f"Auto-promoted {browser} -> {latest['latestStableMajor']}"
                    )

    def approve(self, browser: str, major: int):
        if major > self.data[browser]["stable_target_major"]:
            self.data[browser]["stable_target_major"] = major
            self.data[browser]["approved_at"] = datetime.utcnow()
            return True
        return False


config_state = BrowserConfigState()
