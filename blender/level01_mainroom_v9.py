# -*- coding: utf-8 -*-
"""
《第七日》第一关 · 主房间 V9
基于之前的资源/家具脚本逻辑重做：只生成参考图对应的【大主房间】。
不生成隐藏房，不生成 CRT / SAVE / LOAD / 木桌 / 木椅。

安全原则：
- 当前活动 Scene 作为资源来源。
- 使用 FULL_COPY 创建独立的新 Scene，原 Scene 完全保留。
- 已经摆好的完整电脑桌、桌面所有物品、办公椅：不重摆、不缩放、不旋转。
- 书柜及柜内已有书：整体整理、整体放大，保持书柜内部相对关系。
- 新建筑和环境全部使用 V9_ 前缀，重复运行只清理 V9 自己的结果。

Blender 5.2 LTS 适用。
"""

import bpy
import math
from mathutils import Vector

ROOM_W = 12.0
ROOM_D = 14.0
ROOM_H = 4.2
WALL_T = 0.18

PLAYER_START = (0.0, -ROOM_D * 0.5 + 0.9, 1.60)

# 如果完整书柜不在当前 .blend 中，可填写绝对路径。
BOOKCASE_BLEND_PATH = ""

GENERATED_PREFIXES = (
    "V9_ROOM_", "V9_ENV_", "V9_PROP_", "V9_LIGHT_", "V9_CAMERA_",
    "V9_BOOKCASE_RIG", "V9_BOOKCASE_COPY"
)

def log(*args):
    print("[第七日 V9]", *args)

def mat(name, color, rough=0.75, metallic=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1.0)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metallic
    return m

def ensure_collection(scene, name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
    elif c.name not in [x.name for x in scene.collection.children]:
        try:
            scene.collection.children.link(c)
        except Exception:
            pass
    return c

def move_to_collection(scene, obj, name):
    c = ensure_collection(scene, name)
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    c.objects.link(obj)

def add_box(scene, name, loc, dims, material, bevel=0.0, collection="V9_ENV"):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    move_to_collection(scene, o, collection)
    if material:
        o.data.materials.append(material)
    if bevel:
        mod = o.modifiers.new("V9_Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return o

def add_cylinder_between(scene, name, a, b, radius, material):
    a, b = Vector(a), Vector(b)
    v = b - a
    if v.length < 0.001:
        return None
    mid = (a + b) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20, radius=radius, depth=v.length, location=mid
    )
    o = bpy.context.object
    o.name = name
    o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    move_to_collection(scene, o, "V9_ENV")
    if material:
        o.data.materials.append(material)
    return o

def world_bounds(objects):
    pts = []
    for o in objects:
        if o.type not in {"MESH", "CURVE", "FONT", "SURFACE", "META"}:
            continue
        try:
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
        except Exception:
            pass
    if not pts:
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def hierarchy(scene, root):
    result = {root}
    changed = True
    while changed:
        changed = False
        for o in scene.objects:
            if o.parent in result and o not in result:
                result.add(o)
                changed = True
    return result

def remove_v9(scene):
    for o in list(scene.objects):
        if o.name.startswith(GENERATED_PREFIXES):
            bpy.data.objects.remove(o, do_unlink=True)

def remove_old_generated_room(scene):
    """
    只在 V9 新副本里执行。
    清掉以前脚本的建筑/隐藏房/占位物。
    对明确的桌、椅、书柜、书籍对象跳过。
    """
    prefixes = (
        "RM_", "SR_", "V6_SR_", "V8_",
        "L01_v4_", "L01_v5_", "L01_v6_", "L01_v7_", "L01_v8_",
        "PLACEHOLDER_"
    )
    keep_words = (
        "desk", "chair", "book", "bookshelf", "bookcase",
        "office workplace", "manager chair", "书"
    )
    for o in list(scene.objects):
        if not o.name.startswith(prefixes):
            continue
        n = o.name.lower()
        if any(w in n for w in keep_words):
            continue
        bpy.data.objects.remove(o, do_unlink=True)

def find_desk(scene):
    exact = (
        "L01_v4_Desk_Complete_KeepOriginal",
        "L01_v5_Desk_Complete_KeepOriginal",
        "L01_v6_Desk_Complete_KeepOriginal",
        "L01_v8_Desk_Complete_KeepOriginal",
        "PR_MainDesk_LOCKED_UNCHANGED",
        "PR_MainDesk_UNCHANGED",
        "Complete Office Workplace Setup",
    )
    for n in exact:
        o = scene.objects.get(n)
        if o:
            return o
    for o in scene.objects:
        if o.get("do_not_move_or_scale"):
            return o
        if "complete office workplace" in o.name.lower():
            return o
    return None

def find_chair(scene):
    exact = (
        "Ribbed Leather Manager Chair Black",
        "L01_v4_Chair_KeepOriginal",
        "L01_v5_Chair_KeepOriginal",
        "L01_v6_Chair_KeepOriginal",
    )
    for n in exact:
        o = scene.objects.get(n)
        if o:
            return o
    for o in scene.objects:
        if "manager chair" in o.name.lower():
            return o
    return None

def lock_furniture(scene):
    desk = find_desk(scene)
    chair = find_chair(scene)
    protected = set()

    if desk:
        protected |= hierarchy(scene, desk)
        log("电脑桌锁定：", desk.name)
    else:
        log("警告：未识别完整电脑桌；V9 不会创建替代桌。")

    if chair:
        protected |= hierarchy(scene, chair)
        log("办公椅锁定：", chair.name)
    else:
        log("警告：未识别办公椅；V9 不会创建替代椅。")

    for o in protected:
        o["V9_LOCKED"] = True
        o["do_not_move_or_scale"] = True
        o["desk_internal_layout_preserved"] = True

    return desk, chair, protected

def is_book(o):
    n = o.name.lower()
    return any(k in n for k in (
        "book", "volume", "novel", "magazine", "textbook",
        "leather-bound", "书"
    ))

def find_bookcase(scene):
    candidates = []
    roots = list(scene.objects)
    for o in roots:
        n = o.name.lower()
        if not any(k in n for k in ("bookcase", "bookshelf", "书柜", "书架")):
            continue
        tree = hierarchy(scene, o)
        b = world_bounds(tree)
        if not b:
            continue
        lo, hi = b
        size = hi - lo
        if size.z >= 1.0:
            candidates.append((size.z, size.x * size.y, o, tree))

    if not candidates:
        return None, [], None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _, _, shelf, shelf_tree = candidates[0]
    b = world_bounds(shelf_tree)
    books = []

    if b:
        lo, hi = b
        pad = Vector((0.40, 0.40, 0.30))
        lo -= pad
        hi += pad
        for o in roots:
            if o in shelf_tree or not is_book(o):
                continue
            ob = world_bounds(hierarchy(scene, o))
            if not ob:
                continue
            a, c = ob
            center = (a + c) * 0.5
            if all(lo[i] <= center[i] <= hi[i] for i in range(3)):
                books.append(o)

    log("书柜识别：", shelf.name, "；独立书籍：", len(books))
    return shelf, books, b

def build_room(scene):
    wall = mat("V9_Mat_Wall", (0.25, 0.26, 0.24), 0.93)
    floor = mat("V9_Mat_Floor", (0.10, 0.105, 0.10), 0.82)
    ceiling = mat("V9_Mat_Ceiling", (0.035, 0.042, 0.041), 0.70, 0.55)
    dark = mat("V9_Mat_DarkMetal", (0.065, 0.07, 0.067), 0.55, 0.60)
    glass = mat("V9_Mat_Window", (0.48, 0.56, 0.59), 0.18)

    add_box(scene, "V9_ROOM_Floor", (0, 0, -0.10),
            (ROOM_W, ROOM_D, 0.20), floor, 0.015)

    add_box(scene, "V9_ROOM_LeftWall", (-ROOM_W/2, 0, ROOM_H/2),
            (WALL_T, ROOM_D, ROOM_H), wall, 0.01)
    add_box(scene, "V9_ROOM_RightWall", (ROOM_W/2, 0, ROOM_H/2),
            (WALL_T, ROOM_D, ROOM_H), wall, 0.01)
    add_box(scene, "V9_ROOM_BackWall", (0, ROOM_D/2, ROOM_H/2),
            (ROOM_W, WALL_T, ROOM_H), wall, 0.01)

    door_w, door_h = 1.30, 2.25
    side = (ROOM_W - door_w) / 2
    add_box(scene, "V9_ROOM_FrontWall_L",
            (-(door_w/2 + side/2), -ROOM_D/2, ROOM_H/2),
            (side, WALL_T, ROOM_H), wall, 0.01)
    add_box(scene, "V9_ROOM_FrontWall_R",
            ((door_w/2 + side/2), -ROOM_D/2, ROOM_H/2),
            (side, WALL_T, ROOM_H), wall, 0.01)
    add_box(scene, "V9_ROOM_DoorHeader",
            (0, -ROOM_D/2, door_h + (ROOM_H-door_h)/2),
            (door_w, WALL_T, ROOM_H-door_h), wall, 0.01)

    win_w, win_h = 2.25, 1.70
    win_z = 2.35
    add_box(scene, "V9_ROOM_WindowGlass",
            (0, ROOM_D/2 - WALL_T*0.60, win_z),
            (win_w, 0.03, win_h), glass, 0.008)

    frame = 0.085
    for x in (-win_w/2, win_w/2):
        add_box(scene, "V9_ENV_WindowFrame",
                (x, ROOM_D/2 - WALL_T*0.68, win_z),
                (frame, 0.06, win_h + frame*2), dark, 0.008)
    for z in (win_z-win_h/2, win_z+win_h/2):
        add_box(scene, "V9_ENV_WindowFrame",
                (0, ROOM_D/2 - WALL_T*0.68, z),
                (win_w+frame*2, 0.06, frame), dark, 0.008)
    add_box(scene, "V9_ENV_WindowFrame",
            (0, ROOM_D/2 - WALL_T*0.70, win_z),
            (frame, 0.06, win_h), dark, 0.006)

    z = ROOM_H - 0.08
    for x in range(-5, 6):
        add_box(scene, "V9_ENV_CeilingGrid",
                (x, 0, z), (0.035, ROOM_D-0.35, 0.045), ceiling)
    for y in range(-6, 7):
        add_box(scene, "V9_ENV_CeilingGrid",
                (0, y, z), (ROOM_W-0.35, 0.035, 0.045), ceiling)
    for x in (-4.2, 0, 4.2):
        add_box(scene, "V9_ENV_CeilingBeam",
                (x, 0, ROOM_H-0.02), (0.12, ROOM_D, 0.12), dark, 0.015)

    for x in (4.55, 5.05):
        add_cylinder_between(
            scene, "V9_ENV_Duct",
            (x, -4.5, ROOM_H-0.28),
            (x, 5.2, ROOM_H-0.28),
            0.15, dark
        )

    for i in range(9):
        add_box(scene, "V9_ENV_Radiator",
                (ROOM_W/2-0.30, 3.15+i*0.11, 0.70),
                (0.10, 0.07, 0.70), dark, 0.012)

    log("主房间建筑：", ROOM_W, "×", ROOM_D, "×", ROOM_H, "m")

def parent_keep_world(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = mw

def place_bookcase(scene, shelf, books):
    if not shelf:
        log("没有找到完整书柜：不生成白模替代品。")
        return None

    members = [shelf] + [b for b in books if b != shelf]
    b = world_bounds(members)
    if not b:
        return None

    lo, hi = b
    center = (lo + hi) * 0.5

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=center)
    rig = bpy.context.object
    rig.name = "V9_BOOKCASE_RIG"
    move_to_collection(scene, rig, "V9_BOOKCASE")

    for o in members:
        parent_keep_world(o, rig)

    b2 = world_bounds(members)
    if not b2:
        return rig
    lo2, hi2 = b2
    size = hi2 - lo2
    scale = min(2.65/max(size.z,0.001), 2.75/max(size.x,0.001))
    scale = max(0.001, min(scale, 8.0))

    rig.scale = (scale, scale, scale)

    b3 = world_bounds(members)
    lo3, hi3 = b3
    center3 = (lo3 + hi3) * 0.5

    target_center = Vector((-ROOM_W/2 + 1.65, 2.65, 0))
    rig.location += target_center - center3
    rig.location.z += -lo3.z

    rig["V9_BOOKCASE_PRESERVE_BOOKS"] = True
    rig["V9_BOOK_COUNT"] = len(books)
    log("书柜已放大并放置；柜内书保持原有相对关系。")
    return rig

def build_props(scene):
    metal = mat("V9_Mat_PropMetal", (0.075,0.08,0.075), 0.55, 0.65)
    wood = mat("V9_Mat_PropWood", (0.24,0.145,0.085), 0.80)
    fabric = mat("V9_Mat_Sofa", (0.15,0.105,0.09), 0.92)
    paper = mat("V9_Mat_Paper", (0.60,0.57,0.48), 0.92)

    add_box(scene, "V9_PROP_LeftStorageTable",
            (-4.15, 3.35, 0.72), (2.35,0.62,0.12), metal, 0.025)
    for x in (-5.0, -3.3):
        add_box(scene, "V9_PROP_LeftStorageLeg",
                (x,3.35,0.36), (0.08,0.08,0.72), metal, 0.008)

    for i, x in enumerate((-4.9,-4.35,-3.8,-3.25)):
        add_box(scene, f"V9_PROP_FileBox_{i}",
                (x,3.10,0.45), (0.42,0.38,0.30), wood, 0.012)

    for i in range(7):
        add_box(scene, f"V9_PROP_DesignSheet_{i}",
                (-ROOM_W/2+0.105, 0.65+i*0.43,
                 1.85+(i%2)*0.16),
                (0.018,0.40,0.30), paper, 0.003)

    for i in range(4):
        add_box(scene, f"V9_PROP_FileCabinet_{i}",
                (4.55,2.25,0.28+i*0.50),
                (0.72,0.58,0.42), metal, 0.03)

    for i in range(4):
        add_box(scene, "V9_PROP_RackShelf",
                (4.20,4.55,0.30+i*0.68),
                (1.65,0.55,0.055), metal, 0.008)
    for x in (3.43,4.97):
        for y in (4.28,4.82):
            add_box(scene, "V9_PROP_RackPost",
                    (x,y,1.35),(0.045,0.045,2.70),metal,0.005)

    add_box(scene, "V9_PROP_SofaSeat",
            (4.05,-2.95,0.50),(2.50,0.92,0.40),fabric,0.08)
    add_box(scene, "V9_PROP_SofaBack",
            (4.05,-3.28,1.08),(2.50,0.28,1.28),fabric,0.06)
    add_box(scene, "V9_PROP_SofaArmL",
            (2.78,-2.95,0.83),(0.26,0.92,0.92),fabric,0.06)
    add_box(scene, "V9_PROP_SofaArmR",
            (5.32,-2.95,0.83),(0.26,0.92,0.92),fabric,0.06)

    for i,(x,y,r) in enumerate(((-2.5,-2.0,-8), (1.8,0.4,12), (2.8,3.1,-5))):
        o = add_box(scene, f"V9_PROP_FallenPaper_{i}",
                    (x,y,0.012),(0.58,0.38,0.016),paper,0.002)
        o.rotation_euler.z = math.radians(r)

def build_lights_camera(scene):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("V9_World")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.025,0.03,0.03,1)
        bg.inputs["Strength"].default_value = 0.20

    bpy.ops.object.light_add(type="AREA",
                             location=(0,ROOM_D/2-0.9,3.15))
    key = bpy.context.object
    key.name = "V9_LIGHT_Window"
    key.data.energy = 1000
    key.data.shape = "RECTANGLE"
    key.data.size = 2.5
    key.data.size_y = 1.8
    key.data.color = (0.80,0.88,1.0)
    key.rotation_euler = (math.radians(-70),0,math.radians(180))
    move_to_collection(scene,key,"V9_ENV")

    bpy.ops.object.light_add(type="AREA", location=(0,0,ROOM_H-0.35))
    fill = bpy.context.object
    fill.name = "V9_LIGHT_CeilingSoft"
    fill.data.energy = 500
    fill.data.size = 7
    fill.data.color = (0.70,0.76,0.74)
    move_to_collection(scene,fill,"V9_ENV")

    bpy.ops.object.camera_add(location=PLAYER_START)
    cam = bpy.context.object
    cam.name = "V9_CAMERA_FirstPerson"
    cam.data.lens = 26
    cam.data.sensor_width = 36
    cam.rotation_euler = (math.radians(90),0,0)
    move_to_collection(scene,cam,"V9_ENV")
    scene.camera = cam

    try:
        scene.view_settings.exposure = -0.35
    except Exception:
        pass

def build():
    source = bpy.context.scene
    if not source:
        raise RuntimeError("没有活动 Scene。")

    old = bpy.data.scenes.get("LEVEL01_MainWorkshop_V9")
    if old and old != source:
        bpy.data.scenes.remove(old)

    bpy.context.window.scene = source
    bpy.ops.scene.new(type="FULL_COPY")
    target = bpy.context.scene
    target.name = "LEVEL01_MainWorkshop_V9"

    remove_v9(target)
    remove_old_generated_room(target)

    desk, chair, protected = lock_furniture(target)
    shelf, books, shelf_bounds = find_bookcase(target)

    build_room(target)
    build_props(target)
    place_bookcase(target, shelf, books)
    build_lights_camera(target)

    target["L01_V9_REFERENCE"] = "only the user-provided abandoned game design studio image"
    target["L01_V9_ROOM_SIZE"] = f"{ROOM_W}x{ROOM_D}x{ROOM_H}m"
    target["L01_V9_HIDDEN_ROOM"] = False
    target["L01_V9_DESK_LOCKED"] = True
    target["L01_V9_CHAIR_LOCKED"] = True
    target["L01_V9_BOOKS_PRESERVED"] = True

    txt = bpy.data.texts.get("L01_V9_说明") or bpy.data.texts.new("L01_V9_说明")
    txt.clear()
    txt.write(
        "《第七日》第一关 V9 主房间\n"
        "只对应用户提供的唯一参考图。\n"
        "本版不生成隐藏房。\n"
        "完整电脑桌 + 桌面所有物品 + 办公椅：锁定，不重新摆放。\n"
        "书柜：整体放大，原有书籍保持相对位置。\n"
        "原始 Scene：保留。\n"
        "下一版再加入隐藏门和超现实空间。\n"
    )

    log("================================")
    log("V9 主房间生成完成")
    log("原始 Scene 保留：", source.name)
    log("新场景：", target.name)
    log("电脑桌：", desk.name if desk else "未识别")
    log("办公椅：", chair.name if chair else "未识别")
    log("书柜：", shelf.name if shelf else "未识别")
    log("================================")
    print("检查完成后请 文件 → 另存为，不要覆盖原始 .blend。")

if __name__ == "__main__":
    try:
        build()
    except Exception as e:
        log("❌ V9 失败：", type(e).__name__, str(e))
        raise
