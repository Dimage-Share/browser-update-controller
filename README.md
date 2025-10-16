# Browser Update Controller (Chrome & Edge) - Google Chat 通知版

内部ネットワーク上で Chrome / Edge の:
- 最新 Stable バージョン監視 (Google / Microsoft 公式 API)
- fast / stable 段階的ロールアウト (TargetVersionPrefix)
- クライアント端末バージョン収集 / 可視化 / Google Chat 通知
を提供します。

エンドポイント: `http://172.16.162.172:6001`

## 主エンドポイント
| Method | Path                          | 説明                                                                         |
| ------ | ----------------------------- | ---------------------------------------------------------------------------- |
| GET    | /healthz                      | Liveness                                                                     |
| GET    | /config/{browser}/{ring}.json | 設定 (browser: chrome                                                        | edge) |
| POST   | /report                       | 端末報告 (Header: X-Auth-Token)                                              |
| POST   | /approve                      | メジャー承認 (Header: X-Admin-Token, JSON: {"browser":"chrome","major":131}) |
| GET    | /stats                        | 簡易集計                                                                     |
| GET    | /dashboard                    | 最近200件 HTML                                                               |

### 設定 JSON 例
```json
{
  "browser": "chrome",
  "ring": "stable",
  "targetVersionPrefix": "130.",
  "minVersion": "130.0.6723.58",
  "latestStable": "130.0.6723.91",
  "latestStableMajor": 130,
  "nextStableMajor": 131,
  "policy": {
    "autoUpdateCheckMinutes": 180,
    "graceDaysForStableMajor": 3
  },
  "approvedAt": "2025-10-16T07:00:00Z"
}
```

## 環境変数 (.env)
| 変数                       | 説明                                            |
| -------------------------- | ----------------------------------------------- |
| CONTROLLER_PORT            | 公開ポート (6001)                               |
| AUTH_TOKEN                 | クライアント報告用トークン                      |
| ADMIN_TOKEN                | 管理操作用トークン                              |
| GCHAT_WEBHOOK              | Google Chat 受信 Webhook URL (未設定で通知無効) |
| CHROME_STABLE_TARGET_MAJOR | Chrome stable 許容メジャー                      |
| EDGE_STABLE_TARGET_MAJOR   | Edge stable 許容メジャー                        |
| CHROME_MIN_VERSION         | Chrome 最低許容バージョン                       |
| EDGE_MIN_VERSION           | Edge 最低許容バージョン                         |
| AUTO_CHECK_INTERVAL_MIN    | 自動画配布ポリシーのチェック間隔値              |
| GRACE_DAYS_STABLE_MAJOR    | fast → stable 昇格猶予日                        |
| AUTO_PROMOTE               | true で猶予日経過後自動昇格                     |
| DB_PATH                    | SQLite パス                                     |

## Google Chat Webhook 作成手順 (Space ベース)
1. Google Chat で対象スペースを開く
2. 上部のスペース名 → アプリ & 連携 → Webhook 管理
3. Webhook 追加: 名前 (例: BrowserUpdate), 説明任意
4. 発行された URL を `.env` の `GCHAT_WEBHOOK` に設定
5. `docker compose up -d --build` (変更時は再起動)

送信形式 (シンプル):
```json
{ "text": "[chrome] HOSTNAME 129.0.XXXX OUTDATED (stable)" }
```
必要に応じてカード形式へ拡張可能（Hangouts Chat card JSON 仕様）。

## メジャー承認フロー
1. fast ring (TargetVersionPrefix 空) が新メジャーを先行取得
2. 動作検証
3. 承認:
```bash
curl -X POST http://172.16.162.172:6001/approve \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"browser":"chrome","major":131}'
```
4. stable ring の `targetVersionPrefix` が更新され、端末が次回取得で反映

## Windows ポリシーレジストリ例
Chrome: `HKLM\SOFTWARE\Policies\Google\Update`  
Edge: `HKLM\SOFTWARE\Policies\Microsoft\EdgeUpdate`  
共通キー:
- UpdateDefault=0 (DWORD)
- AutoUpdateCheckPeriodMinutes
- TargetVersionPrefix (任意 / fast は未設定)

## 通知タイミング
- ステータス: OUTDATED / WARNING / MISSING / BLOCKED_WAIT_PREFIX
- 1日1回のハートビート (scheduler)

## 起動
```bash
cp .env.example .env
# トークン類を変更
docker compose up -d --build
```

## バックアップ
```bash
docker exec browser-update-controller \
  sh -c 'sqlite3 /data/controller.db ".backup /data/backup/controller-$(date +%Y%m%d).db"'
```

## 将来拡張
- Firefox ESR 追加
- Prometheus /metrics
- Google Chat カード通知 (色分け)
- OAuth / mTLS / IP 制限