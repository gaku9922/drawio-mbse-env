"""
validator.py
objects / relations の整合性を検証するモジュール。

検証内容：
  [ERROR] objects.yaml 内で同一 id が重複定義されている
  [ERROR] from / to に指定されたIDが objects.yaml に存在しない
  [ERROR] リレーションに閉路（サイクル）がある
  [WARN]  attributes に edge_color_key に対応する値がない
"""

from collections import Counter, defaultdict
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


def _find_cycle_nodes(relations: list) -> list[str] | None:
    """閉路があればサイクル上のノード ID リストを返す。なければ None。"""
    adj: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for r in relations:
        u, v = r["from"], r["to"]
        adj[u].append(v)
        nodes.add(u)
        nodes.add(v)

    visited: set[str] = set()
    stack: set[str] = set()
    parent: dict[str, str | None] = {}

    def dfs(u: str) -> list[str] | None:
        visited.add(u)
        stack.add(u)
        for v in adj[u]:
            if v not in visited:
                parent[v] = u
                found = dfs(v)
                if found:
                    return found
            elif v in stack:
                cycle_end = v
                path = [v]
                cur = u
                while cur != cycle_end:
                    path.append(cur)
                    cur = parent.get(cur, cycle_end)
                    if cur in path:
                        break
                path.append(cycle_end)
                return list(reversed(path))
        stack.remove(u)
        return None

    for node in sorted(nodes):
        if node not in visited:
            parent[node] = None
            found = dfs(node)
            if found:
                return found

    return None


def _validate_duplicate_ids(objects: list, result: ValidationResult) -> None:
    """同一 id の重複定義を検出する。"""
    counts = Counter(o["id"] for o in objects)
    for obj_id, count in sorted(counts.items()):
        if count > 1:
            result.errors.append(
                f"[ERROR] 重複ID: '{obj_id}' ({count}回定義)"
            )


def _validate_cycles(relations: list, result: ValidationResult) -> None:
    """閉路検出。検出時は ERROR を追加する。"""
    cycle = _find_cycle_nodes(relations)
    if cycle:
        path = " → ".join(cycle)
        result.errors.append(
            f"[ERROR] 閉路が検出されました: {path} "
            f"（レイアウトの rank 付けができません）"
        )


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

    # ① 重複 id 検出
    _validate_duplicate_ids(objects, result)

    # objects のIDセットを構築
    object_ids = {o["id"] for o in objects}

    # edge_color_key（色分けに使う属性キー）
    edge_color_key = config.get("edge_color_key")

    for r in relations:
        from_id = r.get("from")
        to_id = r.get("to")
        attributes = r.get("attributes", {})
        skip = False

        # ② from ID の存在確認
        if from_id not in object_ids:
            result.errors.append(
                f"[ERROR] [SKIP] 未定義ID: '{from_id}' (from: {from_id} → to: {to_id})"
            )
            skip = True

        # ③ to ID の存在確認
        if to_id not in object_ids:
            result.errors.append(
                f"[ERROR] [SKIP] 未定義ID: '{to_id}' (from: {from_id} → to: {to_id})"
            )
            skip = True

        if skip:
            continue

        # ④ edge_color_key に対応する属性が存在するか（警告のみ・スキップしない）
        if edge_color_key and edge_color_key not in attributes:
            result.warnings.append(
                f"[WARN]  '{edge_color_key}' が attributes に未定義: "
                f"(from: {from_id} → to: {to_id}) → デフォルト色で描画します"
            )

        valid_relations.append(r)

    # ⑤ 閉路検出（有効なリレーションのみ対象）
    _validate_cycles(valid_relations, result)

    return result, valid_relations
