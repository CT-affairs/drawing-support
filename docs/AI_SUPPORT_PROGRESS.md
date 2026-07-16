# AIサポート製図 PoC 進捗記録

最終更新: 2026-07-16

## 現在の到達点

Tfasから出力したDXFをブラウザからCloud Runへ送信し、`ezdxf`で読み込んでJSONレスポンスを返す一連の経路を確認した。

```text
Plesk上の /liff3/dxf-json.html
  ↓ multipart/form-data
Cloud Run drawing-support
  ↓ POST /api/v1/dxf/parse
ezdxfでDXFを読み込み
  ↓
構造化JSONをブラウザへ表示
```

## 実装済み

- `/liff3/drawing-support.html`を製図サポートのダッシュボード化
- `/liff3/dxf-json.html`をDXF JSON化の専用画面として追加
- 発注画面のサイドメニュー構成・配色・active表示を踏襲
- DXFファイルの選択、ドラッグ＆ドロップ、解析結果表示
- `POST /api/v1/dxf/parse`の実装
- `ezdxf`によるDXF基本情報のJSON化
- Cloud RunとPlesk間のCORS設定
- PoC中の接続確認のためCloud Runを公開設定へ変更
- フロントエンドFTP対象に`liff3/*.css`を追加
- 通常系・ファイル未指定・拡張子不正・破損DXF・サイズ超過のテスト
- レイアウト別のエンティティ件数、ブロック別の件数、INSERTとブロック名の取得
- DXFセクション、生レコード件数、ezdxf内部件数、監査件数などの診断情報
- 通常読み込みで図形が取得できない場合の`recover.read()`フォールバック
- 文字コード候補診断と選択結果の記録

## 実際に確認できたこと

約6,300KBのDXFを送信し、次のレスポンスを取得できた。

```json
{
  "dxf_version": "AC1009",
  "entities": [],
  "entity_counts": {},
  "layers": [],
  "schema_version": "1.0",
  "units": 6
}
```

これにより、以下は成立している。

- ブラウザからCloud Run APIへ接続できる
- 数MBのDXFを受信できる
- `ezdxf`でDXFとして読み込める
- DXFバージョンと単位を取得できる
- JSONレスポンスを返せる

## 現時点の課題

`entities`が空だったため、図面の図形情報をまだ取得できていない。

図形の全展開はまだ行わず、レイアウト別・ブロック別の集計とINSERT参照だけを追加した。Tfas出力DXFでは、図形が次の場所に存在する可能性がある。

- Paper Space
- Block定義
- INSERT参照先
- レイアウト別のエンティティ
- Tfas固有またはR12形式の要素

`AC1009`はAutoCAD R12形式であるため、次回はDXFの格納構造を診断する必要がある。ファイルサイズが大きいこと自体は、図形数が取得できない直接の原因とは限らない。

## 次回の作業候補

優先順に次を確認する。

1. レスポンスの`spaces`、`blocks`、`inserts`で実DXFの格納場所を確認する
2. `diagnostics.entities_section`の生レコード件数と種別を確認する
3. `diagnostics.encoding`の`dwg_codepage`、候補、選択確度を確認する
4. `diagnostics.loader`が`recover`になった場合の監査結果を確認する
5. Tfasから出力するDXF設定（2D/3D、R12互換、ブロック化）を確認する
6. LINE、POLYLINE、TEXT、DIMENSION、INSERT等がどこに格納されているか確認する
7. 図形取得後に、AIへ渡す中間JSONの項目を整理する

## セキュリティ・運用上の注意

現在のCloud Runは、Plesk上のブラウザから直接PoC APIを呼ぶため公開設定にしている。Cloud Runの公開設定はサービス単位であり、Cloud Run URL上のAPIを誰でも呼び出せる状態である。

一方、`/liff/`と`/liff2/`はPlesk側の別サービスであり、今回のCloud Run公開設定の対象ではない。

現在のPoCでは、利用者認証・認可は未実装である。機密図面や個人情報を含む本番データは使用しない。実運用前に、LIFF IDトークン等の認証検証、利用者・所属に基づく認可、監査ログ、ファイル保持方針を追加し、Cloud Run公開設定も見直す。

## 再開時の確認

- Cloud Runの最新リビジョンがデプロイ済みか確認する
- Plesk側の`/liff3/dxf-json.html`とCSSが最新か確認する
- Cloud Run URLが`liff3/dxf-json.html`の設定と一致しているか確認する
- 解析対象DXFは機密情報を除いたサンプルを使う
- まず診断用のModel Space／Paper Space／Block集計を追加する
