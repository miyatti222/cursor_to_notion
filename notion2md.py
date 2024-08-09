#!/usr/bin/env python3

import os
import json
import argparse
from notion_client import Client, APIResponseError
from typing import List, Dict, Any
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
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
        logging.warning("config.jsonが見つかりません。デフォルト設定を使用します。")
        return {}

def extract_id_from_url(url: str) -> str:
    match = re.search(r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url)
    return match.group(1).replace("-", "") if match else None

def get_block_children(block_id: str, start_cursor: str = None) -> Dict[str, Any]:
    return notion.blocks.children.list(block_id=block_id, start_cursor=start_cursor)

def get_page_content(page_id: str) -> List[Dict[str, Any]]:
    blocks = []
    start_cursor = None

    while True:
        response = get_block_children(page_id, start_cursor)
        blocks.extend(response["results"])
        if not response["has_more"]:
            break
        start_cursor = response["next_cursor"]

    return blocks

def block_to_markdown(block: Dict[str, Any], depth: int = 0) -> str:
    block_type = block["type"]
    indent = "  " * depth

    if block_type == "paragraph":
        return f"{indent}{text_to_markdown(block['paragraph']['rich_text'])}\n"
    elif block_type.startswith("heading_"):
        level = int(block_type[-1])
        return f"{indent}{'#' * level} {text_to_markdown(block[block_type]['rich_text'])}\n"
    elif block_type == "to_do":
        checked = "x" if block["to_do"]["checked"] else " "
        return f"{indent}- [{checked}] {text_to_markdown(block['to_do']['rich_text'])}\n"
    elif block_type == "code":
        language = block["code"]["language"]
        code = text_to_markdown(block["code"]["rich_text"])
        return f"{indent}```{language}\n{code}\n```\n"
    elif block_type == "quote":
        return f"{indent}> {text_to_markdown(block['quote']['rich_text'])}\n"
    elif block_type == "divider":
        return f"{indent}---\n"
    elif block_type == "image":
        caption = text_to_markdown(block["image"].get("caption", []))
        url = block["image"]["file"]["url"]
        return f"{indent}![{caption}]({url})\n"
    elif block_type in ["numbered_list_item", "bulleted_list_item"]:
        if block_type == "numbered_list_item":
            return f"{indent}1. {text_to_markdown(block[block_type]['rich_text'])}\n"
        else:
            return f"{indent}- {text_to_markdown(block[block_type]['rich_text'])}\n"
    else:
        return ""

def text_to_markdown(rich_text: List[Dict[str, Any]]) -> str:
    markdown = ""
    for text in rich_text:
        content = text["plain_text"]
        if text.get("href"):
            content = f"[{content}]({text['href']})"
        if text["annotations"]["bold"]:
            content = f"**{content}**"
        if text["annotations"]["italic"]:
            content = f"*{content}*"
        if text["annotations"]["strikethrough"]:
            content = f"~~{content}~~"
        if text["annotations"]["code"]:
            content = f"`{content}`"
        markdown += content
    return markdown

def get_page_title(page_id: str) -> str:
    try:
        page = notion.pages.retrieve(page_id)
        for prop_name, prop_value in page["properties"].items():
            if prop_value["type"] == "title":
                if prop_value["title"]:
                    return prop_value["title"][0]["plain_text"]
    except APIResponseError as e:
        if "Could not find page" in str(e):
            try:
                database = notion.databases.retrieve(page_id)
                if database["title"]:
                    return database["title"][0]["plain_text"]
            except APIResponseError:
                pass
        logging.error(f"APIエラー: {str(e)}")
    except Exception as e:
        logging.error(f"予期せぬエラー: {str(e)}")
    return "Untitled"

def get_database_entries(database_id: str) -> List[Dict[str, Any]]:
    results = []
    has_more = True
    next_cursor = None
    while has_more:
        response = notion.databases.query(
            database_id=database_id,
            start_cursor=next_cursor
        )
        results.extend(response["results"])
        has_more = response["has_more"]
        next_cursor = response["next_cursor"]
    return results

def process_blocks(blocks: List[Dict[str, Any]], depth: int = 0) -> str:
    markdown = ""
    list_type = None
    list_depth = 0

    for block in blocks:
        block_type = block["type"]

        if block_type in ["numbered_list_item", "bulleted_list_item"]:
            if list_type != block_type:
                list_type = block_type
                list_depth = depth
            indent = "  " * depth
            if block_type == "numbered_list_item":
                markdown += f"{indent}1. {text_to_markdown(block[block_type]['rich_text'])}\n"
            else:
                markdown += f"{indent}- {text_to_markdown(block[block_type]['rich_text'])}\n"

            if block.get("has_children"):
                child_blocks = get_page_content(block["id"])
                markdown += process_blocks(child_blocks, depth + 1)
        else:
            list_type = None
            markdown += block_to_markdown(block, depth)

            if block.get("has_children"):
                child_blocks = get_page_content(block["id"])
                markdown += process_blocks(child_blocks, depth + 1)

    return markdown

def notion_to_md(page_id: str, output_dir: str, fetch_children: bool = False):
    page_id = page_id.replace("-", "")
    try:
        page = notion.pages.retrieve(page_id)
        is_database = False
    except APIResponseError:
        page = notion.databases.retrieve(page_id)
        is_database = True

    page_title = get_page_title(page_id)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', page_title)
    output_file = os.path.join(output_dir, f"{safe_title}.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {page_title}\n\n")
        if is_database:
            entries = get_database_entries(page_id)
            for entry in entries:
                entry_title = entry["properties"].get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled")
                entry_id = entry["id"]
                f.write(f"- [{entry_title}](https://www.notion.so/{entry_id.replace('-', '')})\n")
        else:
            blocks = get_page_content(page_id)
            markdown = process_blocks(blocks)
            f.write(markdown)
        f.write(f"\n\n//url:https://www.notion.so/{page_id}")

    logging.info(f"Markdownファイルが作成されました: {output_file}")

    if fetch_children:
        if is_database:
            entries = get_database_entries(page_id)
            for entry in entries:
                entry_id = entry["id"]
                entry_title = entry["properties"].get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled")
                child_output_dir = os.path.join(output_dir, safe_title)
                os.makedirs(child_output_dir, exist_ok=True)
                notion_to_md(entry_id, child_output_dir, fetch_children)
        else:
            child_blocks = [b for b in blocks if b["type"] == "child_page"]
            for child in child_blocks:
                child_id = child["id"]
                child_output_dir = os.path.join(output_dir, safe_title)
                os.makedirs(child_output_dir, exist_ok=True)
                notion_to_md(child_id, child_output_dir, fetch_children)

def main():
    config = load_config()
    parser = argparse.ArgumentParser(description="Convert Notion page to Markdown file")
    parser.add_argument("url", nargs='?', help="URL of the Notion page or database")
    parser.add_argument("-o", "--output", help="Output directory for Markdown files")
    parser.add_argument("-c", "--children", action="store_true", help="Fetch child pages")
    args = parser.parse_args()

    if not args.url:
        args.url = config.get("default_parent_url")
        if not args.url:
            logging.error("エラー: URLが指定されておらず、config.jsonにも定義されていません。")
            return

    page_id = extract_id_from_url(args.url)
    if not page_id:
        logging.error("エラー: 有効なNotionページIDがURLから抽出できませんでした。")
        return

    output_dir = args.output or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"出力ディレクトリ: {output_dir}")

    try:
        notion_to_md(page_id, output_dir, args.children)
    except Exception as e:
        logging.error(f"エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main()