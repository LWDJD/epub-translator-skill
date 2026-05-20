"""
翻译进度审计脚本

用法：
    python scripts/check_progress.py [--src chapters_to_translate] [--tgt chapters_translated]

对比源文件与翻译文件，输出：
    - 每章节翻译完成/缺失/部分翻译状态
    - 英文段落的精确位置（段落号 + 预览文本）
    - 汇总统计
"""
import os, sys, json, argparse
sys.stdout.reconfigure(encoding='utf-8')


def audit(src_dir: str, tgt_dir: str):
    src_files = sorted([f for f in os.listdir(src_dir) if f.endswith('.json')])

    total_src = 0
    total_tgt = 0
    total_eng = 0
    total_missing_sections = 0

    print("=" * 72)
    print("  翻译进度审计")
    print("=" * 72)

    for f in src_files:
        src = json.load(open(os.path.join(src_dir, f), 'r', encoding='utf-8'))
        tag = f.split('__')[-1].replace('.json', '')
        total_src += src['count']

        tgt_path = os.path.join(tgt_dir, f)
        if not os.path.exists(tgt_path):
            print(f"  [{tag:10s}] ❌ 缺失  ({src['count']:4d} 段)")
            total_tgt += src['count']
            total_eng += src['count']
            total_missing_sections += 1
            continue

        tgt = json.load(open(tgt_path, 'r', encoding='utf-8'))
        total_tgt += tgt['count']

        eng_count = 0
        eng_positions = []
        for i, p in enumerate(tgt['paragraphs']):
            ascii_l = sum(1 for c in p if c.isascii() and c.isalpha())
            cn = sum(1 for c in p if '\u4e00' <= c <= '\u9fff')
            is_eng = ascii_l > 20 and cn * 3 < ascii_l
            if is_eng:
                eng_count += 1
                if len(eng_positions) < 5:
                    eng_positions.append((i + 1, p[:60]))

        pct = (1 - eng_count / tgt['count']) * 100 if tgt['count'] > 0 else 100
        if pct >= 99:
            status = '✅'
        elif pct >= 50:
            status = '⚠️'
        else:
            status = '❌'

        total_eng += eng_count

        print(f"  [{tag:10s}] {status}  {pct:5.1f}%  "
              f"({tgt['count']:4d} 段, {eng_count:4d} 段未翻译)")
        if eng_positions:
            for pos, preview in eng_positions:
                print(f"          └ 段#{pos:4d}: {preview}...")
            if eng_count > 5:
                print(f"          └ ... 还有 {eng_count - 5} 段未翻译")

    print("=" * 72)
    if total_src > 0:
        overall_pct = (1 - total_eng / total_src) * 100
        print(f"  总进度: {overall_pct:.1f}%")
        print(f"  总段落: {total_src:5d}")
        print(f"  已覆盖: {total_tgt - total_eng:5d}")
        print(f"  未翻译: {total_eng:5d}")
        print(f"  缺失章节: {total_missing_sections}")
    print("=" * 72)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='翻译进度审计')
    parser.add_argument('--src', default='chapters_to_translate',
                        help='源文件目录（默认: chapters_to_translate）')
    parser.add_argument('--tgt', default='chapters_translated',
                        help='翻译文件目录（默认: chapters_translated）')
    args = parser.parse_args()
    audit(args.src, args.tgt)
