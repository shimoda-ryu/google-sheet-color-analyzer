# Google Sheets Color Analyzer

Googleスプレッドシート上の商品画像URLを読み込み、OpenCVを使用して主要カラーを自動判定し、書き戻すツールです。
既存のPythonスクリプトをリファクタリングし、汎用的かつ設定変更が容易な構成にしました。

## ✨ 特長
- **設定の外部化:** `config/settings.yaml` でシート名、列名、カラー定義を自由に編集可能。
- **モダンな設計:** ソースコードをモジュール化 (`src/`) し、メンテナンス性を向上。
- **安全:** 機密情報は `.env` ファイルで管理。

## 📁 ディレクトリ構成
```text
google-sheet-color-analyzer/
├── src/           # ソースコード
├── config/        # 設定ファイル (settings.yaml)
├── tests/         # テストコード
├── .env.example   # 環境変数のテンプレート
└── requirements.txt
```

## 🚀 セットアップ手順

### 1. 必要要件
- Python 3.8 以上
- Google Cloud Platform (GCP) アカウント

### 2. インストール
```bash
# 依存ライブラリのインストール
pip install -r requirements.txt
```

### 3. Google Sheets API 設定
1. GCPコンソールでプロジェクトを作成し、**Google Sheets API** を有効にします。
2. サービスアカウントを作成し、JSONキーファイルをダウンロードします。
3. キーファイルをプロジェクトルート (または任意の安全な場所) に配置します。
4. 対象のGoogleスプレッドシートを開き、「共有」からサービスアカウントのメールアドレス (`xxx@yyy.iam.gserviceaccount.com`) に **編集権限** を付与します。

### 4. 環境変数の設定
`.env.example` をコピーして `.env` を作成し、以下を記述します。

```ini
# スプレッドシートID (URLの /d/xxxxx/ の xxxxx 部分)
SPREADSHEET_ID=your_spreadsheet_id_here

# ダウンロードしたJSONキーファイルのパス
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

### 5. 動作設定
`config/settings.yaml` を編集して、シート名やカラー定義を調整してください。
特に `color_categories` や `color_definitions` を自分の商品の色展開に合わせて変更することで、判定精度を最適化できます。

## 🖥 使い方

```bash
# 実行
python -m src.main
```

実行すると、以下の処理が自動で行われます。
1. `Product_Original` シートから商品情報を読み込み。
2. カラーIDが空、または未知の色名の商品に対し、画像URLから画像をダウンロード。
3. K-Means法で主要色を抽出。
4. 設定ファイルの色定義と照合し、最も近いカラーカテゴリを判定。
5. スプレッドシートに結果 (`=ID`) を書き込み。

## 🧪 テストの実行

```bash
pytest
```
