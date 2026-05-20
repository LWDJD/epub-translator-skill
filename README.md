# EPUB Translator Skill

[![DeepSeek TUI Skill](https://img.shields.io/badge/DeepSeek%20TUI-Skill-blue)](https://deepseek-tui.com)

一个 **AI 翻译 EPUB 电子书** 的 DeepSeek TUI 技能。在 DeepSeek TUI 中安装后，Agent 会自动完成全流程：

**提取原文 → 逐段翻译 → 重建中文 EPUB**

无需手动运行脚本，只需告诉 Agent 要翻译哪本书即可。

## 安装

在 DeepSeek TUI 中运行：

```
/skill install github:LWDJD/epub-translator-skill
```

Agent 会自动安装 Python 依赖（`ebooklib`、`beautifulsoup4`、`lxml`）。

## 使用方式

安装后告诉 Agent：

> "翻译这本书 [book.epub]"
> "提取这本 EPUB 的内容"
> "把翻译结果重建成中文 EPUB"

Agent 会调用此技能，按 SKILL.md 中的流程逐步完成翻译工作。

## 仓库结构

```
├── SKILL.md                  ← 技能主文件（完整工作流 + 代码示例 + 排错指南）
├── README.md                 ← 本文件
├── requirements.txt          ← Python 依赖
└── scripts/
    ├── extract_epub.py       ← 提取原文段落
    ├── build_epub.py         ← 重建中文 EPUB
    └── check_progress.py     ← 翻译进度审计
```

## 许可

MIT
