"""
builder.py
objects / relations から draw.io XML を生成するモジュール。

レイアウト方針：
  - 接続元（from）に登場するオブジェクトを左列に配置
  - 接続先（to）のみのオブジェクトを右列に配置
  - いずれにも登場しないオブジェクトは右列の末尾に配置
  - direction: TB の場合は上段／下段に読み替える
"""

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


def _tooltip(obj: dict) -> str:
    """id / name 以外の属性をツールチップ文字列にまとめる。"""
    skip = {"id", "name"}
    lines = [f"{k}: {v}" for k, v in obj.items() if k not in skip]
    return "&#xa;".join(lines)   # draw.io の改行エスケープ


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

    # from 側 / to 側 を分類
    from_ids = {r["from"] for r in relations}
    to_ids   = {r["to"]   for r in relations}

    left_col  = [o for o in objects if o["id"] in from_ids]
    right_col = [o for o in objects if o["id"] not in from_ids]

    coords = {}

    if direction == "LR":
        # 左列：from 側
        for i, obj in enumerate(left_col):
            x = margin
            y = margin + i * (nh + sy)
            coords[obj["id"]] = (x, y)
        # 右列：その他
        for i, obj in enumerate(right_col):
            x = margin + nw + sx
            y = margin + i * (nh + sy)
            coords[obj["id"]] = (x, y)
    else:  # TB
        # 上段：from 側
        for i, obj in enumerate(left_col):
            x = margin + i * (nw + sx)
            y = margin
            coords[obj["id"]] = (x, y)
        # 下段：その他
        for i, obj in enumerate(right_col):
            x = margin + i * (nw + sx)
            y = margin + nh + sy
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

    coords = _compute_layout(objects, valid_relations, config)

    # XML ルート構造
    root    = ET.Element("mxGraphModel")
    diagram = ET.SubElement(root, "root")
    ET.SubElement(diagram, "mxCell", id="0")
    ET.SubElement(diagram, "mxCell", id="1", parent="0")

    # ノード生成
    for obj in objects:
        obj_id  = obj["id"]
        x, y    = coords.get(obj_id, (40, 40))
        label   = f"{obj_id}\n{obj['name']}"
        style   = _get_style(obj, config)
        tooltip = _tooltip(obj)

        cell = ET.SubElement(
            diagram, "mxCell",
            id=obj_id,
            value=label,
            style=style,
            vertex="1",
            parent="1",
            tooltip=tooltip,
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
        style = (
            f"edgeStyle=orthogonalEdgeStyle;rounded=0;"
            f"strokeColor={color};strokeWidth=2;"
            f"exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
            f"entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
        )
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