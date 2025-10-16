# Browser Update Controller

Chrome / Edge の最新安定版バージョンを定期取得し、差分が出た際に Google Chat へ通知する軽量コントローラです。各 Windows クライアント端末へ配布する PowerShell スクリプトと組み合わせて、Active Directory や GPO を触れない環境でもブラウザ更新運用の省力化を支援します。

## 機能概要
- 1時間ごと (環境変数で可変) に Chrome / Edge の Windows Stable 最新バージョンを取得
- 直前バージョンとの差分が発生した場合 Google Chat Incoming Webhook へ通知
- 取得結果はローカル JSON (`data/version_state.json`) にキャッシュ
- REST API で現在バージョン / 手動再チェック / ダウンロードページ URL を提供
- PowerShell スクリプトで各端末は API を参照し、Chrome MSI / winget Edge アップデートを実行

## 主要エンドポイント
| Method | Path               | 説明                                        |
| ------ | ------------------ | ------------------------------------------- |
| GET    | `/health`          | ヘルスチェック                              |
| GET    | `/versions`        | 取得済みバージョンと履歴表示                |
| POST   | `/refresh`         | 即時で最新バージョン再チェック (非同期実行) |
| GET    | `/download/chrome` | Chrome ダウンロードページ URL               |
| GET    | `/download/edge`   | Edge ダウンロードページ URL                 |
| GET    | `/`                | 簡易トップ                                  |

## 動作環境
- Docker / Docker Compose
- ホスト想定 IP: `172.16.162.172` (必要に応じて変更)
- 公開ポート: `6001`

## セットアップ手順
1. リポジトリ取得
2. `.env` を作成 (例は下記)
3. `docker compose build && docker compose up -d` で起動

### .env サンプル
```
CHECK_INTERVAL_SECONDS=3600
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/XXXX/messages?key=YYYY&token=ZZZZ
LOG_LEVEL=info
```

### 起動・停止 (PowerShell)
```
docker compose up -d
docker compose logs -f browser-update-controller
docker compose down
```

## Google Chat 連携
1. Google Chat でスペースを作成
2. 「アプリと統合」→「ウェブフックを追加」→ 名前例: `BrowserUpdateNotifier`
3. 発行された Webhook URL を `.env` の `GOOGLE_CHAT_WEBHOOK_URL` に設定
4. コンテナ再起動後、新バージョン検出時に通知されます

### 通知例
```
Chrome 新バージョン検出: 129.0.XXXX.Y
旧: 128.0.AAAA.B -> 新: 129.0.XXXX.Y
ダウンロード: https://www.google.com/chrome/
```

## クライアント端末側の更新スクリプト
`scripts/update-browsers.ps1` を配布してください。主な挙動:
- コントローラ `/versions` を参照し最新バージョンを確認
- Chrome: レジストリからローカルバージョン取得 / 差異があれば Enterprise MSI をダウンロードしサイレントインストール
- Edge: `winget upgrade Microsoft.Edge -e --silent`
- コントローラが到達不能でも Edge の更新は試行

### 手動実行例 (PowerShell 管理者)
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
./update-browsers.ps1 -ControllerBaseUrl http://172.16.162.172:6001
```

### 強制再インストール (Chrome 差分無視)
```
./update-browsers.ps1 -Force
```

## Windows タスク スケジューラ登録例
1. スクリプトを `C:\Tools\update-browsers.ps1` などに配置
2. タスク スケジューラ → 基本タスクの作成
	 - 名前: `UpdateBrowsers`
	 - トリガー: 1日1回 / もしくは 3時間おき (詳細タブで「繰り返し」設定)
	 - 操作: プログラム開始
		 - プログラム/スクリプト: `powershell.exe`
		 - 引数の追加: `-ExecutionPolicy Bypass -File C:\Tools\update-browsers.ps1 -ControllerBaseUrl http://172.16.162.172:6001`
		 - 開始 (オプション): `C:\Tools`
3. 「最上位の特権で実行する」(Chrome / Edge のインストールで昇格が必要な場合)
4. 条件タブ: バッテリ使用時でも実行したい場合は該当チェック解除

## アップデート検知ロジック概要
1. バックグラウンドスレッドが interval ごとに外部 API を取得
2. 直前と異なるバージョンを検出したらイベント履歴へ追加 + Google Chat 通知
3. `/versions` で `history` 配列として過去イベントを閲覧可能

## セキュリティ / 運用メモ
- Webhook URL は秘匿 ( `.env` を Git にコミットしない )
- ネットワーク制限が厳しい環境では HTTP プロキシ環境変数 (`HTTP_PROXY` / `HTTPS_PROXY`) をコンテナに付与可能
- 将来的に API Key 認証を追加する場合: リバースプロキシや FastAPI の依存で `X-API-Key` 検証を挿入

## トラブルシュート
| 症状                        | 対応                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------ |
| Google Chat 通知が来ない    | Webhook URL/ファイアウォール/ログで `Google Chat webhook failed` を確認              |
| `/versions` が空または null | 外部 API 取得失敗。コンテナログで `version check failed` を確認                      |
| Chrome 更新されない         | スクリプトログで MSI インストール ExitCode を確認。管理者権限/セキュリティソフト干渉 |
| Edge 更新されない           | `winget` 利用可否 (設定→アプリ→App Installer) を確認                                 |

## ビルド/起動 (開発用途)
```
docker compose build --no-cache
docker compose up -d
curl http://172.16.162.172:6001/versions
```

## ライセンス
`LICENSE` を参照してください。

---
改善アイデア / 追加要望があれば Issue や PR でお知らせください。

