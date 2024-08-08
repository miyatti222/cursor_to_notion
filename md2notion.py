#!/usr/bin/env python3

import os
import json
import argparse
import re
from notion_client import Client, APIResponseError
from md_to_blocks import convert_markdown_to_notion_blocks

# Notion APIキーを環境変数から取得
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

# Notionクライアントの初期化
notion = Client(auth=NOTION_TOKEN)

def load_config():
    # まず現在のディレクトリでconfig.jsonを探す
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.json')
    
    if not os.path.exists(config_path):
        # 現在のディレクトリにない場合、スクリプトのディレクトリで探す
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: config.jsonが見つかりません。デフォルト設定を使用します。")
        return {}

def extract_id_from_url(url: str) -> str:
    match = re.search(r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url)
    return match.group(1).replace("-", "") if match else None

def clear_page_content(page_id: str):
    # ページの子ブロックをすべて取得
    blocks = notion.blocks.children.list(block_id=page_id)
    
    # すべてのブロックを「空」に更新
    for block in blocks.get("results", []):
        notion.blocks.update(block_id=block["id"], archived=True)

def create_or_update_notion_page(title: str, blocks: list, url: str, title_column: str = "名前", update_mode: bool = False):
    page_id = extract_id_from_url(url)
    if not page_id:
        raise ValueError("Invalid Notion URL provided")

    if update_mode:
        # 既存のページを更新
        print("既存のページを更新します")
        
        # タイトルを更新
        notion.pages.update(page_id=page_id, properties={"title": {"title": [{"text": {"content": title}}]}})
        
        # 既存のコンテンツをクリア
        print("既存のコンテンツをクリア中...")
        clear_page_content(page_id)
        
        # 新しいコンテンツを追加
        print("新しいコンテンツを追加中...")
        notion.blocks.children.append(block_id=page_id, children=blocks)
        
        return notion.pages.retrieve(page_id=page_id)["url"]
    else:
        # 新しいページを作成
        print("新しいページを作成します")
        try:
            parent_object = notion.databases.retrieve(database_id=page_id)
            is_database = True
        except APIResponseError as e:
            if e.code == "object_not_found":
                try:
                    parent_object = notion.pages.retrieve(page_id=page_id)
                    is_database = False
                except APIResponseError as e:
                    raise ValueError(f"Invalid parent URL: {str(e)}")
            else:
                raise ValueError(f"APIエラー: {str(e)}")

        if is_database:
            new_page = notion.pages.create(
                parent={"database_id": page_id},
                properties={
                    title_column: {"title": [{"text": {"content": title}}]}
                },
            )
        else:
            new_page = notion.pages.create(
                parent={"page_id": page_id},
                properties={
                    "title": {"title": [{"text": {"content": title}}]}
                },
            )

        notion.blocks.children.append(block_id=new_page["id"], children=blocks)
        return new_page["url"]

def extract_url_from_markdown(markdown_content: str) -> str:
    url_match = re.search(r"//url:(https://www\.notion\.so/[^\s]+)", markdown_content)
    if url_match:
        return url_match.group(1)
    return None

def main():
    print("スクリプトを開始します")
    config = load_config()
    default_parent_url = config.get('default_parent_url', '')
    default_title_column = config.get('default_title_column', '名前')

    parser = argparse.ArgumentParser(description="Convert Markdown file to Notion page or update existing page")
    parser.add_argument("file", help="Path to the Markdown file")
    parser.add_argument("url", nargs='?', default=default_parent_url, help="URL of the parent page/database or the page to update")
    parser.add_argument("-t", "--title", help="Title for the Notion page (default: Markdown filename without extension)")
    parser.add_argument("-c", "--column", default=default_title_column, help=f"Name of the title column for database (default: '{default_title_column}')")
    args = parser.parse_args()

    print(f"Markdownファイルを読み込みます: {args.file}")
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        print("Markdownファイルの読み込みが完了しました")
    except FileNotFoundError:
        print(f"エラー: ファイル '{args.file}' が見つかりません。")
        return
    except Exception as e:
        print(f"エラー: ファイルの読み込み中に問題が発生しました: {e}")
        return

    # Markdownの末尾からURLを抽出
    update_url = extract_url_from_markdown(markdown_content)
    
    # URLが見つかった場合は更新モード、そうでない場合は新規作成モード
    if update_url:
        print(f"更新モード: {update_url}")
        parent_url = update_url
        update_mode = True
    else:
        print("新規作成モード")
        update_mode = False
        parent_url = args.url
        if not parent_url:
            print("エラー: 親ページまたはデータベースのURLが指定されていません。コマンドラインで指定するか、config.jsonファイルに設定してください。")
            return

    print("Markdownの変換を開始します")
    # URLの行を除いてからブロックに変換
    markdown_content = re.sub(r"\n//url:https://www\.notion\.so/[^\s]+", "", markdown_content)
    blocks = convert_markdown_to_notion_blocks(markdown_content)
    print("Markdownの変換が完了しました")

    # タイトルが指定されていない場合、Markdownファイルの名前を使用
    if args.title is None:
        args.title = os.path.splitext(os.path.basename(args.file))[0]

    try:
        page_url = create_or_update_notion_page(args.title, blocks, parent_url, args.column, update_mode=update_mode)
        if update_mode:
            print(f"���ージが更新されました: {page_url}")
        else:
            print(f"新しいページが作成されました: {page_url}")
    except Exception as e:
        print(f"エラー: Notionページの作成/更新中に問題が発生しました: {e}")

if __name__ == "__main__":
    main()