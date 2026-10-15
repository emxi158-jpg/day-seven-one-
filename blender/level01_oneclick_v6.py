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



# ===================== v6: 修复书柜与隐藏房家具 =====================
# 所有更新只作用于自动生成的预览场景，不改原始办公桌/书柜模型。
BOOKCASE_FINAL_HEIGHT = 2.46
BOOKCASE_FINAL_LENGTH = 2.35
BOOKCASE_WALL_GAP = 0.12

def v6_get_book_source(source):
    """保留先前导入的书柜场景；找不到时从第二份 .blend 导入。"""
    for s in bpy.data.scenes:
        if s != source and s.name.startswith("SRC_Bookcase_Imported_Keep"):
            if choose_bookshelf(s):
                return s
    return source_bookcase_scene(source)


def v6_book_name(obj):
    name = obj.name.lower()
    if obj.instance_type == 'COLLECTION' and obj.instance_collection:
        name += " " + obj.instance_collection.name.lower()
    return any(w in name for w in ("book", "volume", "novel", "magazine", "leather-bound", "书"))


def v6_bookcase_with_original_books(scene):
    """从原场景选最佳书柜 + 柜内已经摆好的独立书籍。
    以几何包围盒交叠判断，不依赖书本必须以 Book 开头，也不逐本重排。
    """
    if scene is None:
        return None, None, [], []
    shelves = [o for o in root_objects(scene)
               if any(w in o.name.lower() for w in ("bookshelf", "bookcase", "书柜", "书架"))]
    if not shelves:
        return None, None, [], []
    candidates = []
    all_roots = root_objects(scene)
    for shelf in shelves:
        lo, hi = box_of_object(shelf)
        dims = hi-lo
        if min(dims) < 0.00001 or dims.z < 0.001:
            continue
        # 保留外沿倾斜/横卧的书，容许柜体旁小范围超出；远处散书不纳入。
        pad_xy = max(.25, min(.72, max(dims.x,dims.y)*.22))
        margin_z = max(.18, min(.4, dims.z*.12))
        near_lo = lo - Vector((pad_xy,pad_xy,margin_z))
        near_hi = hi + Vector((pad_xy,pad_xy,margin_z))
        chosen = {shelf}
        skipped = []
        for other in all_roots:
            if other == shelf or other in shelves or not v6_book_name(other):
                continue
            blo, bhi = box_of_object(other)
            center = (blo+bhi)*.5
            # 既接受中心在书柜范围内的书，也接受与书柜内空间大幅交叠的书。
            center_in = all(near_lo[i] <= center[i] <= near_hi[i] for i in range(3))
            inter = [max(0., min(bhi[i],near_hi[i])-max(blo[i],near_lo[i]))
                     for i in range(3)]
            volume = 1.
            for i in range(3):
                volume *= max(bhi[i]-blo[i],.000001)
            intersects = (inter[0]*inter[1]*inter[2] >= volume*.18)
            if center_in or intersects:
                chosen.add(other)
            else:
                skipped.append(other.name)
        # 若书本已经属于书柜集合实例，则 shelf 本身就包含书本，不额外拆分。
        total = set()
        for obj in chosen:
            total.update(descendants(obj,scene.objects))
        candidates.append((len(chosen)-1, len(total), shelf, total, skipped))
        report("候选书柜及周边书籍:",shelf.name,"独立书籍组",len(chosen)-1,"合计对象",len(total))
    if not candidates:
        return None,None,[],[]
    # 已摆书较多的书柜优先。并列时优先 Bookshelf（常见已布好书的书架）。
    candidates.sort(key=lambda x:(x[0],x[1],x[2].name=="Bookshelf"),reverse=True)
    _, _, shelf, members, skipped = candidates[0]
    shelf_bounds = box_of_object(shelf)
    return shelf, shelf_bounds, list(members), skipped


def v6_make_shelf_instance(source_scene, shelf, shelf_bounds, members, target):
    """统一缩放柜体 + 书籍，柜体大小计算只看柜体，不看散书包围盒。"""
    group, _ = make_snapshot_collection(
        source_scene, members, "L01_v6_Bookcase_With_OriginalBooks")
    low, high = shelf_bounds
    size = high-low
    # 用柜体包围盒设置实例偏移，保证书本原始相对位置完全不改变。
    group.instance_offset = Vector(((low.x+high.x)*.5,(low.y+high.y)*.5,low.z))
    rotation = BOOKCASE_ROTATION
    rad = math.radians(rotation)
    width_x = abs(math.cos(rad))*size.x + abs(math.sin(rad))*size.y
    width_y = abs(math.sin(rad))*size.x + abs(math.cos(rad))*size.y
    scale_height = BOOKCASE_FINAL_HEIGHT / max(size.z,.00001)
    scale_width = BOOKCASE_FINAL_LENGTH / max(width_y,.00001)
    # 高度优先，但宽度最大约 2.35 m；不会因书本在柜外而缩得过小。
    scale = max(.0001, min(scale_height,scale_width,200.))
    result_depth = scale*width_x
    # 保证贴左墙且不穿墙：左墙内表面 x=-4.42
    x = -4.42 + BOOKCASE_WALL_GAP + result_depth*.5
    ob=add_snapshot_instance(target,group,"L01_v6_Bookcase_FullBooks",
                             (x,BOOKCASE_DESTINATION[1],0),scale,rotation)
    ob["source_shelf"]=shelf.name
    ob["book_parts"]=len(members)
    ob["bookcase_height_m"]=round(size.z*scale,3)
    report("书柜已放大，书本保持原位置：",shelf.name,
           "实际长×深×高(m):",
           (round(width_y*scale,2),round(result_depth,2),round(size.z*scale,2)),
           "独立源对象:",len(members))
    return ob


def v6_material(name, color, metallic=0., roughness=.7, emission=None):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    mat.diffuse_color=(*color,1.)
    surface=mat.node_tree.nodes.get("Principled BSDF")
    if surface:
        surface.inputs["Base Color"].default_value=(*color,1.)
        surface.inputs["Metallic"].default_value=metallic
        surface.inputs["Roughness"].default_value=roughness
        if emission:
            surface.inputs["Emission Color"].default_value=(*emission,1.)
            surface.inputs["Emission Strength"].default_value=.8
    return mat


def v6_wood_mat(name, base, alternate):
    mat=v6_material(name,base,roughness=.73)
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    surface=nodes.get("Principled BSDF")
    if not surface:
        return mat
    texcoord=nodes.new("ShaderNodeTexCoord")
    mapping=nodes.new("ShaderNodeVectorMath")
    mapping.operation='MULTIPLY'
    mapping.inputs[1].default_value=(2.0,11.0,1.8)
    noise=nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=5.2
    noise.inputs["Detail"].default_value=2.
    colors=nodes.new("ShaderNodeValToRGB")
    colors.color_ramp.elements[0].position=.24
    colors.color_ramp.elements[0].color=(*alternate,1.)
    colors.color_ramp.elements[1].position=.80
    colors.color_ramp.elements[1].color=(*base,1.)
    links.new(texcoord.outputs["Generated"],mapping.inputs[0])
    links.new(mapping.outputs["Vector"],noise.inputs["Vector"])
    links.new(noise.outputs["Fac"],colors.inputs["Fac"])
    links.new(colors.outputs["Color"],surface.inputs["Base Color"])
    return mat


def v6_piece(target, label, pos, dims, mat, bevel=.008):
    obj=block(target,label,pos,dims,mat)
    if bevel:
        modifier=obj.modifiers.new("Soft_rounded_edges","BEVEL")
        modifier.width=min(bevel,min(dims)*.20)
        modifier.segments=3
    return obj


def v6_hidden_room_furniture(target):
    """不引用主电脑桌。仅替换旧版白色木桌、木椅和CRT占位。
    实体模式启用【材质颜色】后可看到色彩，材质预览可见木纹。
    """
    # 先生成全新材质、模型，确认后再清理此前脚本生成的SR占位。
    old=[o for o in target.objects if
         o.name.startswith(("SR_","V6_SR_"))]
    for o in old:
        bpy.data.objects.remove(o,do_unlink=True)

    wood=v6_wood_mat("SR_v6_DarkOak",(0.37,.225,.125),(.18,.085,.045))
    wood2=v6_wood_mat("SR_v6_WornWood",(.51,.345,.21),(.28,.17,.10))
    metal=v6_material("SR_v6_Gunmetal",(.13,.145,.15),metallic=.6,roughness=.40)
    plastic=v6_material("SR_v6_OffwhiteCRT",(.64,.60,.51),roughness=.82)
    black=v6_material("SR_v6_GlassBlack",(.015,.035,.031),roughness=.2)
    green=v6_material("SR_v6_ScreenGreen",(.34,.92,.66),roughness=.25,
                      emission=(.13,.55,.30))
    paper=v6_material("SR_v6_Parchment",(.70,.66,.52),roughness=.86)

    # 旧木桌：面朝西侧隐藏门，桌面是深色木板，桌架有横梁。
    px,py = 6.93,.35
    v6_piece(target,"V6_SR_WoodTable_Top",(px,py,.76),(.88,1.36,.085),wood,.015)
    for dx in (-.35,.35):
        for dy in (-.56,.56):
            v6_piece(target,"V6_SR_TableLeg",(px+dx,py+dy,.36),
                     (.075,.075,.72),wood,.009)
    v6_piece(target,"V6_SR_TableSideBeam",(px,py-.56,.58),
             (.73,.055,.15),wood2,.009)
    v6_piece(target,"V6_SR_TableSideBeam",(px,py+.56,.58),
             (.73,.055,.15),wood2,.009)
    # 木椅：靠门，面向右侧CRT，使用深木质座椅和靠背横条。
    sx,sy=5.95,.34
    v6_piece(target,"V6_SR_ChairSeat",(sx,sy,.47),(.51,.50,.072),wood2,.018)
    for dx in (-.205,.205):
        for dy in (-.19,.19):
            v6_piece(target,"V6_SR_ChairLeg",(sx+dx,sy+dy,.24),
                     (.057,.065,.48),wood,.009)
    for dy in (-.19,.19):
        v6_piece(target,"V6_SR_ChairBackRail",(sx-.23,sy+dy,.84),
                 (.065,.07,.79),wood,.006)
    for z in (.76,.94,1.08):
        v6_piece(target,"V6_SR_ChairBackSlat",(sx-.23,sy,z),
                 (.064,.48,.105),wood2,.01)
    # CRT显示器：塑料后壳 / 显示面板 / 底座 / 通风槽等，不再只是一块白砖。
    v6_piece(target,"V6_SR_CRT_FullBody",(6.94,py,1.022),
             (.43,.63,.45),plastic,.037)
    v6_piece(target,"V6_SR_CRT_FrontFrame",(6.709,py,1.04),
             (.030,.57,.37),metal,.016)
    v6_piece(target,"V6_SR_CRT_DarkScreen",(6.688,py,1.055),
             (.013,.495,.288),black,.014)
    v6_piece(target,"V6_SR_CRT_Base",(6.955,py,.817),
             (.36,.40,.065),plastic,.014)
    v6_piece(target,"V6_SR_CRT_PowerButton",(6.681,.59,.894),
             (.018,.026,.021),green,.007)
    for y in (-.20,-.15,-.10,.10,.15,.20):
        v6_piece(target,"V6_SR_CRT_Vents",(7.164,py+y,1.09),
                 (.007,.016,.24),metal,.002)
    # CRT的文字只有静态预览，交互在Godot实现。
    font=bpy.data.curves.new("V6_SR_CRT_MENU","FONT")
    font.body="PLAYER / ZERO\nSAVE  LOAD\nRESET"
    font.size=.066
    font.space_line=1.28
    ob=bpy.data.objects.new("V6_SR_CRT_ScreenMenu",font)
    target.objects.link(ob)
    ob.location=(6.674,.13,1.115)
    ob.rotation_euler=(math.radians(90),0,math.radians(-90))
    font.materials.append(green)
    # 一点桌面细节，但不在主办公桌增删任何东西。
    v6_piece(target,"V6_SR_DeskNotes",(6.965,-.19,.811),
             (.24,.30,.013),paper,.002)
    v6_piece(target,"V6_SR_DeskNotes_Clip",(6.83,-.19,.826),
             (.04,.075,.008),metal,.002)
    report("隐藏房间家具改为深木桌椅、旧式CRT与独立材质，旧占位已清理。")


def v6_find_props(target):
    existing = next((c for c in target.collection.children if
                    c.name.startswith("PR_SaveRoomPlaceholders")),None)
    if existing:
        return existing
    return make_child(target.collection,"PR_SaveRoomPlaceholders")


def v6_enable_material_colors():
    """Blender默认实体着色忽略材质颜色，打开材质颜色便于看到木质家具。"""
    try:
        if bpy.context.screen:
            for area in bpy.context.screen.areas:
                if area.type=="VIEW_3D":
                    space=area.spaces.active
                    if space and space.shading.type=="SOLID":
                        space.shading.color_type='MATERIAL'
    except Exception as exc:
        report("视图材质显示设置未改变：",str(exc))

def v6_note_log(entries):
    txt=bpy.data.texts.get("L01_v6_识别报告") or bpy.data.texts.new("L01_v6_识别报告")
    txt.clear()
    txt.write("《第七日》v6 自动修复记录\n")
    txt.write("保留：完整办公桌 + 办公椅、主工作室和隐藏房结构。\n")
    for title, names in entries:
        txt.write("\n%s (%d)\n"%(title,len(names)))
        for name in sorted(names):
            txt.write("  "+name+"\n")



def build():
    # 必须保留已经搭对的完整电脑桌。若目标场景已有桌组，则绝不替换或移动。
    current=bpy.context.scene
    target = current if current and current.name.startswith(TARGET_SCENE_PREFIX) else next(
        (s for s in reversed(list(bpy.data.scenes)) if
         s.name.startswith(TARGET_SCENE_PREFIX)), None)

    source=bpy.data.scenes.get(SOURCE_SCENE_NAME)
    if source is None or choose_by_name(source,"Complete Office Workplace Setup") is None:
        source=next((s for s in bpy.data.scenes if s != target and
                     choose_by_name(s,"Complete Office Workplace Setup")),None)
    if target is None and source is None:
        raise RuntimeError("找不到原始完整电脑桌，请先打开 studio_original.blend。")
    created = target is None
    if created:
        v5_build_room()
        target = next((scene for scene in reversed(list(bpy.data.scenes)) if scene.name.startswith(TARGET_SCENE_PREFIX)), None)
        if target is None:
            raise RuntimeError("自动创建房间后未找到新场景，请保存截图给我。")

    furniture=find_or_make_preview_furniture(target)
    existing_desks=[o for o in target.objects
                    if o.name in ("L01_v4_Desk_Complete_KeepOriginal",
                                  "L01_v5_Desk_Complete_KeepOriginal",
                                  "L01_v6_Desk_Complete_KeepOriginal")]
    if existing_desks:
        report("办公桌已存在且用户确认摆放正确：完全不动它。")
    elif source:
        replace_preview(target,set(PREVIEW_DESK_NAMES))
        items=choose_complete_desk(source)
        desk_coll, desk_bounds=make_snapshot_collection(
            source,items,"L01_v6_Desk_Unchanged_WithChair")
        desk_instance=add_snapshot_instance(
            furniture,desk_coll,"L01_v4_Desk_Complete_KeepOriginal",
            DESK_DESTINATION,scale=1.,rotate_deg=0.)
        desk_instance["do_not_move_or_scale"]=True
        report("办公桌以原始比例平移，桌面和办公椅保留。")
    else:
        report("没有源办公桌场景，因此完全保留现有家具。")

    bookshelf_source=v6_get_book_source(source or current)
    shelf, shelf_bounds, books, excluded=v6_bookcase_with_original_books(bookshelf_source)
    # 只有找到真正的源书柜后，才从【预览场景】删除之前偏小、空置的书柜实例。
    if shelf and books:
        for obj in list(target.objects):
            if (obj.name in PREVIEW_BOOK_NAMES or
                obj.name in ("L01_v4_Bookcase_Clean","L01_v6_Bookcase_FullBooks") or
                obj.name.startswith(("PLACEHOLDER_BOOKCASE","PLACEHOLDER_Bookcase"))):
                bpy.data.objects.remove(obj,do_unlink=True)
        v6_make_shelf_instance(bookshelf_source,shelf,shelf_bounds,books,furniture)
    else:
        report("警告：未识别到源文件中的完整书柜；没有删除现有书柜。")

    v6_hidden_room_furniture(v6_find_props(target))
    if bpy.context.window:
        bpy.context.window.scene=target
    v6_enable_material_colors()
    v6_note_log([
        ("带入书柜的对象",[o.name for o in books]),
        ("未带入的书籍组合（疑似柜外散书）",excluded),
        ("保留原样的办公桌实例",[o.name for o in existing_desks])
    ])
    report("修复结束：未重建原有房间和桌子；书柜放大且保留柜内书；隐藏房家具已改为有材质的独立道具。")
    report("请【文件 → 另存为】，勿覆盖你的源 .blend 文件。")

if __name__ == "__main__":
    build()
