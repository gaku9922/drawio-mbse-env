"""
generate.py
model/ を読み込み、draw.io XML を output/ に生成する。

使い方:
  python scripts/generate.py
  python scripts/generate.py --model path/to/model --output path/to/output
"""

import argparse
import sys
from pathlib import Path

# lib を import パスに追加
sys.path.insert(0, str(Path(__file__).parent))

from lib.loader    import load_model
from lib.validator import validate
from lib.builder   import build_drawio_xml


def main():
    parser = argparse.ArgumentParser(description="model/ から draw.io XML を生成する")
    parser.add_argument(
        "--model", default="model",
        help="model ディレクトリのパス（デフォルト: model）"
    )
    parser.add_argument(
        "--output", default="output",
        help="出力ディレクトリのパス（デフォルト: output）"
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # ── 読み込み ──────────────────────────
    try:
        objects, relations, config = load_model(args.model)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"読み込み完了: オブジェクト {len(objects)}件 / リレーション {len(relations)}件")

    # ── 検証 ──────────────────────────────
    result, valid_relations = validate(objects, relations, config)

    skipped = len(relations) - len(valid_relations)

    if result.has_errors or result.has_warnings:
        print()
        print(result.summary())

    # レポートファイルに保存
    report_path = output_dir / "report.txt"
    report_path.write_text(result.summary(), encoding="utf-8")
    print(f"\n検証レポート → {report_path}")

    # ── XML 生成 ──────────────────────────
    xml_str = build_drawio_xml(objects, valid_relations, config)

    drawio_path = output_dir / "system.drawio"
    drawio_path.write_text(xml_str, encoding="utf-8")

    print(f"draw.io XML  → {drawio_path}")
    print()
    print(f"  ノード  : {len(objects)}個")
    print(f"  矢印    : {len(valid_relations)}本（スキップ: {skipped}本）")

    if result.has_errors:
        print("\n[!] エラーがあります。report.txt を確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()