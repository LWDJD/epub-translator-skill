"""
EPUB 重建脚本：将翻译后的 JSON 写回 EPUB

用法：
    python scripts/build_epub.py --input book.epub \\
        --translated chapters_translated --output book_中文版.epub

同时处理：
    - 正文段落替换（保留子标签结构，跳过表格内容）
    - 目录翻译（TOC → 中文）
    - TOC uid 修复（避免 None 崩溃）
"""
import os, sys, json, re, string, uuid, argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

PURE_SYMBOL_RE = re.compile(r'^[\d\s' + re.escape(string.punctuation) + r']+$')


def build_toc_map() -> dict:
    """
    返回默认的 TOC 中文映射。
    请根据你的书籍修改此函数，或通过 --toc-map 传入 JSON 文件。
    """
    # ========== 在这里添加你的章节映射 ==========
    return {
        "Cover": "封面",
        "Title Page": "书名页",
        "Copyright": "版权页",
        "Introduction": "引言",
        "Index": "索引",
        "About the Author": "关于作者",
    }


def update_toc(items, toc_map: dict):
    for item in items:
        if isinstance(item, tuple):
            s, c = item
            if hasattr(s, 'title') and s.title in toc_map:
                s.title = toc_map[s.title]
            update_toc(c, toc_map)
        elif isinstance(item, (epub.Link, epub.Section)):
            if hasattr(item, 'title') and item.title in toc_map:
                item.title = toc_map[item.title]


def fix_uids(items):
    for item in items:
        if isinstance(item, tuple):
            s, c = item
            if hasattr(s, 'uid') and s.uid is None:
                s.uid = 'toc_' + uuid.uuid4().hex[:8]
            fix_uids(c)
        elif isinstance(item, (epub.Link, epub.Section)):
            if hasattr(item, 'uid') and item.uid is None:
                item.uid = 'toc_' + uuid.uuid4().hex[:8]


def build(input_path: str, translated_dir: str, output_path: str, toc_map: dict):
    book = epub.read_epub(input_path)

    # ---- 1. 目录翻译 ----
    update_toc(book.toc, toc_map)
    for item in list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        if 'nav' in item.get_name().lower():
            content = item.get_content().decode('utf-8')
            for eng, chn in sorted(toc_map.items(), key=lambda x: -len(x[0])):
                if eng in content:
                    content = content.replace(eng, chn)
            item.set_content(content.encode('utf-8'))
            break

    # ---- 2. 正文替换 ----
    for item in list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        jn = item.get_name().split('/')[-1].replace('.xhtml', '.json')
        cp = None
        for f in os.listdir(translated_dir):
            if f.endswith('__' + jn):
                cp = os.path.join(translated_dir, f)
                break
        if not cp:
            continue

        with open(cp, 'r', encoding='utf-8') as fh:
            paras = json.load(fh)['paragraphs']
        if not paras:
            continue

        soup = BeautifulSoup(item.get_body_content(), 'html.parser')
        tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th'])
        pi = 0
        for tag in tags:
            text = tag.get_text(strip=True)
            if not text or len(text) < 3 or PURE_SYMBOL_RE.match(text):
                continue
            if pi >= len(paras):
                break
            if tag.find_parent('table') is not None:
                pi += 1
                continue
            texts = list(tag.find_all(string=True))
            if texts:
                texts[0].replace_with(paras[pi])
                for t in texts[1:]:
                    t.extract()
                for child in tag.find_all():
                    if child.name in ['img', 'br', 'hr']:
                        continue
                    if not child.get_text(strip=True):
                        child.decompose()
            pi += 1
        item.set_content(str(soup).encode('utf-8'))

    # ---- 3. TOC uid 修复 + 写入 ----
    fix_uids(book.toc)
    epub.write_epub(output_path, book)

    size_mb = os.path.getsize(output_path) / (1024 ** 2)
    print(f"构建完成: {output_path} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='重建翻译后的中文 EPUB')
    parser.add_argument('--input', '-i', required=True, help='原始 EPUB 文件路径')
    parser.add_argument('--translated', '-t', default='chapters_translated',
                        help='翻译 JSON 目录（默认: chapters_translated）')
    parser.add_argument('--output', '-o', default=None,
                        help='输出 EPUB 路径（默认: <输入文件名>_中文版.epub）')
    parser.add_argument('--toc-map', default=None,
                        help='TOC 映射 JSON 文件（可选）')
    args = parser.parse_args()

    output = args.output
    if not output:
        base, ext = os.path.splitext(args.input)
        output = f"{base}_中文版.epub"

    toc_map = build_toc_map()
    if args.toc_map:
        with open(args.toc_map, 'r', encoding='utf-8') as f:
            toc_map.update(json.load(f))

    build(args.input, args.translated, output, toc_map)
