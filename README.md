# 製図サポート（drawing-support）

社内ツール群のうち、製図業務を支援する独立ツールです。日報ツールや帳票・発注管理ツールとはリポジトリを分離し、公開URL、デプロイ、障害対応もこのリポジトリの責務として管理します。

## 公開URL

- 画面: `/liff3/drawing-support.html`
- DXF JSON化: `/liff3/dxf-json.html`
- 日報ツールの管理メニュー「その他リンク」→「製図サポート」から遷移します。

ホスト名、APIのベースURL、GCPプロジェクトなど環境依存の値は、実装確定後に環境変数またはデプロイ設定へ置きます。秘密値をこのREADMEへ記載しないでください。

## 最初に読む文書

1. `AGENTS.md` — AIを含む開発者向けの作業規約
2. `REPOSITORY.md` — 社内ツール群との責務境界
3. `docs/INTEGRATIONS.md` — 日報ツール等との連携契約

## 現在の状態

Cloud Run のバックエンドは `cloudbuild.yaml` で既存GCPプロジェクト内の Artifact Registry と Cloud Run サービスへデプロイします。現時点では、Tfasから出力したDXFを `POST /api/v1/dxf/parse` で受け取り、図形・レイヤー・単位などを構造化JSONへ変換します。フロントエンドは `cloudbuild-frontend.yaml` の別トリガーでFTPアップロードします。

DXF JSON化の検証中は、Plesk上のブラウザからCloud Runへ直接接続するため、Cloud Runを公開設定にしています。利用者認証・認可が未実装の検証用設定であり、本番運用前にLIFF等の認証検証をAPIへ追加し、公開設定を見直してください。

ローカルでは次のコマンドでAPIを起動できます。

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

DXF解析APIの仕様と制約は `docs/INTEGRATIONS.md` に記載しています。TFSを直接解析するものではなく、Tfas側でDXFへ変換したファイルを対象とします。

デプロイ手順と必要なGCP権限は `docs/DEPLOYMENT.md` を参照してください。

## 秘密情報

APIキー、アクセストークン、Cookie、サービスアカウント鍵、個人情報をGit管理対象へ保存しません。環境変数名は`.env.example`に記載し、実値はローカルの`.env`やデプロイ環境で管理します。
