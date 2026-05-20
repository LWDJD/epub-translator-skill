"""
EPUB 原文提取脚本

用法：
    python scripts/extract_epub.py <input.epub> [--output-dir chapters_to_translate]

从 EPUB 中提取所有章节的文本段落（p/h1-6/li/td/th），
每个章节输出一个 JSON 文件到指定的输出目录。
"""
import os, sys, json, re, string, argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

PURE_SYMBOL_RE = re.compile(r'^[\d\s' + re.escape(string.punctuation) + r']+$')
SKIP_FILES = {'cover.xhtml', 'navigation.xhtml', 'eula.xhtml', 'nav.xhtml', 'toc.xhtml'}


def extract(epub_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    book = epub.read_epub(epub_path)

    total_paragraphs = 0
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        short_name = item.get_name().split('/')[-1]
        if short_name.lower() in SKIP_FILES or short_name.lower().startswith('ad.'):
            continue

        soup = BeautifulSoup(item.get_body_content(), 'html.parser')
        paragraphs = []
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th']):
            text = tag.get_text(strip=True)
            if not text or len(text) < 3 or PURE_SYMBOL_RE.match(text):
                continue
            paragraphs.append(text)

        if paragraphs:
            out_name = short_name.replace('.xhtml', '.json')
            with open(os.path.join(output_dir, out_name), 'w', encoding='utf-8') as f:
                json.dump({
                    'index': idx,
                    'file_name': item.get_name(),
                    'short_name': short_name,
                    'paragraphs': paragraphs,
                    'count': len(paragraphs),
                }, f, ensure_ascii=False, indent=2)
            print(f"  {out_name:40s} {len(paragraphs):4d} 段")
            total_paragraphs += len(paragraphs)

    print(f"\n共提取 {total_paragraphs} 段，保存到 {output_dir}/")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='从 EPUB 提取原文段落')
    parser.add_argument('input', help='输入的 EPUB 文件路径')
    parser.add_argument('--output-dir', '-o', default='chapters_to_translate',
                        help='输出目录（默认: chapters_to_translate）')
    args = parser.parse_args()
    extract(args.input, args.output_dir)
