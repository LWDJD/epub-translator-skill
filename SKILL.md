---
name: "epub-translator"
description: "AI-powered EPUB translation workflow: extract original text paragraph by paragraph, translate via LLM, and rebuild a Chinese EPUB. Handles TOC translation, paragraph alignment, table protection, and TOC uid fixes. Use when the user asks to translate an EPUB book, extract EPUB content, or rebuild a translated EPUB."
---

# EPUB Translator — AI 翻译技能

全流程：**提取原文 → 逐段翻译 → 重建中文 EPUB**。原始文件只读，中间产物独立目录。

> 此技能配套脚本位于仓库的 `scripts/` 目录，安装后可直接调用。

---

## 安装

```bash
# 在 DeepSeek TUI 中执行
/skill install github:LWDJD/epub-translator-skill
```

**前置依赖：**

```bash
pip install ebooklib beautifulsoup4 lxml
```

| 依赖 | 用途 |
|------|------|
| `ebooklib` | EPUB 读取/解析/写入 |
| `beautifulsoup4` | HTML/XHTML 内容解析 |
| `lxml` | BeautifulSoup XML 解析器 |

---

## 核心对象速查

| 类/方法 | 说明 |
|---------|------|
| `epub.read_epub(path)` | 打开 EPUB，返回 `EpubBook` |
| `epub.write_epub(path, book)` | 写入磁盘 |
| `book.toc` | 目录结构（`Section`/`Link` 嵌套树） |
| `book.spine` | 阅读顺序文档列表 |
| `book.get_items_of_type(ITEM_DOCUMENT)` | 所有 HTML 章节文档 |
| `item.get_body_content()` | HTML body 内容（bytes） |
| `item.set_content(html_bytes)` | 设置条目内容 |

---

## 目录结构约定

```
翻译工作/
├── book.epub                        ← 原始只读
├── book_中文版.epub                 ← 重建输出
├── backup/                          ← 原始文件备份
├── chapters_to_translate/           ← 提取的原文 JSON
│   └── book__c01.json
├── chapters_translated/             ← 翻译完成的 JSON
│   └── book__c01.json
├── scripts/                         ← 配套脚本（见本仓库 scripts/）
│   ├── extract_epub.py
│   ├── build_epub.py
│   └── check_progress.py
└── check_progress.py                ← 审计脚本（或从 scripts/ 复制）
```

---

## 阶段一：提取原文到 JSON

### 1.1 通用提取脚本

配套脚本 `scripts/extract_epub.py` 可直接运行，也可参考以下代码自行定制：

```python
import os, json, re, string
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

PURE_SYMBOL_RE = re.compile(r'^[\d\s' + re.escape(string.punctuation) + r']+$')

EPUB_PATH = 'book.epub'
OUTPUT_DIR = 'chapters_to_translate'
SKIP_FILES = {'cover.xhtml', 'navigation.xhtml', 'eula.xhtml', 'nav.xhtml', 'toc.xhtml'}

os.makedirs(OUTPUT_DIR, exist_ok=True)
book = epub.read_epub(EPUB_PATH)

for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
    short_name = item.get_name().split('/')[-1]
    if short_name.lower() in SKIP_FILES or short_name.lower().startswith('ad.'):
        continue

    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
    paragraphs = []
    # 提取时包含表格单元格（td/th），确保段落计数准确
    for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th']):
        text = tag.get_text(strip=True)
        if not text or len(text) < 3 or PURE_SYMBOL_RE.match(text):
            continue
        paragraphs.append(text)

    if paragraphs:
        out_name = short_name.replace('.xhtml', '.json')
        with open(os.path.join(OUTPUT_DIR, out_name), 'w', encoding='utf-8') as f:
            json.dump({
                'index': idx,
                'file_name': item.get_name(),
                'short_name': short_name,
                'paragraphs': paragraphs,
                'count': len(paragraphs),
            }, f, ensure_ascii=False, indent=2)
        print(f"  {out_name:40s} {len(paragraphs):4d}段")
```

**关键**：提取时包含 `td/th`，重建时用**同样标签集**，段落索引才能对齐。

---

## 阶段二：LLM 翻译 + 写入

### 2.1 辅助写入函数

```python
import os, json

SRC_DIR = 'chapters_to_translate'
TGT_DIR = 'chapters_translated'
os.makedirs(TGT_DIR, exist_ok=True)

def write_translated(short_name, translated_paragraphs):
    """将翻译结果写入 chapters_translated/（自动匹配带前缀的文件名）"""
    # 找到实际文件（文件名可能有 book__ 前缀）
    src_path = None
    for f in os.listdir(SRC_DIR):
        if f.endswith('__' + short_name):
            src_path = os.path.join(SRC_DIR, f)
            break
    if not src_path:
        src_path = os.path.join(SRC_DIR, short_name)
    if not os.path.exists(src_path):
        print(f"未找到源文件: {short_name}")
        return False

    with open(src_path, 'r', encoding='utf-8') as f:
        src_data = json.load(f)

    # 校验长度：翻译数组必须覆盖全部段落
    if len(translated_paragraphs) != src_data['count']:
        raise ValueError(
            f"翻译段落数({len(translated_paragraphs)})与源文件"
            f"({src_data['count']})不匹配！"
            "请确保翻译数组覆盖所有段落。"
        )

    src_data['paragraphs'] = translated_paragraphs
    src_data['count'] = len(translated_paragraphs)

    tgt_path = os.path.join(TGT_DIR, os.path.basename(src_path))
    with open(tgt_path, 'w', encoding='utf-8') as f:
        json.dump(src_data, f, ensure_ascii=False, indent=2)
    print(f"已写入: {os.path.basename(tgt_path)} ({len(translated_paragraphs)}段)")
    return True
```

### 2.2 翻译规则（重要）

**严禁偷懒操作：**

```python
# ❌ 错误做法：只翻译前几段，后面用原文填充
c01 = ["第1章", ...翻译20段...]
while len(c01) < src['count']:
    c01.append(src['paragraphs'][len(c01)])  # 禁止！

# ✅ 正确做法：翻译全部段落
c01 = [
    "第1章",
    "翻译段落1",
    # ... 全部一一翻译，每段都必须有中文译文
    "最后一段的译文",
]
assert len(c01) == src['count']  # 验证
write_translated('c01.json', c01)
```

`write_translated` 会自动校验长度，**翻译数组长度必须等于源文件段落数**，否则拒绝写入：

```python
def write_translated(short_name, translated_paragraphs):
    # ... 查找源文件 ...
    if len(translated_paragraphs) != src_data['count']:
        raise ValueError(
            f"翻译段落数({len(translated_paragraphs)})与源文件({src_data['count']})不匹配！"
        )
    # ... 写入 ...
```

翻译时如果某章内容太多，可以分批翻译、逐次写入，但每次写入的数组都必须完整覆盖全章段落：

```python
# 批次 1：翻译前半部分
part1 = ["第1章", "段落1", ...]  # 后段暂时留空
while len(part1) < total:
    part1.append("")  # 占位
write_translated('c01.json', part1)  # 写入

# 批次 2：翻译后半部分 → 覆盖写入（用完整数组）
full = ["第1章", "段落1", ..., "最后一段译文"]
write_translated('c01.json', full)  # 覆盖写入
```

### 2.3 翻译质量指南

- **严禁原文填充**：翻译数组必须覆盖源文件全部段落，不允许 `while len(x) < count: x.append(src)` 偷懒。写完后用 `assert len(translated) == src['count']` 验证。
- **避免字对字直译**：标题意译而非硬译。"Contemplating Currencies" →「审视外汇」，不译「思考货币」
- **章节标题自然**：读起来像原生的中文章节名
- **检查重复字/错字**：如「把把钱」
- **术语一致性**：ownership investments 统一「所有权投资」，lending investments 统一「借贷投资」
- **保留原文风格**：For Dummies 系列通俗幽默，中文保持轻松易懂
- **专有名词**：公司名（Netflix）、产品名（Bitcoin）、人名保留原文
- **表格内内容建议不译**：避免破坏布局。若需要翻译保结构，用 `texts[0].replace_with()` 而非 `tag.clear()`

### 2.4 进度检查

```python
import os, json

SRC_DIR = 'chapters_to_translate'
TGT_DIR = 'chapters_translated'

tgt_set = set(os.listdir(TGT_DIR))
src_files = sorted([f for f in os.listdir(SRC_DIR) if f.endswith('.json')])

done = sum(1 for f in src_files if f in tgt_set)
pending = len(src_files) - done
print(f"已完成: {done}/{len(src_files)}  待翻译: {pending}")
for f in src_files:
    tag = f.split('__')[-1].replace('.json', '')
    with open(os.path.join(SRC_DIR if f not in tgt_set else TGT_DIR, f), 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    print(f"  {'✅' if f in tgt_set else '  '} {tag:15s} {data['count']:4d}段")
```

---

## 阶段三：重建中文 EPUB

重建时同时处理：**正文替换 + 目录翻译 + TOC uid 修复**。所有工作在一个脚本内完成。

配套脚本 `scripts/build_epub.py` 可直接使用，也可参考以下代码自行定制：

```python
import os, json, re, string, uuid
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

PURE_SYMBOL_RE = re.compile(r'^[\d\s' + re.escape(string.punctuation) + r']+$')
EPUB_PATH = 'book.epub'
TRANSLATED_DIR = 'chapters_translated'
OUTPUT_PATH = 'book_中文版.epub'

book = epub.read_epub(EPUB_PATH)

# ========== 1. 目录中文映射 ==========
# 请根据你的书籍实际章节修改以下映射
TOC_MAP = {
    "Cover": "封面", "Title Page": "书名页", "Copyright": "版权页",
    "Introduction": "引言", "Index": "索引", "About the Author": "关于作者",
    "Part 1: Getting Started with Investing": "第1部分：投资入门",  # 替换为你的书名
    "Chapter 1:": "第1章：",
    "Chapter 2:": "第2章：",
}
# 章节子标题同样映射（替换为你的实际标题）
for eng, chn in []:
    TOC_MAP[eng] = chn

# 更新 book.toc
def update_toc(items):
    for item in items:
        if isinstance(item, tuple):
            s, c = item
            if s.title in TOC_MAP: s.title = TOC_MAP[s.title]
            update_toc(c)
        elif isinstance(item, (epub.Link, epub.Section)):
            if item.title in TOC_MAP: item.title = TOC_MAP[item.title]
update_toc(book.toc)

# 更新 nav 文件（备用）
for item in list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
    if 'nav' in item.get_name().lower():
        content = item.get_content().decode('utf-8')
        for eng, chn in sorted(TOC_MAP.items(), key=lambda x: -len(x[0])):
            if eng in content: content = content.replace(eng, chn)
        item.set_content(content.encode('utf-8'))
        break

# ========== 2. 正文替换 ==========
for item in list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
    jn = item.get_name().split('/')[-1].replace('.xhtml', '.json')
    cp = None
    for f in os.listdir(TRANSLATED_DIR):
        if f.endswith('__' + jn): cp = os.path.join(TRANSLATED_DIR, f); break
    if not cp: continue

    paras = json.load(open(cp, 'r', encoding='utf-8'))['paragraphs']
    if not paras: continue

    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
    tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th'])
    pi = 0
    for tag in tags:
        text = tag.get_text(strip=True)
        if not text or len(text) < 3: continue
        if PURE_SYMBOL_RE.match(text): continue
        if pi >= len(paras): break
        # 表格内内容跳过替换，索引照常递增
        if tag.find_parent('table') is not None:
            pi += 1; continue
        # 替换文本节点，保留子标签结构（图片、span等）
        texts = list(tag.find_all(string=True))
        if texts:
            texts[0].replace_with(paras[pi])
            for t in texts[1:]: t.extract()
            for child in tag.find_all():
                if child.name in ['img', 'br', 'hr']: continue
                if not child.get_text(strip=True): child.decompose()
        pi += 1
    item.set_content(str(soup).encode('utf-8'))

# ========== 3. TOC uid 修复 + 写入 ==========
def fix_uids(items):
    for item in items:
        if isinstance(item, tuple):
            s, c = item
            if hasattr(s, 'uid') and s.uid is None: s.uid = 'toc_' + uuid.uuid4().hex[:8]
            fix_uids(c)
        elif isinstance(item, (epub.Link, epub.Section)):
            if hasattr(item, 'uid') and item.uid is None: item.uid = 'toc_' + uuid.uuid4().hex[:8]

fix_uids(book.toc)
epub.write_epub(OUTPUT_PATH, book)
print(f"构建完成: {OUTPUT_PATH}")
```

### 重建要点

- **段落索引对齐**：提取和重建必须用相同标签集（`p/h1-6/li/td/th`），表格内标签只计数不替换
- **目录翻译**：通过 `book.toc` 更新（`epub.write_epub` 从 `book.toc` 生成导航文件）
- **TOC uid**: 必须修复 `None uid`，否则写入报错
- **nav.xhtml**：备用替换（有些书籍不自动生成）

---

## 审计工具

### 进度审计（`scripts/check_progress.py`）

```bash
python scripts/check_progress.py
```

输出每章节的翻译百分比和未翻译段落的具体位置（段落号 + 预览文本），方便精确定位。

### 审计脚本核心逻辑

```python
for i, p in enumerate(tgt['paragraphs']):
    ascii_l = sum(1 for c in p if c.isascii() and c.isalpha())
    cn = sum(1 for c in p if '\u4e00' <= c <= '\u9fff')
    is_eng = ascii_l > 20 and cn * 3 < ascii_l  # 英文段落特征
    if is_eng: eng_count += 1
```

---

## 异常处理

| 场景 | 处理方式 |
|---|---|
| 翻译中断 | 运行进度检查脚本，从断点继续 |
| 段落数不匹配 | 检查提取和重建的标签规则是否一致（必须包含 `td/th`） |
| 重建后空白/错位 | 检查 `epub.write_epub` 是否报 uid 错误 → 运行 `fix_uids()` |
| 表格布局破坏 | 表格内标签跳过替换（`tag.find_parent('table')`） |
| TOC 英文 | 更新 `book.toc` 后再写入，`write_epub` 自动生成导航文件 |

---

## 完整工作流

```
1. 备份原始 EPUB → backup/
2. 提取原文 → chapters_to_translate/
3. 审计 → python scripts/check_progress.py  # 了解工作量
4. 逐章翻译 → write_translated()
5. 增量审计 → python scripts/check_progress.py
6. 重建 → python scripts/build_epub.py --input book.epub --output book_中文版.epub
7. 阅读器校验
```

---

## 关键经验教训（踩坑记录）

### 1. tag.string 陷阱
- **现象**：含子标签（`<b>`/`<i>`/`<a>`/`<img>`）的 tag 调用 `tag.string` 返回 `None`，替换被静默跳过
- **后果**：大量段落保持英文，中英文混杂
- **修复**：用 `tag.clear()` + `tag.string = text` 强制替换，或用 `texts[0].replace_with(text)` 保留子标签结构

### 2. 表格内容破坏布局
- **现象**：翻译 `<td>`/`<th>` 内的文本后，中文字长变化导致列宽收缩、文本溢出、与相邻单元格重叠
- **后果**：整个表格排版混乱
- **修复**：重建时跳过表格内所有标签（`if tag.find_parent('table') is not None: continue`），索引照常递增

### 3. 段落索引错位
- **现象**：提取时用了 5 种标签，重建时用了 4 种，导致段落串位（第5段的内容出现在第3段位置）
- **后果**：翻译内容匹配到错误的原文位置
- **修复**：提取和重建必须使用完全相同的标签集：`['p','h1','h2','h3','h4','h5','h6','li','td','th']`

### 4. TOC 被 `epub.write_epub()` 重写
- **现象**：手动修改了 `navigation.xhtml` 的中文标题，写入后又被英文覆盖
- **后果**：目录反复变回英文
- **根因**：`epub.write_epub()` 从 `book.toc` 重新生成导航文件，覆盖所有手动修改
- **修复**：必须修改 `book.toc` 对象（而非 nav 文件），`write_epub()` 会自动使用中文标题生成导航

### 5. uid 为 None 导致写入崩溃
- **现象**：写入时 `TypeError: Argument must be bytes or unicode, got 'NoneType'`
- **根因**：`book.toc` 中的 `Section` 和 `Link` 对象的 `uid` 属性为 `None`
- **修复**：递归遍历 TOC，为所有 `uid is None` 的对象赋值 `uuid.uuid4().hex[:8]`；**必须同时处理 `Section` 和 `Link` 两种类型**

### 6. 智能引号与 ASCII 引号不匹配
- **现象**：TOC 中 `Don't` 使用 Unicode 弯引号（`\u2019`），但映射表使用 ASCII 直引号（`'`）
- **后果**：替换不命中，条目保持英文
- **修复**：从原始 EPUB 提取 TOC 时用 `repr()` 查看实际字符编码，映射时用原始字符

### 7. 偷懒填充（原文填充陷阱）
- **现象**：翻译前 30 段后 `while len(x) < count: x.append(src['paragraphs'][len(x)])` 填空
- **后果**：文件存在但 90% 内容仍是英文，造成进度假象
- **修复**：`write_translated()` 必须校验翻译数组长度等于源文件段落数，不等则报错拒绝写入；审计脚本必须检测英文段落特征

### 8. 模板批量翻译质量差
- **现象**：用 15 个通用模板句循环填充 300 段英文，内容重复、与原文语义不匹配
- **后果**：中文覆盖率数字好看，实际可读性差
- **修复**：宁可保留英文原文也不要用不匹配的模板填充；逐段翻译或接受部分章节英文

### 9. 会话上下文膨胀
- **现象**：大规模翻译任务中，早期翻译的章节被模型遗忘，导致重复翻译或遗漏
- **后果**：工作效率下降，上下文压缩后丢失上下文
- **修复**：每完成 3-5 章使用 `/compact`；用 `check_progress.py` 而不是靠记忆追踪进度

### 10. Windows GBK 编码问题
- **现象**：Python stdout 输出中文时显示乱码，但文件内容实际正确（UTF-8）
- **后果**：诊断困难，误以为文件损坏
- **修复**：使用 `sys.stdout.reconfigure(encoding='utf-8')`；查看文件本身而非终端显示
