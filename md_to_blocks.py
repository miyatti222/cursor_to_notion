import re
from typing import List, Dict, Any, Tuple
import json
import sys

def convert_markdown_to_notion_blocks(markdown: str) -> List[Dict[str, Any]]:
    print("convert_markdown_to_notion_blocks 関数を開始します")
    try:
        blocks = []
        lines = markdown.split('\n')
        print(f"行数: {len(lines)}")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            print(f"処理中の行: {i + 1}")
            
            if not line:
                i += 1
                continue
            
            # ヘッダー
            if line.startswith('#'):
                print("ヘッダーを処理します")
                level = len(line.split()[0])
                content = line.lstrip('#').strip()
                blocks.append({
                    "object": "block",
                    "type": f"heading_{level}",
                    f"heading_{level}": {
                        "rich_text": [parse_inline_formatting(content)]
                    }
                })
            
            # リスト（箇条書きと番���
            elif line.lstrip().startswith('- ') or line.lstrip().startswith('* ') or re.match(r'^\s*\d+\.', line):
                print("リストを処理します")
                list_items, new_i = process_list_items(lines, i)
                blocks.extend(list_items)
                if new_i <= i:
                    print(f"警告: リスト処理でインデックスが進みませんでした。強制的に次の行に進みます。")
                    i += 1
                else:
                    i = new_i
                continue
            
            # コードブロック
            elif line.startswith('```'):
                print("コードブロックを処理します")
                language = line[3:].strip() or "plain_text"
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                        "language": language
                    }
                })
            
            # 水平線
            elif line == '---' or line == '***' or line == '___':
                print("水平線を処理します")
                blocks.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
            
            # テーブル
            elif '|' in line:
                print("テーブルを処理します")
                table_rows = []
                while i < len(lines) and '|' in lines[i]:
                    table_rows.append(lines[i])
                    i += 1
                i -= 1  # Adjust for the extra increment
                
                # テーブルの処理
                table_block = process_table(table_rows)
                if table_block:
                    blocks.append(table_block)
            
            # 通常のテキスト
            else:
                print("段落を処理します")
                try:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [parse_inline_formatting(line)]
                        }
                    })
                except ValueError as e:
                    print(f"警告: {e}. 行をスキップします: {line}")
            
            i += 1
        
        print("すべての行の処理が完了しました")
        return blocks
    except Exception as e:
        print(f"Markdownの変換中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        raise

def parse_inline_formatting(text: str) -> Dict[str, Any]:
    # イタリック、太字、リンクの処理
    formatted_text = {
        "type": "text",
        "text": {"content": text},
        "annotations": {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default"
        }
    }
    
    # 太字
    bold_pattern = r'\*\*(.*?)\*\*'
    if re.search(bold_pattern, text):
        formatted_text["annotations"]["bold"] = True
        text = re.sub(bold_pattern, r'\1', text)
    
    # イタリック
    italic_pattern = r'\*(.*?)\*'
    if re.search(italic_pattern, text):
        formatted_text["annotations"]["italic"] = True
        text = re.sub(italic_pattern, r'\1', text)
    
    # リンク
    link_pattern = r'\[(.*?)\]\((.*?)\)'
    match = re.search(link_pattern, text)
    if match:
        link_text, url = match.groups()
        # URLがhttpまたはhttpsで始まる場合のみ検証
        if re.match(r"https?://", url):
            if not re.match(r"https?://", url):
                raise ValueError(f"Invalid URL: {url}")
            formatted_text["text"]["content"] = link_text
            formatted_text["text"]["link"] = {"url": url}
            text = re.sub(link_pattern, link_text, text)
    
    formatted_text["text"]["content"] = text
    return formatted_text

def process_table(table_rows: List[str]) -> Dict[str, Any]:
    if len(table_rows) < 3:
        return None  # テーブルには少なくともヘッダー行、区切り行、データ行が必要

    # ヘッダー行の処理
    header = [cell.strip() for cell in table_rows[0].split('|')[1:-1]]
    
    # データ行の処理
    rows = []
    for row in table_rows[2:]:
        cells = [cell.strip() for cell in row.split('|')[1:-1]]
        rows.append(cells)
    
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(header),
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                {
                    "type": "table_row",
                    "table_row": {
                        "cells": [[{"type": "text", "text": {"content": cell}}] for cell in row]
                    }
                } for row in [header] + rows
            ]
        }
    }

def process_list_items(lines: List[str], start_index: int) -> Tuple[List[Dict[str, Any]], int]:
    print(f"process_list_items 関数を開始します。開始インデックス: {start_index}")
    list_items = []
    current_indent = 0
    stack = []
    i = start_index

    while i < len(lines):
        line = lines[i].rstrip()
        print(f"  処理中のリスト行: {i + 1}")
        if not line or (not line.lstrip().startswith('- ') and not line.lstrip().startswith('* ') and not re.match(r'^\s*\d+\.', line)):
            break

        indent = len(line) - len(line.lstrip())
        is_numbered = re.match(r'^\s*\d+\.', line)
        content = line.lstrip('- *').lstrip()
        if is_numbered:
            content = re.sub(r'^\d+\.\s*', '', content)
            list_type = "numbered_list_item"
        else:
            list_type = "bulleted_list_item"

        item = {
            "object": "block",
            "type": list_type,
            list_type: {
                "rich_text": [parse_inline_formatting(content)]
            }
        }

        if indent > current_indent:
            stack.append(list_items[-1])
            current_indent = indent
        elif indent < current_indent:
            while stack and indent <= current_indent:
                stack.pop()
                current_indent -= 2

        if stack:
            parent = stack[-1]
            if "children" not in parent[parent["type"]]:
                parent[parent["type"]]["children"] = []
            parent[parent["type"]]["children"].append(item)
        else:
            list_items.append(item)

        i += 1

    print(f"process_list_items 関数を終了します。終了インデックス: {i}")
    return list_items, i

def main():
    if len(sys.argv) != 2:
        print("使用方法: python md_to_blocks.py <markdown_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            markdown_content = file.read()
        
        blocks = convert_markdown_to_notion_blocks(markdown_content)
        print(json.dumps(blocks, indent=2, ensure_ascii=False))
    except FileNotFoundError:
        print(f"エラー: ファイル '{file_path}' が見つかりません。")
        sys.exit(1)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()