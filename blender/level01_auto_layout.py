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

def build():
    old_scene = bpy.context.scene
    # 在读取外部资产之前，锁定原文件里的整套电脑桌集合。
    desk = bpy.data.collections.get("Complete Office Workplace Setup")
    sofa = bpy.data.collections.get("Corner Sofa")
    cabinet = bpy.data.collections.get("Drawer Cabinet")

    bookcase, hidden_count, bookcase_note = bookcase_from_other_blend()
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

if __name__ == "__main__":
    build()
