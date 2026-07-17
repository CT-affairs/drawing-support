# ツール間連携

## 日報ツールからの画面遷移

日報ツールの管理画面には、次のメニューが定義されています。

- 見出し: `その他リンク`
- 項目: `製図サポート`
- 遷移先: `/liff3/drawing-support.html`

製図サポート内の画面は、ダッシュボードを`/liff3/drawing-support.html`、DXF JSON化機能を`/liff3/dxf-json.html`として分離します。サイドメニューのカテゴリ・配色・active表示は発注画面のメニュー構成を踏襲します。

PoCの進捗、確認済みのレスポンス、次回の調査項目は`docs/AI_SUPPORT_PROGRESS.md`を参照してください。

現在の連携契約はURL遷移のみです。クエリ文字列、POSTデータ、ブラウザストレージによる引き渡しは契約に含みません。

## 認証・認可

方式は未確定です。実装前に次を決定してください。

1. LIFF認証、日報ツールのPCセッション、または本ツール独自セッションのどれを使うか
2. 認証情報を本ツールのバックエンドでどう検証するか
3. 利用可能な社員・グループ・管理者権限をどう判定するか
4. セッション期限切れと権限不足をどう表示するか

日報ツール側でメニューが見えることを、本ツールの認可として信用してはいけません。本ツールのAPI側でも権限を検証します。

## Firestore・社員情報

日報ツールでは、少なくとも以下の共有候補があります。

| 項目 | 用途 | 注意点 |
|---|---|---|
| `users` | LINEユーザーと社員の紐付け | 本ツールが必要とするフィールドを確定するまで直接依存しない |
| `employee_mappings` | 社員番号等のマッピング | 読み取り主体と権限を決める |
| `company_employee_id` | 社員の安定識別子候補 | 型、桁、退職者の扱いを確定する |
| `group_id` | 所属・権限の補助 | 単独で認可根拠にしない |

製図固有データは本ツール所有のコレクションへ保存します。他ツール所有コレクションへの書き込みは、明示的に合意した場合だけ行います。

## API連携

### 製図サポート内部API

DXF解析のPoCとして、次のエンドポイントを提供します。

| 項目 | 内容 |
|---|---|
| エンドポイント | `POST /api/v1/dxf/parse` |
| 要求 | `multipart/form-data` の `file` フィールド。拡張子`.dxf` |
| 最大サイズ | 既定30MiB。`MAX_DXF_BYTES`で変更。Cloud Runのリクエスト上限を超えるファイルは受付不可 |
| 応答 | `schema_version`、`dxf_version`、`units`、`layers`、`entity_counts`、`entities`、`spaces`、`blocks`、`inserts`、`diagnostics` |
| 認証 | PoC中はCloud Runを公開。アプリケーションレベルの利用者認証・認可は未実装のため、本番利用不可 |
| CORS | `DRAWING_SUPPORT_CORS_ORIGINS`でカンマ区切りの許可Originを指定。既定値は`https://clean-techno.com`と`https://www.clean-techno.com` |
| エラー | `400 file_required`、`415 invalid_extension`、`422 invalid_dxf`、`413 file_too_large` |

`entities`には、現在、Model SpaceにあるLINE、LWPOLYLINE/POLYLINE、CIRCLE、ARC、TEXT/MTEXT、INSERT、DIMENSIONの基本情報を格納します。`spaces`にはレイアウト別のエンティティ件数、`blocks`にはブロック定義別の件数、`inserts`には配置先レイアウト・ブロック名・配置座標・縮尺を格納します。解析は、まず文字コード候補を診断し、選択した文字コードで通常読み込みを行います。通常読み込みで図形が0件なのに生DXFの`ENTITIES`または`BLOCKS`にレコードがある場合は、`recover.read()`へフォールバックします。`diagnostics.encoding`に`$DWGCODEPAGE`、候補文字コード、選択結果、確度を記録し、`diagnostics.loader`に`standard`または`recover`を記録します。recoverの試行結果と監査件数も返します。

レイヤー名とブロック名の復元は単一方式へ固定しません。元名称を保持したまま複数の復元候補を生成し、厳密なバイト往復、未解決文字、日本語文字数、文字化け指標、名称参照間の整合性を評価して、十分な確度がある候補だけをJSONへ採用します。現在は、UTF-8のバイト列がCP932等の文字列として保存された経路と、CP932の元バイトがCP1252文字とサロゲートに分かれて残った経路に対応しています。後者は今回確認した一候補であり、すべてのDXFへ無条件適用するものではありません。元の名称、復元名、選択方式、確度、元バイト列、出現箇所は`diagnostics.name_decoding`に保持します。候補なしまたは確度不足の場合は元名称を維持します。候補方式、選択フロー、確認例は`docs/AI_SUPPORT_PROGRESS.md`の「名称復元の基本方針」を参照してください。

`diagnostics`にはファイルサイズ、文字コード、DXFセクション別の生レコード件数、ezdxf内部エンティティ数、監査件数を格納します。未知のエンティティも種別とレイヤーは保持します。寸法計算、干渉判定、DXF再出力、AIによる候補判断はこのAPIの責務に含めません。

このAPIはTFS（Tfas固有形式）を直接読みません。TfasからDXFまたはIFCへ変換した後のDXFを対象にします。将来AI APIを追加する場合は、このJSONを入力にして候補生成・異常箇所の説明・修正案を行い、座標・寸法の確定はプログラム側で検証します。

### 解析結果のGoogle Drive共有ドライブ保存

`/liff3/dxf-json.html`の「共有ドライブへ保存」ボタンから、`POST /api/v1/dxf/parse`の応答JSONをそのままGoogle Driveの共有ドライブへ保存できます。自動保存ではなく、利用者がボタンを押した回だけ保存します。

| 項目 | 内容 |
|---|---|
| エンドポイント | `POST /api/v1/drive/save` |
| 要求 | JSON本文`{"filename": "元のDXFファイル名", "data": {解析結果JSON}}` |
| 応答 | `file_id`、`file_name`、`web_view_link` |
| エラー | `400 invalid_request`（`data`欠落）、`502 drive_upload_failed`（認証未設定・アップロード失敗） |
| 保存先 | 既定は共有ドライブフォルダID`1TQRI0_z6WmeG8-8VjXONRSyKwP4h97m2`。`GOOGLE_DRIVE_FOLDER_ID`で上書き可能 |
| 認証 | サービスアカウントの鍵。`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`（鍵JSONの中身）または`GOOGLE_APPLICATION_CREDENTIALS`（鍵ファイルパス） |
| ファイル名 | 元のDXFファイル名から拡張子を除いた部分＋UTC実行時刻＋`.json` |

事前準備として、Google Cloud側でサービスアカウントを作成し、そのメールアドレスを対象の共有ドライブへ「コンテンツ管理者」以上の権限で追加しておく必要があります（今回のPoCでは追加済み）。Cloud Run側は`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`にサービスアカウント鍵の中身をシークレットとして設定します。

日報ツール・帳票ツールとのAPI連携は引き続き未定義です。追加時は以下をこの文書へ記録します。

- 所有ツールとエンドポイント
- HTTPメソッド、要求・応答スキーマ
- 認証方式と必要権限
- タイムアウト、再試行、冪等性
- エラー時の利用者表示
- バージョニングと廃止手順

## デプロイ境界

日報ツールはGitHubの`main`へのpushを契機にCloud Buildでデプロイされています。本ツールは独立リポジトリのため、独立したトリガーとデプロイ対象を持たせます。

Cloud Buildを構成するときは、最低限次を確認します。

- 対象GitHubリポジトリとブランチ
- `/liff3/`だけを更新する配置先
- 日報ツール(`/liff/`)や帳票ツール(`/liff2/`)を削除・上書きしないこと
- キャッシュ更新方法
- ロールバック方法

初期構成では、バックエンドを本リポジトリ単独の Cloud Run サービス `drawing-support` としてデプロイします。フロントエンドは別のCloud BuildトリガーからFTPアップロードします。コンテナやアップロード対象は `/liff3/` 配下に限定し、日報ツール(`/liff/`)や帳票ツール(`/liff2/`)の成果物を取り込みません。DXF JSON化のPoCではブラウザから直接APIを呼ぶため公開設定としますが、認証方式確定後にアプリケーション認証を追加し、Cloud Run設定も含めて本番用に見直します。具体的な準備・デプロイ手順は `docs/DEPLOYMENT.md` に記載します。

## 未決事項

- 技術スタックとローカル起動方法
- 認証・認可方式
- バックエンドAPIの有無とURL
- 元のDXFファイル自体の保存先・保持期間（解析結果JSONの共有ドライブ保存は実装済み。「解析結果のGoogle Drive共有ドライブ保存」参照）
- 共有ドライブに保存したJSONの保持期間・棚卸し方法
- Firestore共有の要否
- Cloud Buildと本番配置方法

決定後は、実装より先に本章を更新してください。
