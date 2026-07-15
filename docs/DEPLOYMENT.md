# Cloud Run 初期デプロイ

## 前提

- 既存の GCP プロジェクトを利用する。`$PROJECT_ID` は Cloud Build が実行されるプロジェクトを指す。
- Cloud Run サービス名の初期値は `drawing-support`。
- リージョンの初期値は `asia-northeast1`。実際の利用リージョンに合わせて変更する。
- Artifact Registry に Docker リポジトリ `dailyreport` を事前作成する。
- DXF JSON化のPoCではPlesk上のブラウザから直接呼び出すため、Cloud Buildは`--allow-unauthenticated`で公開サービスを作成する。これは利用者認証・認可が未実装の検証用設定であり、本番運用では変更する。

## 初回準備

```powershell
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create dailyreport `
  --repository-format=docker `
  --location=asia-northeast1 `
  --description="shared container images"
```

リポジトリが既に存在する場合、作成コマンドは不要です。Cloud Build の実行サービスアカウントには、Artifact Registry への書き込み権限と Cloud Run のデプロイ権限を付与してください。

## 手動実行

```powershell
gcloud builds submit --config=cloudbuild.yaml .
```

`cloudbuild.yaml` はイメージをビルド・pushし、同じGCPプロジェクト内の Cloud Run サービスを更新します。

コンテナはPython 3.12、Flask、Gunicornで起動し、`8080`ポートで`app:app`を提供します。DXF解析に必要な`ezdxf`は、リポジトリ直下の`requirements.txt`からイメージビルド時にインストールされます。

## Cloud Build トリガー

GitHub の本リポジトリと `main` ブランチを対象に、次の2つの独立トリガーを作成します。

- バックエンド: `cloudbuild.yaml` → Cloud Run `drawing-support`
- フロントエンド: `cloudbuild-frontend.yaml` → `deploy_frontend.txt` の対象をFTPアップロード

フロントエンド用トリガーは次のSecret Managerシークレットを参照します。

- `CT-ops-platform-ftp-host`
- `CT-ops-platform-ftp-user`
- `CT-ops-platform-ftp-pass`

Cloud Buildの実行サービスアカウントには、3つのシークレットへの `Secret Manager Secret Accessor` 権限を付与してください。シークレットの値はCloud Build設定やリポジトリへ記載しません。

## 確認

```powershell
gcloud run services describe drawing-support --region=asia-northeast1
```

PoC中はサービスURLを公開し、Plesk上のDXF JSON化画面から接続します。利用者認証・認可を実装する際は、API側の認可実装とCloud Runの公開設定を同時に見直してください。
