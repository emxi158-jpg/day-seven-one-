# -*- coding: utf-8 -*-
# 《第七日》一键建房与家具修复v5；支持直接在原始 .blend 运行。
# -*- coding: utf-8 -*-
"""
《第七日》第一关：9m×11m 主工作室 + 右侧隐藏存档房，Blender 自动布局 v3
运行方法：先打开原始 studio_original.blend，再在「脚本」工作区运行本脚本。
原模型不删除、不拆分；整套电脑桌仅平移（实例 scale=1, rotation=0）。
书柜可从另一个 .blend 追加：优先使用 Antique Bookcase 集合。
所有新对象创建在一个新的预览场景中；执行后请【另存为】，不要覆盖源文件。
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector, Matrix

# 如果自动找不到书柜文件，在这里填入路径，例如：
# BOOKCASE_BLEND_PATH = r"D:\Models\studio_original(1).blend"
BOOKCASE_BLEND_PATH = ""
BOOKCASE_COLLECTION = "Antique Bookcase"
SCENE_PREFIX = "LEVEL01_Workshop_With_SaveRoom"
MAIN_W, MAIN_D, MAIN_H = 9.0, 11.0, 3.4
SAVE_W, SAVE_D, SAVE_H = 3.35, 3.30, 2.85
ROOM_EDGE_X = MAIN_W * 0.5
SAVE_CENTER_X = ROOM_EDGE_X + SAVE_W * 0.5
PASSAGE_WIDTH, PASSAGE_HEIGHT = 1.25, 2.25

def notify(title, message):
    print("[第七日]", title, message)
    def draw(self, context):
        for line in message.split("\n"):
            self.layout.label(text=line[:95])
    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon="INFO")
    except Exception:
        pass

def material(name, rgb, roughness=0.85):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = (*rgb, 1.0)
        node.inputs["Roughness"].default_value = roughness
    return mat

def new_group(parent, name):
    group = bpy.data.collections.new(name)
    parent.children.link(group)
    return group

def block(target, name, center, dimensions, mat, hidden=False):
    x, y, z = (float(v) * 0.5 for v in dimensions)
    vertices = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),
             (1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    obj.location = center
    obj.data.materials.append(mat)
    obj.hide_viewport = hidden
    return obj

def note(target, name, at, radius=0.22):
    obj = bpy.data.objects.new(name, None)
    target.objects.link(obj)
    obj.location = at
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = radius
    return obj

def bounds_of_collection(group):
    """Return world-space bounds, including ordinary meshes and nested collection instances."""
    vertices = []
    visited = set()
    def walk(group, transform, depth=0):
        if depth > 10 or group is None:
            return
        ident = group.as_pointer()
        if ident in visited:
            return
        visited.add(ident)
        for obj in group.objects:
            world = transform @ obj.matrix_world
            if obj.type in {"MESH", "CURVE", "FONT", "SURFACE", "META"}:
                try:
                    for pt in obj.bound_box:
                        vertices.append(world @ Vector(pt))
                except (AttributeError, ValueError):
                    pass
            if obj.instance_type == "COLLECTION" and obj.instance_collection:
                nested = obj.instance_collection
                walk(nested, world @ Matrix.Translation(-nested.instance_offset), depth+1)
        for child in group.children:
            walk(child, transform, depth+1)
        visited.remove(ident)
    walk(group, Matrix.Identity(4))
    if not vertices:
        return None
    minimum = Vector([min(p[i] for p in vertices) for i in range(3)])
    maximum = Vector([max(p[i] for p in vertices) for i in range(3)])
    return minimum, maximum

def add_asset(scene_group, source_group, name, xy, angle=0, limits=None, preserve=False):
    if not source_group:
        print("未找到资产：", name)
        return False
    bbox = bounds_of_collection(source_group)
    if not bbox:
        print("资产没有可用的可见几何体：", source_group.name)
        return False
    low, high = bbox
    size = high-low
    radians = math.radians(0 if preserve else angle)
    c, s = abs(math.cos(radians)), abs(math.sin(radians))
    span_x, span_y = c*size.x+s*size.y, s*size.x+c*size.y
    if preserve:
        scale = 1.0
    else:
        scale = min(limits[0]/max(span_x, .00001),
                    limits[1]/max(span_y, .00001),
                    limits[2]/max(size.z, .00001))
        scale = max(.0001, min(scale, 100.0))
    inst = bpy.data.objects.new(name, None)
    scene_group.objects.link(inst)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = source_group
    inst.scale = (scale,)*3
    inst.rotation_euler.z = radians
    from mathutils import Euler
    rot = Euler((0,0,radians)).to_matrix()
    bottom_middle = Vector(((low.x+high.x)*.5,(low.y+high.y)*.5,low.z))
    inst.location = Vector((xy[0],xy[1],0)) - scale*(rot@(bottom_middle-source_group.instance_offset))
    print("摆放:",name, "缩放",round(scale,4),
          "整体尺寸(m)",tuple(round(a*scale,2) for a in (span_x,span_y,size.z)))
    if preserve and (span_x > MAIN_W*.85 or span_y > MAIN_D*.60):
        print("注意：完整电脑桌包围盒超过通常尺寸，仍严格保留原大小；可检查源模型单位。")
    return True

def locate_library():
    if BOOKCASE_BLEND_PATH:
        p = Path(bpy.path.abspath(BOOKCASE_BLEND_PATH))
        return p if p.exists() else None
    if not bpy.data.filepath:
        return None
    home = Path(bpy.data.filepath).parent
    preferred = [home/"studio_original(1).blend", home/"bookcase.blend",
                 home/"bookshelf.blend",home/"书柜.blend"]
    for p in preferred:
        if p.exists() and p.resolve() != Path(bpy.data.filepath).resolve():
            return p
    candidates = [p for p in home.glob("*.blend")
                  if p.resolve() != Path(bpy.data.filepath).resolve()
                  and any(w in p.stem.lower() for w in ("bookcase","bookshelf","书柜","书架"))]
    return candidates[0] if len(candidates)==1 else None

def bookcase_from_other_blend():
    # 优先考虑用户已经在主文件内整理好的集合。
    existing = bpy.data.collections.get("Bookcase_Clean")
    if existing:
        return existing, 0, "当前文件中的 Bookcase_Clean"
    path = locate_library()
    if path is None:
        print("未自动找到书柜 .blend 文件；请修改脚本顶部 BOOKCASE_BLEND_PATH。")
        return None, 0, "未找到外部书柜文件"
    with bpy.data.libraries.load(str(path), link=False) as (source, dest):
        options = [BOOKCASE_COLLECTION, "Bookshelf", "Bookcase", "书柜", "书架"]
        matched = next((n for n in options if n in source.collections), None)
        if matched is None:
            matched = next((n for n in source.collections
                            if "bookcase" in n.lower() or "bookshelf" in n.lower()), None)
        dest.collections = [matched] if matched else []
    chosen = dest.collections[0] if dest.collections else None
    if chosen is None:
        print("文件中没有识别到书柜集合，请查看源文件集合名称：", path)
        return None, 0, "外部文件没有识别到书柜集合"
    extras = hide_clearly_loose_books(chosen)
    return chosen, extras, str(path.name) + " / " + chosen.name

def hide_clearly_loose_books(group):
    """只隐藏明显脱离柜体边界的独立书本；不删除任何原始文件或资源。
    模棱两可的书宁可保留，避免自动误删柜内书。
    """
    objects = list(group.all_objects)
    structure = [o for o in objects if o.type == "MESH" and
                 any(t in o.name.lower() for t in ("bookcase","bookshelf","shelf_frame","cabinet_frame"))]
    if not structure:
        print("没找到可安全判定的书柜主体，跳过散书自动清理。")
        return 0
    pts=[]
    for obj in structure:
        for corner in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(corner))
    if not pts:
        return 0
    minimum = Vector([min(p[i] for p in pts) for i in range(3)])
    maximum = Vector([max(p[i] for p in pts) for i in range(3)])
    margin_xy, margin_z = .28, .22
    ignored=0
    for obj in objects:
        lower = obj.name.lower()
        if obj.type != "MESH" or any(t in lower for t in ("bookcase","bookshelf","bookend")):
            continue
        if not any(k in lower for k in ("book","volume","novel","textbook")):
            continue
        box = [obj.matrix_world@Vector(p) for p in obj.bound_box]
        if not box:
            continue
        center = sum(box,Vector())/len(box)
        outside = (
            center.x < minimum.x-margin_xy or center.x > maximum.x+margin_xy or
            center.y < minimum.y-margin_xy or center.y > maximum.y+margin_xy or
            center.z < minimum.z-margin_z or center.z > maximum.z+margin_z
        )
        if outside:
            obj.hide_viewport = True
            obj.hide_render = True
            ignored += 1
            print("暂时隐藏书柜外散书:",obj.name)
    return ignored

def architecture(main, hidden, materials):
    wall, floor, ceiling, glass = materials
    W,D,H = MAIN_W,MAIN_D,MAIN_H
    hw,hd = W*.5,D*.5
    block(main,"RM_Floor",(0,0,-.10),(W,D,.20),floor)
    block(main,"RM_LeftWall",(-hw,0,H*.5),(.16,D,H),wall)
    # 右墙拆分为三段，真实预留1.25m的隐藏房入口
    half_gap=PASSAGE_WIDTH*.5
    for side, a, b in (("Front",-hd,-half_gap),("Back",half_gap,hd)):
        block(main,"RM_RightWall_"+side,(hw,(a+b)*.5,H*.5),
              (.16,b-a,H),wall)
    block(main,"RM_Doorway_UpperWall",(hw,0,(PASSAGE_HEIGHT+H)*.5),
          (.16,PASSAGE_WIDTH,H-PASSAGE_HEIGHT),wall)

    # 主入口：南侧正中 1.35m宽×2.35m高
    ew,eh=1.35,2.35
    width=(W-ew)*.5
    x=ew*.5+width*.5
    block(main,"RM_Entry_Left",(-x,-hd,H*.5),(width,.16,H),wall)
    block(main,"RM_Entry_Right",(x,-hd,H*.5),(width,.16,H),wall)
    block(main,"RM_Entry_Top",(0,-hd,(eh+H)*.5),(ew,.16,H-eh),wall)
    # 主后窗：2.6m宽×1.72m高
    ww,lo,hi=2.6,.92,2.64
    width=(W-ww)*.5
    x=ww*.5+width*.5
    block(main,"RM_Back_Left",(-x,hd,H*.5),(width,.16,H),wall)
    block(main,"RM_Back_Right",(x,hd,H*.5),(width,.16,H),wall)
    block(main,"RM_Window_Sill",(0,hd,lo*.5),(ww,.16,lo),wall)
    block(main,"RM_Window_Top",(0,hd,(hi+H)*.5),(ww,.16,H-hi),wall)
    block(main,"RM_WindowGlass",(0,hd,(lo+hi)*.5),(ww-.04,.012,hi-lo),glass)
    block(main,"RM_Ceiling_PreviewHidden",(0,0,H+.08),(W,D,.16),ceiling,hidden=True)

    # 从右墙向外生长的3.35m×3.3m×2.85m隐藏小房间
    sx,sd,sh = SAVE_CENTER_X,SAVE_D,SAVE_H
    right_edge=ROOM_EDGE_X+SAVE_W
    block(hidden,"SR_Floor",(sx,0,-.10),(SAVE_W,SAVE_D,.20),floor)
    block(hidden,"SR_FarRightWall",(right_edge,0,sh*.5),(.16,sd,sh),wall)
    block(hidden,"SR_BackWall",(sx,sd*.5,sh*.5),(SAVE_W,.16,sh),wall)
    block(hidden,"SR_FrontWall",(sx,-sd*.5,sh*.5),(SAVE_W,.16,sh),wall)
    # 两个房间共用主房间右墙作为入口一侧；其上方的空隙作填补
    block(hidden,"SR_EntryLintelInside",(ROOM_EDGE_X+.075,0,(PASSAGE_HEIGHT+sh)*.5),
          (.15,PASSAGE_WIDTH,sh-PASSAGE_HEIGHT),wall)
    block(hidden,"SR_Ceiling_PreviewHidden",(sx,0,sh+.08),
          (SAVE_W,SAVE_D,.16),ceiling,hidden=True)

def local_save_room_assets(furniture, white, wood, dark, screen):
    # 这些是可以替换为下载模型的占位几何体，绝不复制/拆开主电脑桌。
    # 桌子靠隐藏房最右侧，CRT正对从主房入口进来的人。
    cx,cy=6.94,.36
    block(furniture,"SR_WoodTableTop",(cx,cy,.76),(.75,1.27,.07),wood)
    for dx in (-.29,.29):
        for dy in (-.51,.51):
            block(furniture,"SR_TableLeg",(cx+dx,cy+dy,.375),(.067,.067,.75),wood)
    # 独立木椅，位于桌子左侧，面朝CRT
    sx,sy=5.97,.33
    block(furniture,"SR_ChairSeat",(sx,sy,.46),(.48,.47,.075),wood)
    for dx in (-.19,.19):
        for dy in (-.17,.17):
            block(furniture,"SR_ChairLeg",(sx+dx,sy+dy,.23),(.048,.052,.46),wood)
    block(furniture,"SR_ChairBack",(sx-.22,sy,.77),(.07,.45,.56),wood)
    # CRT正面朝向房间西侧(-X)，可看到屏幕文本
    block(furniture,"SR_CRT_Back",(6.91,.36,.97),(.42,.58,.37),white)
    block(furniture,"SR_CRT_Screen",(6.687,.36,1.00),(.018,.46,.266),screen)
    # Save/Load/Reset文字预览。真实可交互界面放到Godot阶段制作。
    text_data=bpy.data.curves.new("CRT_MenuFont","FONT")
    text_data.body="PLAYER\nZERO\nSAVE\nLOAD\nRESET"
    text_data.size=.065
    text_data.space_line=1.20
    text_obj=bpy.data.objects.new("SR_CRT_Menu_PLAYER_ZERO_SAVE_LOAD_RESET",text_data)
    furniture.objects.link(text_obj)
    text_obj.location=(6.671,.17,1.09)
    text_obj.rotation_euler=(math.radians(90),0,math.radians(-90))
    text_obj.data.materials.append(dark)

def light_and_camera(target):
    camera_data=bpy.data.cameras.new("Player_FPS_26mm")
    camera_data.lens=26
    obj=bpy.data.objects.new("Player_FPS_26mm",camera_data)
    target.objects.link(obj)
    obj.location=(0,-4.55,1.60)
    goal=Vector((0,1.1,1.35))
    obj.rotation_euler=(goal-obj.location).to_track_quat("-Z","Y").to_euler()
    light_data=bpy.data.lights.new("WindowSoftColdLight","AREA")
    light_data.energy=900
    light_data.color=(.79,.87,1.0)
    light=bpy.data.objects.new("WindowSoftColdLight",light_data)
    target.objects.link(light)
    light.location=(0,4.95,2.8)
    light.rotation_euler=(Vector((0,0,.8))-light.location).to_track_quat("-Z","Y").to_euler()
    return obj

def v5_build_room():
    old_scene = bpy.context.scene
    # 在读取外部资产之前，锁定原文件里的整套电脑桌集合。
    desk = bpy.data.collections.get("Complete Office Workplace Setup")
    sofa = bpy.data.collections.get("Corner Sofa")
    cabinet = bpy.data.collections.get("Drawer Cabinet")

    bookcase, hidden_count, bookcase_note = (None, 0, 'v5 will append bookcase')
    new_scene=bpy.data.scenes.new(SCENE_PREFIX)
    architecture_collection=new_group(new_scene.collection,"RM_MainWorkshop")
    save_collection=new_group(new_scene.collection,"RM_HiddenSaveRoom")
    furniture=new_group(new_scene.collection,"PR_ExistingAssets_Instances")
    placeholders=new_group(new_scene.collection,"PR_SaveRoomPlaceholders")
    puzzle=new_group(new_scene.collection,"PZ_FuturePuzzleMarkers")
    light_group=new_group(new_scene.collection,"LT_LightingAndCamera")
    wall=material("L01_OldPlaster",(0.70,0.70,0.68))
    floor=material("L01_TimberFloor",(0.40,0.30,0.23))
    ceiling=material("L01_Ceiling",(0.78,0.78,0.77))
    glass=material("L01_MatteGlass",(0.54,0.64,0.67))
    wood=material("L01_SimpleWood",(0.38,0.25,0.17))
    white=material("L01_AgedCRTPlastic",(0.73,0.71,0.63))
    dark=material("L01_CRTGlyphs",(0.47,0.95,0.78))
    screen=material("L01_CRTScreen",(0.014,0.032,0.029))
    architecture(architecture_collection,save_collection,(wall,floor,ceiling,glass))

    # 办公桌：保留整个组合、原比例、原旋转，严格只改变集合实例位置。
    placed_desk=add_asset(furniture,desk,"PR_MainDesk_LOCKED_UNCHANGED",
                          (0,1.2),preserve=True)
    if not placed_desk:
        block(furniture,"NOTICE_Missing_CompleteDesk",(0,1.2,.76),(2.3,1.1,1.52),white)
        print("请检查原始工作室文件是否包含 Complete Office Workplace Setup 集合。")

    add_asset(furniture,sofa,"PR_CornerSofa",(3.30,-2.2),angle=270,
              limits=(1.70,2.35,1.10))
    add_asset(furniture,cabinet,"PR_DrawerCabinet",(3.60,2.18),
              limits=(1.05,.75,1.45))
    if not add_asset(furniture,bookcase,"PR_Bookcase_Clean",(-3.84,1.65),angle=90,
                     limits=(.68,2.15,2.22)):
        block(furniture,"PLACEHOLDER_BOOKCASE",(-3.89,1.65,1.10),(.55,1.90,2.20),wood)

    local_save_room_assets(placeholders,white,wood,dark,screen)

    # 白墙薄片：只用于白盒预览。它不是实墙，不能导出为阻塞碰撞体。
    visual = block(puzzle,"PZ_ShadowDoor_VisualSkin_NO_COLLISION",
                   (ROOM_EDGE_X+.015,0,1.125),(.018,PASSAGE_WIDTH-.04,2.25),wall)
    note(puzzle,"PZ_ShadowDoor_Center",(ROOM_EDGE_X,0,1.4))
    note(puzzle,"PZ_ViewAlignment_Target",(2.3,-1.5,1.6))
    note(puzzle,"SP_BookcaseToCeiling_Future",(-4.27,3.2,3.05))
    note(puzzle,"PZ_CRT_InsideSaveRoom",(6.7,.36,1.0))
    note(puzzle,"SPAWN_FirstPerson_Start",(0,-4.55,1.6))
    new_scene.camera=light_and_camera(light_group)
    if bpy.context.window:
        bpy.context.window.scene=new_scene
    print("\n《第七日》第一关新版预览生成完成")
    print("主房间: 9×11×3.4米；右侧隐藏房: 3.35×3.3×2.85米")
    print("原办公桌：", "已成功整体摆放，不缩放不旋转" if placed_desk else "未找到集合")
    print("书柜来源:",bookcase_note,"自动隐藏疑似散书:",hidden_count)
    print("请【文件 → 另存为】保存为新的 .blend 文件，切勿覆盖原始文件。")
    notify("第一关布局生成完成","已创建主工作室和隐藏存档房。\n原电脑桌没有拆分/缩放/旋转；请另存为新文件。\n书柜: "+bookcase_note[:55])



# ===== 自动修复完整电脑桌及书柜的v4升级代码 =====
# -*- coding: utf-8 -*-
"""
《第七日》第一关 · 一键建房+家具细化 v5

没有现有房间时先自动创建主工作室及右侧隐藏房；有房间则只修复家具：
- 把原来已摆好的「完整电脑桌 + 桌面所有摆件 + 办公椅」组成一个快照集合实例；
  scale=(1,1,1)，rotation=(0,0,0)，只整体移动，原布局不变。
- 不动 9×11m 主房间、右侧附加隐藏房、CRT/SAVE/LOAD 占位。
- 从外部另一份 .blend 的【原场景】取出真正书柜与柜内书，忽略散落柜外的书。
- 不删除/不移动任何源文件资产。

使用：直接打开存有原始完整电脑桌的 studio_original.blend，
在 Blender 中文版「脚本」工作区运行本 .py，一次完成，v3与v4均无需单独运行。
书柜文件放在当前 .blend 同目录，或在下面 BOOKCASE_BLEND_PATH 写完整路径。
"""
import bpy
from pathlib import Path
from mathutils import Vector, Matrix
import math

# ============== 可调整设置 ==============
BOOKCASE_BLEND_PATH = ""   # 例如 r"D:\\Project\\studio_original(1).blend"
BOOKCASE_FILE_NAME = "studio_original(1).blend"
SOURCE_SCENE_NAME = "Scene"     # 原始已搭好办公桌的场景名称
TARGET_SCENE_PREFIX = "LEVEL01_Workshop_With_SaveRoom"
BOOKCASE_PREFERENCE = ("Bookshelf", "Antique Bookcase")
DESK_DESTINATION = (0.0, 1.2, 0.0)
BOOKCASE_DESTINATION = (-3.84, 1.65, 0.0)
BOOKCASE_TARGET_SIZE = (0.7, 2.2, 2.25)  # 摆放朝向后的最大 X/Y/Z 尺寸
BOOKCASE_ROTATION = 90     # 书柜正面朝房间中央；如正面不对，改为 -90 或 0
DESK_DETECTION_MARGIN = 1.0  # 自动收集靠近电脑桌的散件，单位：米
INCLUDE_ADDITIONAL_DESK_PROPS = True

# 如果在原始 Scene 里提前选中了整套电脑桌、椅子和摆件，
# 这些选中的物体优先作为完整组合。若一个也没选，则全自动识别。
USE_SELECTION_IF_MULTIPLE = True

PREVIEW_DESK_NAMES = (
    "PR_MainDesk_LOCKED_UNCHANGED", "PR_MainDesk_UNCHANGED",
    "PR_CompleteDesk_UNCHANGED", "PR_MainDesk_LOCKED",
    "PR_MainDesk_Set", "PR_MainDesk", "NOTICE_Missing_CompleteDesk"
)
PREVIEW_BOOK_NAMES = (
    "PR_Bookcase_Clean", "PR_Bookcase", "PLACEHOLDER_BOOKCASE",
    "PLACEHOLDER_Bookcase_Select_Then_Rerun", "PLACEHOLDER_Bookcase"
)

# ============== 公用函数 ==============
def report(*args):
    print("[第七日 v4]", *args)


def visual_points(obj, transform=None, depth=0, active=None):
    """获得原场景资产在世界坐标中的8角点，支持 BlenderKit Empty 集合实例嵌套。"""
    if depth >= 9:
        return []
    if active is None:
        active = set()
    world = obj.matrix_world if transform is None else transform
    points = []
    if obj.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}:
        try:
            points.extend(world @ Vector(p) for p in obj.bound_box)
        except (ValueError, AttributeError):
            pass
    if obj.instance_type == 'COLLECTION' and obj.instance_collection is not None:
        coll = obj.instance_collection
        ptr = coll.as_pointer()
        if ptr not in active:
            active.add(ptr)
            offset = Matrix.Translation(-coll.instance_offset)
            for member in coll.objects:
                # collection member objects' matrix_world are local to collection instance
                points.extend(visual_points(member, world @ offset @ member.matrix_world, depth + 1, active))
            for child_collection in coll.children:
                for member in child_collection.objects:
                    points.extend(visual_points(member, world @ offset @ member.matrix_world, depth + 1, active))
            active.remove(ptr)
    return points


def box_of_object(obj):
    vertices = visual_points(obj)
    if not vertices:
        center = obj.matrix_world.translation.copy()
        return center.copy(), center.copy()
    minimum = Vector([min(v[i] for v in vertices) for i in range(3)])
    maximum = Vector([max(v[i] for v in vertices) for i in range(3)])
    return minimum, maximum


def box_of_objects(items):
    mins, maxs = [], []
    for ob in items:
        low, high = box_of_object(ob)
        mins.append(low)
        maxs.append(high)
    return (Vector([min(v[i] for v in mins) for i in range(3)]),
            Vector([max(v[i] for v in maxs) for i in range(3)]))


def flat_distance_to_rect(point, low, high):
    dx = max(low.x-point.x, 0.0, point.x-high.x)
    dy = max(low.y-point.y, 0.0, point.y-high.y)
    return math.hypot(dx, dy)


def root_objects(scene):
    return [o for o in scene.objects if o.parent is None]


def choose_by_name(scene, exact):
    return next((ob for ob in root_objects(scene) if ob.name == exact), None)


def descendants(root, scene_objects):
    out = {root}
    for obj in scene_objects:
        parent = obj.parent
        while parent is not None:
            if parent == root:
                out.add(obj)
                break
            parent = parent.parent
    return out


def choose_complete_desk(source):
    desk = choose_by_name(source, "Complete Office Workplace Setup")
    if desk is None:
        matches = [o for o in source.objects if "Complete Office Workplace Setup" in o.name]
        desk = matches[0] if matches else None
    if desk is None:
        raise RuntimeError("原始场景中找不到完整电脑桌对象 Complete Office Workplace Setup。请打开原始场景文件运行。")

    if USE_SELECTION_IF_MULTIPLE and bpy.context.scene == source:
        manual = [o for o in bpy.context.selected_objects if o in source.objects]
        # 选中一两件往往是不小心点到的，不用它来决定完整桌面。
        if len(manual) >= 3 and desk in manual:
            result = set(manual)
            report("优先使用原始场景手动选中的", len(result), "个办公区对象")
        else:
            result = {desk}
    else:
        result = {desk}

    base_low, base_high = box_of_object(desk)
    if (base_high-base_low).length < .001:
        report("警告：未获得桌面完整包围盒；仅通过相关对象名称扩展收集。")
    exclude = (
        "corner sofa", "drawer cabinet", "antique bookcase", "bookshelf",
        "mushroom rigged", "camera", "office wall clock", "mountain picture",
    )
    if INCLUDE_ADDITIONAL_DESK_PROPS and len(result) == 1:
        for ob in root_objects(source):
            if ob == desk or any(k in ob.name.lower() for k in exclude):
                continue
            # 只有根对象；子物体会随原组合父级自动添加。
            low, high = box_of_object(ob)
            center = (low+high)*.5
            if flat_distance_to_rect(center,base_low,base_high) <= DESK_DETECTION_MARGIN:
                if center.z >= base_low.z-.5 and center.z <= base_high.z+2.0:
                    result.add(ob)

    # 办公椅总是单独的 BlenderKit 集合，强制加入，即使检测范围没覆盖。
    chair = choose_by_name(source, "Ribbed Leather Manager Chair Black")
    if chair:
        result.add(chair)
    else:
        report("警告：未找到 Ribbed Leather Manager Chair Black 办公椅，请核对原始场景。")

    full = set()
    for ob in result:
        full.update(descendants(ob, source.objects))
    report("完整桌面保留对象数量:",len(full),"（包含独立的办公椅和桌上杂物）")
    for ob in sorted(full,key=lambda v:v.name):
        report("  桌面:",ob.name)
    return full


def make_snapshot_collection(scene, objects, name):
    """对象链接到新集合而不移动、复制、删除源对象；通过集合实例整体放入目标场景。"""
    coll = bpy.data.collections.new(name)
    for obj in objects:
        coll.objects.link(obj)
    low,high=box_of_objects(objects)
    # 以物体组真实包围盒底部中心作为实例起点，保持每件家具全部相对位置。
    coll.instance_offset=Vector(((low.x+high.x)*.5,(low.y+high.y)*.5,low.z))
    return coll,(low,high)


def add_snapshot_instance(target, group, name, destination, scale=1.0, rotate_deg=0.0):
    inst = bpy.data.objects.new(name, None)
    target.objects.link(inst)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = group
    inst.empty_display_type = 'CUBE'
    inst.empty_display_size = .25
    inst.scale = (scale,)*3
    inst.rotation_euler.z = math.radians(rotate_deg)
    inst.location = Vector(destination)
    return inst


def source_bookcase_scene(current_scene):
    if BOOKCASE_BLEND_PATH:
        path = Path(bpy.path.abspath(BOOKCASE_BLEND_PATH))
    else:
        if not bpy.data.filepath:
            raise RuntimeError("请先保存当前 .blend 文件，或给 BOOKCASE_BLEND_PATH 填写绝对路径。")
        path = Path(bpy.data.filepath).parent / BOOKCASE_FILE_NAME
    if path.is_file() and bpy.data.filepath and path.resolve() == Path(bpy.data.filepath).resolve():
        report("当前打开的就是书柜源文件，直接从 Scene 里提取书柜。")
        return current_scene
    if not path.is_file():
        existing=choose_bookshelf(current_scene)
        if existing:
            report("外部书柜源文件未找到，改用当前原场景书柜:",existing.name)
            return current_scene
        report("书柜源文件找不到:", path)
        report("将保留当前书柜占位模型。请在脚本顶部 BOOKCASE_BLEND_PATH 填入绝对路径。")
        return None
    try:
        with bpy.data.libraries.load(str(path),link=False) as (data_from,data_to):
            preferred = "Scene" if "Scene" in data_from.scenes else next(iter(data_from.scenes),None)
            data_to.scenes = [preferred] if preferred is not None else []
        if not data_to.scenes or not data_to.scenes[0]:
            report("书柜文件中未找到场景:",path)
            return None
        result=data_to.scenes[0]
        result.name="SRC_Bookcase_Imported_Keep"
        report("已导入书柜文件的原始布局场景:", path.name)
        return result
    except Exception as exc:
        report("外部文件加载失败:",type(exc).__name__,str(exc))
        return None


def choose_bookshelf(scene):
    if scene is None:
        return None
    roots = root_objects(scene)
    for name in BOOKCASE_PREFERENCE:
        ob = next((o for o in roots if o.name == name),None)
        if ob: return ob
    for ob in roots:
        if any(x in ob.name.lower() for x in ("bookcase","bookshelf","书架","书柜")):
            return ob
    return None


def select_books_inside_shelf(scene, shelf):
    if shelf is None:
        return set(), []
    low,high=box_of_object(shelf)
    result={shelf}
    skipped=[]
    # 为书柜上原本紧靠边缘或倾斜的书保留一点余量，不把远处散书加入新场景。
    delta=Vector((.19,.19,.21))
    low -= delta
    high += delta
    for ob in root_objects(scene):
        if ob == shelf:
            continue
        name=ob.name.lower()
        if not any(w in name for w in ("book", "volume", "novel", "magazine")):
            continue
        blo,bhi=box_of_object(ob)
        center=(blo+bhi)*.5
        inside=(all(low[i]<=center[i]<=high[i] for i in range(3)))
        if inside:
            result.add(ob)
        else:
            skipped.append(ob.name)
    full=set()
    for ob in result:
        full.update(descendants(ob,scene.objects))
    return full,skipped


def mark_log(entries):
    txt=bpy.data.texts.get("L01_v4_检测记录") or bpy.data.texts.new("L01_v4_检测记录")
    txt.clear()
    txt.write("《第七日》v4 自动识别记录\n")
    txt.write("原文件对象不会被删除、移动或缩放。\n")
    for title, items in entries:
        txt.write("\n--- %s (%d) ---\n" % (title,len(items)))
        for it in sorted(items):
            txt.write(str(it)+"\n")


def replace_preview(scene, to_remove):
    # 仅删除旧脚本生成的错误实例/占位；主房间、隐藏小房间、沙发、文件柜全部保留。
    for ob in list(scene.objects):
        if ob.name in to_remove or ob.name.startswith("PLACEHOLDER_BOOKCASE"):
            report("从预览移除旧对象:",ob.name)
            bpy.data.objects.remove(ob,do_unlink=True)


def find_or_make_preview_furniture(scene):
    # 必须在【目标场景】内部查找，不能误用旧预览场景的同名集合。
    return next(
        (c for c in scene.collection.children if c.name.startswith(("PR_ExistingAssets_Instances", "PR_Furniture_Instances", "PR_Updated_Furniture_v4"))), None
    ) or make_child(scene.collection,"PR_Updated_Furniture_v4")


def make_child(parent,name):
    new=bpy.data.collections.new(name)
    parent.children.link(new)
    return new


def build():
    current=bpy.context.scene
    target = current if current and current.name.startswith(TARGET_SCENE_PREFIX) else next(
        (s for s in reversed(list(bpy.data.scenes)) if s.name.startswith(TARGET_SCENE_PREFIX)),None)
    if target is None:
        report("当前没有工作室：自动创建9×11米主房间和右侧隐藏房间。")
        v5_build_room()
        target = bpy.context.scene if bpy.context.scene.name.startswith(TARGET_SCENE_PREFIX) else next((s for s in bpy.data.scenes if s.name.startswith(TARGET_SCENE_PREFIX)),None)
    source=bpy.data.scenes.get(SOURCE_SCENE_NAME)
    if source is None or source==target or choose_by_name(source, "Complete Office Workplace Setup") is None:
        source=next((s for s in bpy.data.scenes if s!=target and choose_by_name(s, "Complete Office Workplace Setup")),None)
    if source is None:
        raise RuntimeError("没有找到完整电脑桌的原始场景，请在包含完整电脑桌模型的 .blend 文件里运行。")

    # 先进行不破坏源文件的“快照”。
    items=choose_complete_desk(source)
    desk_coll,desk_bounds=make_snapshot_collection(source,items,"L01_v4_FullDesk_With_Chair_And_Props")
    report("整套办公桌世界空间原始包围盒尺寸:", tuple(round(x,3) for x in desk_bounds[1]-desk_bounds[0]))

    book_src=source_bookcase_scene(source)
    book_root=choose_bookshelf(book_src)
    if book_root:
        # 文件里存在两种书柜，选择附近摆书最多的那个，避免把空柜误当最终书架。
        other_candidates=[o for o in root_objects(book_src)
                          if o != book_root and o.name in BOOKCASE_PREFERENCE]
        candidates=[book_root]+other_candidates
        evaluated=[]
        for candidate in candidates:
            chosen,discarded=select_books_inside_shelf(book_src,candidate)
            score=sum(1 for o in chosen if o != candidate and
                      any(w in o.name.lower() for w in ("book","magazine","volume")))
            evaluated.append((score,candidate,chosen,discarded))
            report("候选书柜:",candidate.name,"附近柜内独立书本数:",score)
        evaluated.sort(key=lambda entry:entry[0],reverse=True)
        _,book_root,books,skipped=evaluated[0]
        report("最终采用书柜:",book_root.name)
        book_coll,bb=make_snapshot_collection(book_src,books,"L01_v4_Bookcase_And_InsideBooks")
    else:
        books,skipped,book_coll,bb=set(),[],None,None
        report("没有识别到完整书柜，请检查外部文件里是否有 Bookshelf 或 Antique Bookcase 对象。")

    container=find_or_make_preview_furniture(target)
    replace_preview(target,set(PREVIEW_DESK_NAMES+PREVIEW_BOOK_NAMES+
                               ("L01_v4_Desk_Complete_KeepOriginal","L01_v4_Bookcase_Clean")))
    inst=add_snapshot_instance(container,desk_coll,"L01_v4_Desk_Complete_KeepOriginal",
                               DESK_DESTINATION,scale=1.0,rotate_deg=0.0)
    inst["desk_scale_locked"]=True
    inst["desk_internal_layout_preserved"]=True

    if book_coll:
        width=bb[1]-bb[0]
        from mathutils import Euler
        q=Euler((0,0,math.radians(BOOKCASE_ROTATION))).to_matrix()
        dx=abs(q[0][0])*width.x+abs(q[0][1])*width.y
        dy=abs(q[1][0])*width.x+abs(q[1][1])*width.y
        scale=min(BOOKCASE_TARGET_SIZE[0]/max(dx,.001),
                  BOOKCASE_TARGET_SIZE[1]/max(dy,.001),
                  BOOKCASE_TARGET_SIZE[2]/max(width.z,.001))
        scale=min(max(scale,.0001),100.0)
        add_snapshot_instance(container,book_coll,"L01_v4_Bookcase_Clean",
                              BOOKCASE_DESTINATION,scale,BOOKCASE_ROTATION)
        report("书柜等比缩放:",round(scale,4),"有效尺寸",
               (round(dx*scale,2),round(dy*scale,2),round(width.z*scale,2)))
        report("书柜外未导入散书数量:",len(skipped))
    else:
        report("书柜保留待处理：没有找到可可靠识别的源书柜对象。")

    mark_log([("桌面完整组合（含椅子）",[o.name for o in items]),
              ("书柜及柜内书",[o.name for o in books]),
              ("柜外散书（本次布局未导入，不删除源文件）", skipped)])
    if bpy.context.window:
        bpy.context.window.scene=target
    report("布局细化完成。房间大小和结构未改变；完整电脑桌及椅子全部按原比例、原朝向组合平移。")
    report("请使用【文件 → 另存为】保存一个新 .blend；千万不要覆盖你的原始模型文件。")

if __name__ == "__main__":
    build()