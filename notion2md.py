#!/usr/bin/env python3

import os
import json
import argparse
from notion_client import Client
from typing import List, Dict, Any, Tuple
import re
import logging

# ロギングの設定（警告レベル以上のみ出力）
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# Notion APIキーを環境変数から取得
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

# Notionクライアントの初期化
notion = Client(auth=NOTION_TOKEN)

def load_config():
    current_dir = os.getcwd()
    config_path = os.path.join(current_dir, 'config.json')
    
    if not os.path.exists(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: config.jsonが見つかりません。デフォルト設定を使用します。")
        return {}

def get_notion_page_content(page_id: str) -> List[Dict[str, Any]]:
    """Notionページのコンテンツを���トとして取得"""
    blocks = []
    has_more = True
    cursor = None

    while has_more:
        response = notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
        blocks.extend(response["results"])
        has_more = response["has_more"]
        cursor = response["next_cursor"]

    return blocks

def convert_notion_blocks_to_markdown(blocks: List[Dict[str, Any]], page_url: str) -> str:
    markdown = ""
    list_type_stack = []
    processed_blocks = set()

    for block in blocks:
        markdown += convert_block_to_markdown(block, list_type_stack, processed_blocks)

    # URLをmarkdownの最後に追加
    markdown += f"\n\n//url:{page_url}"

    return markdown.strip()

def convert_block_to_markdown(block: Dict[str, Any], list_type_stack: List[str], processed_blocks: set, depth: int = 0) -> str:
    block_id = block["id"]
    if block_id in processed_blocks:
        return ""
    processed_blocks.add(block_id)

    block_type = block["type"]
    markdown = ""
    indent = "  " * depth

    if block_type in ["bulleted_list_item", "numbered_list_item"]:
        markdown += process_list_item(block, list_type_stack, processed_blocks, depth)
    elif block_type == "paragraph":
        markdown += f"{indent}{convert_rich_text_to_markdown(block['paragraph']['rich_text'])}\n\n"
    elif block_type.startswith("heading_"):
        level = int(block_type[-1])
        markdown += f"{indent}{'#' * level} {convert_rich_text_to_markdown(block[block_type]['rich_text'])}\n\n"
    elif block_type == "child_page":
        page_title = block["child_page"]["title"]
        page_id = block["id"]
        markdown += f"{indent}- [{page_title}](https://www.notion.so/{page_id.replace('-', '')})\n\n"
    elif block_type == "code":
        language = block["code"]["language"]
        code_content = convert_rich_text_to_markdown(block["code"]["rich_text"])
        markdown += f"{indent}```{language}\n{code_content}\n{indent}```\n\n"
    elif block_type == "image":
        image_url = block["image"]["file"]["url"]
        markdown += f"{indent}![Image]({image_url})\n\n"
    elif block_type == "divider":
        markdown += f"{indent}---\n\n"
    elif block_type == "quote":
        quote_content = convert_rich_text_to_markdown(block["quote"]["rich_text"])
        markdown += f"{indent}> {quote_content}\n\n"
    elif block_type == "to_do":
        checked = "x" if block["to_do"]["checked"] else " "
        todo_content = convert_rich_text_to_markdown(block["to_do"]["rich_text"])
        markdown += f"{indent}- [{checked}] {todo_content}\n"
    else:
        logging.warning(f"Unsupported block type: {block_type}")

    if "has_children" in block and block["has_children"]:
        children = notion.blocks.children.list(block_id=block["id"])["results"]
        for child in children:
            markdown += convert_block_to_markdown(child, list_type_stack, processed_blocks, depth + 1)

    return markdown

def process_list_item(block: Dict[str, Any], list_type_stack: List[str], processed_blocks: set, depth: int) -> str:
    block_type = block["type"]
    content = convert_rich_text_to_markdown(block[block_type]["rich_text"])
    indent = "  " * depth

    if block_type == "bulleted_list_item":
        markdown = f"{indent}- {content}\n"
        list_type_stack.append("bulleted")
    else:  # numbered_list_item
        if list_type_stack and list_type_stack[-1] == "numbered":
            number = list_type_stack.count("numbered")
        else:
            number = 1
        markdown = f"{indent}{number}. {content}\n"
        list_type_stack.append("numbered")
    
    if "has_children" in block and block["has_children"]:
        children = notion.blocks.children.list(block_id=block["id"])["results"]
        for child in children:
            markdown += convert_block_to_markdown(child, list_type_stack, processed_blocks, depth + 1)
    
    list_type_stack.pop()
    return markdown

def convert_rich_text_to_markdown(rich_text: List[Dict[str, Any]]) -> str:
    """リッチテキストをMarkdownに変換"""
    markdown = ""
    for text in rich_text:
        content = text["plain_text"]
        annotations = text["annotations"]
        if annotations["bold"]:
            content = f"**{content}**"
        if annotations["italic"]:
            content = f"*{content}*"
        if annotations["strikethrough"]:
            content = f"~~{content}~~"
        if annotations["code"]:
            content = f"`{content}`"
        if text.get("href"):
            content = f"[{content}]({text['href']})"
        markdown += content
    return markdown

def get_child_pages(page_id: str) -> List[Dict[str, Any]]:
    """指定さたページの子ページを取得"""
    child_pages = []
    has_more = True
    cursor = None

    while has_more:
        response = notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
        for block in response["results"]:
            if block["type"] == "child_page":
                child_pages.append(block)
        has_more = response["has_more"]
        cursor = response["next_cursor"]

    return child_pages

def get_page_title(page_id: str) -> str:
    """ページのタイトルを取得"""
    page_info = notion.pages.retrieve(page_id)
    return page_info["properties"]["title"]["title"][0]["plain_text"]

def process_page(page_id: str, page_url: str, output_dir: str, depth: int = 0, fetch_children: bool = False):
    """ページを処理してMarkdownファイルを作成"""
    blocks = get_notion_page_content(page_id)
    markdown_content = convert_notion_blocks_to_markdown(blocks, page_url)

    page_title = get_page_title(page_id)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', page_title)  # ファイル名に使えない文字を置換

    # 親ページは指定されたディレクトリに保存
    if depth == 0:
        output_file = os.path.join(output_dir, f"{safe_title}.md")
        if fetch_children:
            child_output_dir = os.path.join(output_dir, safe_title)  # 親ページの名前のフォルダを作成
            os.makedirs(child_output_dir, exist_ok=True)
        else:
            child_output_dir = None
    else:
        # 子ページは親ページの名前のフォルダに保存
        output_file = os.path.join(output_dir, f"{safe_title}.md")
        child_output_dir = output_dir

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"{'  ' * depth}Markdownファイルが作成されました: {output_file}")

    # 子ページを再帰的に処理
    if fetch_children and child_output_dir:
        child_pages = get_child_pages(page_id)
        for child_page in child_pages:
            child_id = child_page["id"]
            child_url = f"https://www.notion.so/{child_id.replace('-', '')}"
            process_page(child_id, child_url, child_output_dir, depth + 1, fetch_children)

def main():
    config = load_config()
    parser = argparse.ArgumentParser(description="Convert Notion page to Markdown file")
    parser.add_argument("url", help="URL of the Notion page")
    parser.add_argument("-o", "--output", help="Output directory for Markdown files")
    parser.add_argument("-c", "--children", action="store_true", help="Fetch child pages")
    args = parser.parse_args()

    # NotionページIDを抽出
    page_id = args.url.split("-")[-1]

    # 親ページのタイトルを取得
    parent_title = get_page_title(page_id)

    # 出力ディレクトリを決定
    if args.output:
        output_dir = args.output
    else:
        output_dir = os.getcwd()
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"出力ディレクトリ: {output_dir}")

    # メインページを処理
    process_page(page_id, args.url, output_dir, fetch_children=args.children)

if __name__ == "__main__":
    main()