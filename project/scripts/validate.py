"""
validate.py
model/ ディレクトリの整合性を検証し、レポートを表示する。

使い方:
  python scripts/validate.py
  python scripts/validate.py --model path/to/model
"""

import argparse
import sys
from pathlib import Path

# lib を import パスに追加
sys.path.insert(0, str(Path(__file__).parent))

from lib.loader    import load_model
from lib.validator import validate


def main():
    parser = argparse.ArgumentParser(description="model/ の整合性を検証する")
    parser.add_argument(
        "--model", default="model",
        help="model ディレクトリのパス（デフォルト: model）"
    )
    args = parser.parse_args()

    # 読み込み
    try:
        objects, relations, config = load_model(args.model)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"読み込み完了: オブジェクト {len(objects)}件 / リレーション {len(relations)}件")

    # 検証
    result, valid_relations = validate(objects, relations, config)

    # レポート出力
    print()
    print(result.summary())

    skipped = len(relations) - len(valid_relations)
    print(f"有効なリレーション: {len(valid_relations)}件 / スキップ: {skipped}件")

    sys.exit(1 if result.has_errors else 0)


if __name__ == "__main__":
    main()