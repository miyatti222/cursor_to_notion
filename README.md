# cursor_to_notion ツールの使用方法

このツールは、MarkdownファイルとNotionページの相互変換を行います。

## 想定ユースケース

1. **Cursorで仕様やスケジュールなどのMarkdownファイルを作成**:
   - LLM（大規模言語モデル）を活用して、仕様書やスケジュールなどのMarkdownファイルをCursorで作成します。

2. **Markdownファイルを `md2notion.py` でNotionにアップロード**:
   - 作成したMarkdownファイルを `md2notion.py` を使用してNotionにアップロードします。
   - これにより、Cursorで作成したドキュメントを他のメンバーと簡単にシェアできます。

3. **Notionで内容を更新**:
   - Notion上でドキュメントの内容を更新します。

4. **更新された内容を `notion2md.py` でダウンロード**:
   - Notionで更新された内容を `notion2md.py` を使用して手元にダウンロードします。
   - ダウンロードされたMarkdownファイルの末尾には、対応するNotionページのURLが `//url:xxxx` の形式で追加されます。

5. **Cursorで内容をLLMと一緒に更新**:
   - ダウンロードしたMarkdownファイルをCursorで開き、LLMと一緒に内容を更新します。

6. **更新したMarkdownファイルを `md2notion.py` で再度アップロード**:
   - 更新したMarkdownファイルを再度 `md2notion.py` を使用してNotionにアップロードし、最新の内容を共有します。
   - Markdownファイルの末尾にある `//url:xxxx` を参照して、既存のNotionページを更新します。

## 共通の準備

1. **依存関係のインストール**:
   ```bash
   pip install notion-client
   ```

2. **環境変数の設定**:
   Notion APIキーを環境変数に設定します。
   ```bash
   export NOTION_TOKEN="your_notion_api_key_here"
   ```

3. **設定ファイルの作成**:
   `config.json` ファイルを作成し、デフォルトの親ページまたはデータベースのURLと、タイトル列の名前を設定します。このファイルは現在のディレクトリまたは`cursor_to_notion`ディレクトリに配置できます。
   ```json
   {
       "default_parent_url": "https://www.notion.so/your_default_parent_page_or_database_url",
       "default_title_column": "名前"
   }
   ```

## notion2md.py の使用方法

NotionページをMarkdownファイルに変換します。

### コマンドライン引数

- `url`: NotionページのURL（省略可能、`config.json` に定義がある場合）
- `-o`, `--output`: Markdownファイルの出力ディレクトリ（省略可能）
- `-c`, `--children`: 子ページを取得する場合に指定

### 使用例

```bash
python notion2md.py https://www.notion.so/your_page_url -o output_directory
```

または、`config.json` に `default_parent_url` が定義されている場合：

```bash
python notion2md.py -o output_directory
```

子ページを取得する場合：

```bash
python notion2md.py https://www.notion.so/your_page_url -o output_directory -c
```

### 出力

指定されたディレクトリにMarkdownファイルが作成されます。ファイル名はNotionページのタイトルに基づきます。さらに、Markdownファイルの末尾には対応するNotionページのURLが `//url:xxxx` の形式で追加されます。

## md2notion.py の使用方法

MarkdownファイルをNotionページに変換します。

### コマンドライン引数

- `file`: Markdownファイルのパス
- `url`: 親ページまたはデータベースのURL（省略可能）
- `-t`, `--title`: Notionページのタイトル（省略可能、デフォルトはMarkdownファイル名）
- `-c`, `--column`: データベースのタイトル列の名前（省略可能、デフォルトは `config.json` の設定）

### 使用例
```bash
python md2notion.py your_markdown_file.md https://www.notion.so/your_parent_page_or_database_url -t "Your Page Title" -c "名前"
```

### 出力

指定された親ページまたはデータベースに新しいNotionページが作成されます。既存のページを更新する場合は、Markdownファイルの末尾に `//url:NotionページのURL` を追加してください。これにより、`md2notion.py` は既存のページを更新するためのURLを認識し、適切に更新を行います。

## 注意事項

- 両スクリプトは、テキスト、ヘッダー、リスト（ネストされたリストを含む）、コードブロック、画像、引用、To-Doリストなどの基本的なMarkdown/Notionの要素をサポートしています。
- 複雑なNotionの機能（データベース、埋め込みコンテンツなど）は完全にはサポートされていない場合があります。
- Notionのレート制限に注意してください。短時間に多数のリクエストを送信すると、APIの使用が制限される可能性があります。
- `md2notion.py` を使用して新規ページを作成する場合、親ページのURLは次の優先順位で決定されます：
  1. コマンドライン引数で指定されたURL
  2. `config.json` の `default_parent_url`
  3. 上記どちらも指定がない場合はエラーになります

## トラブルシューティング

エラーが発生した場合は、以下を確認してください：
- Notion APIキーが正しく設定されているか
- 親ページまたはデータベースのURLが正しいか
- Markdownファイルが存在し、読み取り可能か
- インターネット接続が安定しているか
- `config.json` ファイルが正しく設定されているか

詳細なエラーメッセージが表示された場合は、それに基づいて問題を解決するか、サポートを求めてください。