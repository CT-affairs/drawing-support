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

`entities`には、現在、Model SpaceにあるLINE、LWPOLYLINE/POLYLINE、CIRCLE、ARC、TEXT/MTEXT、INSERT、DIMENSIONの基本情報を格納します。`spaces`にはレイアウト別のエンティティ件数、`blocks`にはブロック定義別の件数・定義内の`entities`・ブロック定義座標での`bbox`、`inserts`には配置先レイアウト・ブロック名・配置座標・縮尺・INSERT個体ID・分類結果を格納します。`inserts[].block`は同一DXF内の`blocks[].name`を参照し、`inserts[].id`は配置されたINSERTごとの固有IDです。`inserts[].classification.role`は`target`、`meta`、`unknown`の3値で、分類根拠と確度も保持します。`blocks[].entities`はブロック定義内の直接の構成要素を格納し、ネストしたINSERTはブロック名・配置座標・回転角・XYZ縮尺を持つ参照として保持します。`blocks[].bbox`は`min`、`max`、`size`、`center`をXYZ配列で返し、計算可能な形状がない場合は`null`です。bboxではネストしたINSERTの形状も再帰展開して外接範囲へ含めます。解析は、まず文字コード候補を診断し、選択した文字コードで通常読み込みを行います。通常読み込みで図形が0件なのに生DXFの`ENTITIES`または`BLOCKS`にレコードがある場合は、`recover.read()`へフォールバックします。`diagnostics.encoding`に`$DWGCODEPAGE`、候補文字コード、選択結果、確度を記録し、`diagnostics.loader`に`standard`または`recover`を記録します。`diagnostics.object_classification`に分類戦略とrole別件数を記録します。recoverの試行結果と監査件数も返します。

レイヤー名とブロック名の復元は単一方式へ固定しません。元名称を保持したまま複数の復元候補を生成し、厳密なバイト往復、未解決文字、日本語文字数、文字化け指標、名称参照間の整合性を評価して、十分な確度がある候補だけをJSONへ採用します。現在は、UTF-8のバイト列がCP932等の文字列として保存された経路と、CP932の元バイトがCP1252文字とサロゲートに分かれて残った経路に対応しています。後者は今回確認した一候補であり、すべてのDXFへ無条件適用するものではありません。元の名称、復元名、選択方式、確度、元バイト列、出現箇所は`diagnostics.name_decoding`に保持します。候補なしまたは確度不足の場合は元名称を維持します。候補方式、選択フロー、確認例は`docs/AI_SUPPORT_PROGRESS.md`の「名称復元の基本方針」を参照してください。

`TEXT`、`MTEXT`、`DIMENSION`の文字列にも同じ候補生成を適用し、丸数字、`×`、`㎡`などCAD注記で使用する記号だけが復元されるケースも評価します。採用結果は`diagnostics.text_decoding`へ記録します。API応答と共有ドライブへ新規保存するJSONは、すべての文字列をUnicodeスカラー値へ正規化して厳密なUTF-8で出力します。復元できないsurrogateescapeバイトは削除せず、`\\xNN`形式の可視トークンとして保持し、件数を`diagnostics.unicode_normalization`へ記録します。過去にsurrogatepassで保存したJSONは読込時に同じ形式へ正規化します。

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

事前準備として、Google Cloud側でサービスアカウントを作成し、そのメールアドレスを対象の共有ドライブへ「コンテンツ管理者」以上の権限で追加しておく必要があります（今回のPoCでは追加済み）。サービスアカウント鍵はSecret Manager`drawing-support-google-drive-sa`へ登録済みで、`cloudbuild.yaml`の`gcloud run deploy`が`--set-secrets`で`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`として注入します。Cloud Runの実行用サービスアカウント（`1088643883290-compute@developer.gserviceaccount.com`）にこのシークレットの`Secret Manager のシークレット アクセサー`権限を付与済みです。

### 共有ドライブのJSON閲覧（解析は行わない）

`/liff3/drive-json-viewer.html`は、共有ドライブに保存済みのJSONを一覧表示し、選んだファイルをツリー表示する専用画面です。DXFの解析は行わず、既にJSON化済みのファイルを確認する用途に限定します。ツリー表示部分は`/liff3/js/json-tree.js`として`dxf-json.html`と共通化しています。

| 項目 | 内容 |
|---|---|
| エンドポイント | `GET /api/v1/drive/list` |
| 応答 | `files`（配列。各要素は`id`、`name`、`modified_time`、`size`） |
| 対象 | 共有ドライブ保存と同じ既定フォルダ直下の`mimeType=application/json`のファイルのみ |
| エラー | `502 drive_list_failed` |

| 項目 | 内容 |
|---|---|
| エンドポイント | `GET /api/v1/drive/file/<file_id>` |
| 応答 | `file_id`、`file_name`、`data`（JSONの中身） |
| 安全対策 | 取得前に対象ファイルの`parents`が既定フォルダと一致するか検証し、一致しない場合は取得せず`502 drive_fetch_failed`を返す |
| エラー | `502 drive_fetch_failed`（フォルダ不一致、取得失敗、JSONとして不正な内容を含む） |

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

### バックエンドトリガーの発火条件

`drawing-support-backend-deploy`トリガーは`ignoredFiles`で対象外ファイルを指定する方式にしています。`liff3/**`（HTML/CSS/JS。フロントエンド側`drawing-support-frontend-ftp-deploy`トリガーの管轄）と`.env`・`.env.*`（機密情報）への変更のみのpushはバックエンドの再ビルドをスキップし、それ以外のファイル変更（`app.py`、`drive_export.py`、`dxf_json.py`、`requirements.txt`、`Dockerfile`、`cloudbuild.yaml`、`tests/**`、`docs/**`等）は自動でCloud Runへ再デプロイします。

以前は逆に`includedFiles`で`Dockerfile`・`nginx.conf`・`cloudbuild.yaml`のみを対象としていたため、アプリ本体（`app.py`等）を変更してpushしてもバックエンドトリガーが発火せず、手動デプロイが必要になっていました（`nginx.conf`は本リポジトリに存在しないファイルで、設定の流用時の残骸と考えられます）。

## 未決事項

- 技術スタックとローカル起動方法
- 認証・認可方式
- バックエンドAPIの有無とURL
- 元のDXFファイル自体の保存先・保持期間（解析結果JSONの共有ドライブ保存は実装済み。「解析結果のGoogle Drive共有ドライブ保存」参照）
- 共有ドライブに保存したJSONの保持期間・棚卸し方法
- Firestore共有の要否
- Cloud Buildと本番配置方法

決定後は、実装より先に本章を更新してください。
### Unit metadata and override

The JSON output uses `unit` as the normalized unit name, `units` as the DXF unit code, and `units_source` as `dxf_header`, `default`, or `user_override`. When the DXF does not declare units, `mm` is used as the default and the source is recorded as `default`. `POST /api/v1/drive/file/{file_id}/unit` updates an existing Drive JSON file in place. This operation changes unit metadata only; it does not rescale coordinates. The Drive JSON viewer exposes this operation from the JSON overview modal.

## Operation master / Firestore contract

The operation master is stored in the new Firestore collection `drawing_operations`. The document ID is the operation ID, so the manually created first document is `OP001`. The drawing-support backend accesses this collection; the browser does not access Firestore directly.

Recommended sample document:

```json
{
  "operation_id": "OP001",
  "name": "曲率Rを抽出",
  "instruction": "曲率Rのある部材を抽出し、半径を一覧化する",
  "actions": ["extract_radius", "classify_target"],
  "active": true,
  "version": 1,
  "description": "",
  "updated_at": "server timestamp"
}
```

`operation_id`, `name`, `instruction`, `actions`, `active`, and `version` are managed fields. `description` is optional. `updated_at` is written by the backend as a Firestore server timestamp. The `/liff3/operation-master.html` page provides simple list, create/update, and delete operations through `GET /api/v1/operations`, `PUT /api/v1/operations/{operation_id}`, and `DELETE /api/v1/operations/{operation_id}`. IDs must be uppercase `OP` followed by at least three digits, such as `OP001`.

The Cloud Run service account needs Firestore access to the project containing this collection. No source-folder data file is required; application default credentials and the deployed service account are the connection mechanism.
