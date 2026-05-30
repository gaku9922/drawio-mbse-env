"""
validator.py
objects / relations の整合性を検証するモジュール。

検証内容：
  [ERROR] from / to に指定されたIDが objects.yaml に存在しない
  [WARN]  attributes に edge_color_key に対応する値がない
"""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        lines = ["=" * 40, "検証レポート", "=" * 40]

        if not self.errors and not self.warnings:
            lines.append("問題は見つかりませんでした。")
        else:
            for msg in self.errors:
                lines.append(msg)
            for msg in self.warnings:
                lines.append(msg)

        lines.append("-" * 40)
        lines.append(f"エラー: {len(self.errors)}件 / 警告: {len(self.warnings)}件")
        return "\n".join(lines)


def validate(
    objects: list,
    relations: list,
    config: dict,
) -> tuple[ValidationResult, list]:
    """
    整合性を検証し、有効なリレーションのみを返す。

    Returns:
        result           : ValidationResult（エラー・警告の一覧）
        valid_relations  : 有効と判断されたリレーションのリスト
    """
    result = ValidationResult()
    valid_relations = []

    # objects のIDセットを構築
    object_ids = {o["id"] for o in objects}

    # edge_color_key（色分けに使う属性キー）
    edge_color_key = config.get("edge_color_key")

    for r in relations:
        from_id = r.get("from")
        to_id = r.get("to")
        attributes = r.get("attributes", {})
        skip = False

        # ① from ID の存在確認
        if from_id not in object_ids:
            result.errors.append(
                f"[ERROR] [SKIP] 未定義ID: '{from_id}' (from: {from_id} → to: {to_id})"
            )
            skip = True

        # ② to ID の存在確認
        if to_id not in object_ids:
            result.errors.append(
                f"[ERROR] [SKIP] 未定義ID: '{to_id}' (from: {from_id} → to: {to_id})"
            )
            skip = True

        if skip:
            continue

        # ③ edge_color_key に対応する属性が存在するか（警告のみ・スキップしない）
        if edge_color_key and edge_color_key not in attributes:
            result.warnings.append(
                f"[WARN]  '{edge_color_key}' が attributes に未定義: "
                f"(from: {from_id} → to: {to_id}) → デフォルト色で描画します"
            )

        valid_relations.append(r)

    return result, valid_relations