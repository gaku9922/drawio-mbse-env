"""
loader.py
YAMLファイルを読み込み、辞書として返すモジュール。
"""

import yaml
from pathlib import Path


def load_yaml(path: str | Path) -> dict | list:
    """YAMLファイルを読み込んで返す。ファイルが存在しない場合は None を返す。"""
    path = Path(path)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model(model_dir: str | Path) -> tuple[list, list, dict]:
    """
    model/ ディレクトリから3ファイルをまとめて読み込む。

    Returns:
        objects   : オブジェクトのリスト（必須）
        relations : リレーションのリスト（省略時は空リスト）
        config    : 設定辞書（省略時は空辞書）
    """
    model_dir = Path(model_dir)

    # objects.yaml は必須
    objects_data = load_yaml(model_dir / "objects.yaml")
    if objects_data is None:
        raise FileNotFoundError(f"objects.yaml が見つかりません: {model_dir}")
    objects = objects_data.get("objects", [])

    # relations.yaml は省略可
    relations_data = load_yaml(model_dir / "relations.yaml")
    relations = relations_data.get("relations", []) if relations_data else []

    # config.yaml は省略可
    config_data = load_yaml(model_dir / "config.yaml")
    config = config_data if config_data else {}

    return objects, relations, config