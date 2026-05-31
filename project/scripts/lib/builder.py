"""
builder.py
objects / relations から draw.io XML を生成するモジュール。

レイアウト方針（最長路ランク）：
  - ソース（to に一度も出ない）: 最左列 rank=0
  - シンク（from に一度も出ない）・未接続: 最右列 rank=R_max
  - 中間（from かつ to）: 最長路で 0 < rank < R_max
  - すべての辺で rank(from) < rank(to)（LR: 右向き / TB: 下向き）
  - direction: TB のとき rank を段（y）に割り当てる
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom


# ────────────────────────────────────────
# 定数
# ────────────────────────────────────────
DEFAULT_FILL   = "#F5F5F5"
DEFAULT_STROKE = "#666666"
DEFAULT_EDGE_COLOR = "#999999"


# ────────────────────────────────────────
# ヘルパー
# ────────────────────────────────────────
def _get_style(obj: dict, config: dict) -> str:
    """オブジェクトのノードスタイル文字列を返す。"""
    type_styles = config.get("type_styles", {})
    obj_type    = obj.get("type")
    style_cfg   = type_styles.get(obj_type) or type_styles.get("default", {})

    fill   = style_cfg.get("fill_color",   DEFAULT_FILL)
    stroke = style_cfg.get("stroke_color", DEFAULT_STROKE)
    return (
        f"rounded=1;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};"
    )


def _get_edge_color(relation: dict, config: dict) -> str:
    """リレーションの矢印色を返す。"""
    edge_color_key = config.get("edge_color_key")
    edge_colors    = config.get("edge_colors", {})
    attributes     = relation.get("attributes", {})

    if edge_color_key:
        value = attributes.get(edge_color_key)
        if value:
            return edge_colors.get(value, edge_colors.get("default", DEFAULT_EDGE_COLOR))
    return edge_colors.get("default", DEFAULT_EDGE_COLOR)


def _edge_label(relation: dict, config: dict) -> str:
    """矢印ラベル（edge_color_key の値）を返す。"""
    edge_color_key = config.get("edge_color_key")
    attributes     = relation.get("attributes", {})
    if edge_color_key:
        return str(attributes.get(edge_color_key, ""))
    return ""


def _edge_connector_style(color: str, direction: str) -> str:
    """方向に応じた矢印の接続点スタイルを返す。"""
    if direction == "TB":
        connector = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    else:
        connector = "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
    return (
        f"edgeStyle=orthogonalEdgeStyle;rounded=0;"
        f"strokeColor={color};strokeWidth=2;"
        f"{connector}"
    )


def _serialize_property(value) -> str:
    """オブジェクト属性値を draw.io の XML 属性文字列に変換する。"""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _object_element_attrs(obj: dict) -> dict[str, str]:
    """
    objects.yaml の全プロパティを <object> 要素の属性 dict に変換する。
    表示ラベルは draw.io 慣例の label（= name）を使う。
    """
    attrs: dict[str, str] = {}
    for key, value in obj.items():
        if key == "name":
            attrs["label"] = _serialize_property(value)
        attrs[key] = _serialize_property(value)
    return attrs


def _role_sets(object_ids: set[str], from_ids: set[str], to_ids: set[str]) -> tuple[set[str], set[str], set[str]]:
    """ソース / シンク / 未接続の ID 集合を返す。"""
    related = from_ids | to_ids
    sources = {oid for oid in object_ids if oid in from_ids and oid not in to_ids}
    sinks   = {oid for oid in object_ids if oid in to_ids and oid not in from_ids}
    isolated = object_ids - related
    return sources, sinks, isolated


def _longest_path_ranks(
    node_ids: set[str],
    relations: list,
    sources: set[str],
) -> dict[str, int]:
    """
    有向辺 u→v について rank(v) >= rank(u)+1 となるよう最長路ランクを付与する。
    ソースは 0 に固定する。
    """
    rank = {oid: 0 for oid in node_ids}

    if not relations:
        return rank

    limit = len(node_ids) + 1
    for _ in range(limit):
        changed = False
        for rel in relations:
            u, v = rel["from"], rel["to"]
            if u not in node_ids or v not in node_ids:
                continue
            new_rank = rank[u] + 1
            if new_rank > rank[v]:
                rank[v] = new_rank
                changed = True
        if not changed:
            break

    for oid in sources:
        rank[oid] = 0

    return rank


def _pin_sinks_and_isolated(rank: dict[str, int], sinks: set[str], isolated: set[str]) -> None:
    """シンクと未接続ノードを最右列（R_max）に揃える。"""
    if not rank:
        return
    r_max = max(rank.values())
    for oid in sinks | isolated:
        rank[oid] = r_max


def _union_find_components(node_ids: set[str], relations: list) -> list[set[str]]:
    """無向グラフとしての連結成分を返す（リレーションに登場するノードのみ）。"""
    parent = {oid: oid for oid in node_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for rel in relations:
        union(rel["from"], rel["to"])

    groups: dict[str, set[str]] = {}
    for oid in node_ids:
        root = find(oid)
        groups.setdefault(root, set()).add(oid)

    return list(groups.values())


def _compute_global_ranks(
    object_ids: set[str],
    relations: list,
    sources: set[str],
    sinks: set[str],
    isolated: set[str],
) -> dict[str, int]:
    """全グラフを通したランクを返す。"""
    related = {r["from"] for r in relations} | {r["to"] for r in relations}
    rank = _longest_path_ranks(related, relations, sources & related)

    for oid in object_ids:
        rank.setdefault(oid, 0)

    _pin_sinks_and_isolated(rank, sinks, isolated)
    return rank


def _compute_per_component_ranks(
    object_ids: set[str],
    relations: list,
    sources: set[str],
    sinks: set[str],
    isolated: set[str],
) -> dict[str, int]:
    """連結成分ごとにランクを付け、列オフセットで横に並べる。"""
    related = {r["from"] for r in relations} | {r["to"] for r in relations}
    global_rank: dict[str, int] = {oid: 0 for oid in object_ids}

    components = _union_find_components(related, relations)
    components.sort(key=lambda c: min(c))

    offset = 0
    for comp in components:
        comp_sources = sources & comp
        comp_sinks = sinks & comp
        comp_relations = [
            r for r in relations
            if r["from"] in comp and r["to"] in comp
        ]
        local = _longest_path_ranks(comp, comp_relations, comp_sources)
        _pin_sinks_and_isolated(local, comp_sinks, set())

        for oid, local_rank in local.items():
            global_rank[oid] = offset + local_rank

        offset += max(local.values(), default=0) + 1

    if isolated:
        iso_rank = offset if offset > 0 else 0
        for oid in isolated:
            global_rank[oid] = iso_rank

    return global_rank


def _compute_node_ranks(
    objects: list,
    relations: list,
    config: dict,
) -> dict[str, int]:
    """各オブジェクト ID の列ランクを返す。"""
    layout = config.get("layout", {})
    component_mode = layout.get("component_mode", "global")

    object_ids = {o["id"] for o in objects}
    from_ids = {r["from"] for r in relations}
    to_ids = {r["to"] for r in relations}
    sources, sinks, isolated = _role_sets(object_ids, from_ids, to_ids)

    if component_mode == "per_component":
        return _compute_per_component_ranks(
            object_ids, relations, sources, sinks, isolated
        )
    return _compute_global_ranks(
        object_ids, relations, sources, sinks, isolated
    )


def _compute_layout(objects: list, relations: list, config: dict) -> dict:
    """
    各オブジェクトの (x, y) 座標を計算して返す。
    戻り値: { id: (x, y) }
    """
    layout    = config.get("layout", {})
    direction = layout.get("direction", "LR")
    nw        = layout.get("node_width",  120)
    nh        = layout.get("node_height",  60)
    sx        = layout.get("spacing_x",    80)
    sy        = layout.get("spacing_y",    40)
    margin    = layout.get("margin",       40)

    ranks = _compute_node_ranks(objects, relations, config)

    # rank ごとに objects.yaml の順で縦（または横）に並べる
    columns: dict[int, list] = {}
    for obj in objects:
        obj_id = obj["id"]
        col = ranks.get(obj_id, 0)
        columns.setdefault(col, []).append(obj)

    coords = {}
    col_step = nw + sx
    row_step = nh + sy

    for col, col_objects in sorted(columns.items()):
        for row, obj in enumerate(col_objects):
            if direction == "LR":
                x = margin + col * col_step
                y = margin + row * row_step
            else:  # TB
                x = margin + row * col_step
                y = margin + col * row_step
            coords[obj["id"]] = (x, y)

    return coords


# ────────────────────────────────────────
# メイン生成関数
# ────────────────────────────────────────
def build_drawio_xml(
    objects: list,
    valid_relations: list,
    config: dict,
) -> str:
    """draw.io XML 文字列を生成して返す。"""

    layout = config.get("layout", {})
    nw = layout.get("node_width",  120)
    nh = layout.get("node_height",  60)
    direction = layout.get("direction", "LR")

    coords = _compute_layout(objects, valid_relations, config)

    # XML ルート構造
    root    = ET.Element("mxGraphModel")
    diagram = ET.SubElement(root, "root")
    ET.SubElement(diagram, "mxCell", id="0")
    ET.SubElement(diagram, "mxCell", id="1", parent="0")

    # ノード生成（全プロパティを <object> 属性に内包、表示は label=name のみ）
    for obj in objects:
        obj_id = obj["id"]
        x, y   = coords.get(obj_id, (40, 40))
        style  = _get_style(obj, config)

        user_object = ET.SubElement(
            diagram, "object",
            **_object_element_attrs(obj),
        )
        cell = ET.SubElement(
            user_object, "mxCell",
            style=style,
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell, "mxGeometry",
            x=str(x), y=str(y),
            width=str(nw), height=str(nh),
            **{"as": "geometry"},
        )

    # エッジ生成
    for idx, rel in enumerate(valid_relations):
        color = _get_edge_color(rel, config)
        label = _edge_label(rel, config)
        style = _edge_connector_style(color, direction)
        edge_id = f"edge-{idx}"
        cell = ET.SubElement(
            diagram, "mxCell",
            id=edge_id,
            value=label,
            style=style,
            edge="1",
            source=rel["from"],
            target=rel["to"],
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})

    # 整形して返す
    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")
