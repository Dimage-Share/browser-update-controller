import httpx, time, logging, asyncio

CHROME_API = "https://versionhistory.googleapis.com/v1/chrome/platform/win/channel/stable/version"
# Edge: 利用 API (公式 edgeupdates) - Stable 情報取得
EDGE_API = "https://edgeupdates.microsoft.com/api/products?channel=Stable&platform=Windows"


class VersionService:

    def __init__(self):
        self.cache = {}
        self.ttl = 60 * 30  # 30分
        self.last_fetch = 0

    async def fetch(self):
        now = time.time()
        if self.cache and now - self.last_fetch < self.ttl:
            return self.cache
        async with httpx.AsyncClient(timeout=15) as client:
            # Chrome
            cr = await client.get(CHROME_API)
            cr.raise_for_status()
            cjson = cr.json()
            chrome_latest = cjson["versions"][0]["version"]
            # Edge
            er = await client.get(EDGE_API)
            er.raise_for_status()
            ejson = er.json()
            # 安定版バージョン探索（製品構造簡易化）
            edge_latest = None
            for item in ejson:
                # item ごとに 'Product' や 'Releases' がある構造
                if 'Product' in item and item['Product'].lower() == 'stable':
                    for rel in item.get('Releases', []):
                        if rel.get("Platform", "").lower() == "windows":
                            edge_latest = rel.get("ProductVersion")
                            break
                if edge_latest:
                    break
            if not edge_latest:
                # fallback: 先頭候補検索
                for item in ejson:
                    if 'Releases' in item:
                        for rel in item['Releases']:
                            if rel.get("ProductVersion"):
                                edge_latest = rel["ProductVersion"]
                                break
                        if edge_latest:
                            break
            if not edge_latest:
                raise RuntimeError("Edge latest version not resolved")

        self.cache = {
            "chrome": {
                "latestStable": chrome_latest,
                "latestStableMajor": int(chrome_latest.split(".")[0]),
                "nextStableMajorGuess": int(chrome_latest.split(".")[0]) + 1
            },
            "edge": {
                "latestStable": edge_latest,
                "latestStableMajor": int(edge_latest.split(".")[0]),
                "nextStableMajorGuess": int(edge_latest.split(".")[0]) + 1
            }
        }
        self.last_fetch = now
        logging.info(f"Fetched versions: {self.cache}")
        return self.cache


version_service = VersionService()
