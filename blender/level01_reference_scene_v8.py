# -*- coding: utf-8 -*-
"""
《第七日》第一关 · v8 参考场景完整布置
基于 v7 继续修改，不重建原房间。

目标：
- 以当前 LEVEL01_Workshop_With_SaveRoom 为基础，做成“废弃游戏设计工作室”的完整可进入3D场景。
- 参考用户提供的工作室场景图：左侧书柜/资料墙，中部完整电脑桌，右侧沙发/文件柜/金属储物架，后墙窗户、暖气片，顶部工业格栅与管线。
- 完整电脑桌 + 办公椅 + 桌面所有摆件：绝不移动、缩放、旋转、拆分。
- 书柜：从原始 Scene 或外部 studio_original(1).blend 读取，保留原本已经摆好的柜内书，放大到真实工作室比例。
- 隐藏房：不改现有 CRT / SAVE / LOAD / 木桌 / 木椅；只增加场景整体环境，不碰隐藏房家具。
- 原始 Scene 与新工作室场景同时保留。
- 本脚本不自动保存 .blend，运行成功后请手动“另存为”。

兼容：Blender 3.2+。
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector, Matrix

# ==================== 用户设置 ====================
BOOKCASE_FILE = ""                     # 例如 r"C:\Users\xxx\Documents\studio_original(1).blend"
BOOKCASE_FILENAME = "studio_original(1).blend"
TARGET_PREFIX = "LEVEL01_Workshop_With_SaveRoom"
SOURCE_SCENE_NAME = "Scene"

# 当前房间尺寸沿用上一版：9 × 11 × 3.4m；右侧隐藏房约3.35 × 3.3 × 2.85m。
ROOM_W, ROOM_D, ROOM_H = 9.0, 11.0, 3.4
WALL_X = ROOM_W * 0.5
BACK_Y = ROOM_D * 0.5

# 书柜最终尺寸：参考图里的高大资料柜，而不是上一版偏小的书柜。
SHELF_HEIGHT = 2.55
SHELF_LENGTH = 2.65
SHELF_Y = 1.75
SHELF_WALL_GAP = 0.10

# 完整电脑桌的目标位置只在“没有已有正确实例”时使用。
# 已有 L01_v4/v6/v7 桌子时，本脚本完全不触碰。
DESK_FALLBACK_XY = (0.0, 1.15)

# 参考图中的家具位置。只移动脚本自己创建的预览实例，不碰源资产。
SOFA_XY = (3.18, -2.35)
CABINET_XY = (3.72, 1.75)
RACK_XY = (3.55, 3.25)

# ==================== 基础函数 ====================
def log(*args):
    print("[第七日 v8]", *args)

def popup(title, lines, icon='INFO'):
    def draw(self, context):
        for line in lines:
            self.layout.label(text=str(line)[:120])
    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        pass

def find_target():
    current = bpy.context.scene
    def room_like(s):
        return any(o.name.startswith(("RM_MainFloor", "RM_Floor")) for o in s.objects)
    if current and current.name.startswith(TARGET_PREFIX) and room_like(current):
        return current
    candidates = [s for s in bpy.data.scenes if s.name.startswith(TARGET_PREFIX) and room_like(s)]
    if candidates:
        return candidates[-1]
    candidates = [s for s in bpy.data.scenes if room_like(s)]
    if candidates:
        return candidates[-1]
    raise RuntimeError("没有找到上一版 LEVEL01_Workshop_With_SaveRoom 场景。请先打开之前生成并保存的工作室 .blend。")

def get_source_scene(target):
    source = bpy.data.scenes.get(SOURCE_SCENE_NAME)
    if source and source != target:
        return source
    for s in bpy.data.scenes:
        if s != target and any(o.name == "Complete Office Workplace Setup" for o in s.objects):
            return s
    return None

def ensure_collection(scene, name):
    old = scene.collection.children.get(name)
    if old:
        return old
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

def clear_v8(target):
    """只删除 v8 自己上次生成的对象；绝不删除桌子、书柜、房间或隐藏房。"""
    prefixes = ("V8_", "REF8_", "L01_v8_")
    for obj in list(target.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        if col.name.startswith("L01_v8_") and col != target.collection:
            try:
                bpy.data.collections.remove(col)
            except Exception:
                pass

def mat(name, rgb, rough=0.75, metallic=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    if p:
        if p.inputs.get("Base Color"): p.inputs["Base Color"].default_value = (*rgb, 1.0)
        if p.inputs.get("Roughness"): p.inputs["Roughness"].default_value = rough
        if p.inputs.get("Metallic"): p.inputs["Metallic"].default_value = metallic
    return m

def assign_material(obj, material):
    if obj.type != 'MESH':
        return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        for i in range(len(obj.data.materials)):
            obj.data.materials[i] = material

def box(col, name, loc, dims, material, bevel=0.0, rotation=None):
    x, y, z = [float(v) * 0.5 for v in dims]
    verts = [
        (-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
        (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)
    ]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    obj.location = loc
    if rotation:
        obj.rotation_euler = rotation
    if material:
        mesh.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new("SoftEdge", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj

def cylinder_between(col, name, a, b, radius, material, vertices=12):
    a, b = Vector(a), Vector(b)
    vec = b - a
    length = vec.length
    if length < 0.001:
        return None
    mid = (a + b) * 0.5
    bpy.context.view_layer.objects.active = None
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=length, location=mid
    )
    obj = bpy.context.object
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    obj.name = name
    obj.rotation_euler = vec.to_track_quat('Z', 'Y').to_euler()
    assign_material(obj, material)
    return obj

def collection_bounds(obj, depth=0, stack=None):
    if depth > 10:
        return None
    if stack is None:
        stack=set()
    pts=[]
    try:
        if obj.type in {'MESH','CURVE','FONT','SURFACE','META'}:
            pts.extend(obj.matrix_world @ Vector(p) for p in obj.bound_box)
    except Exception:
        pass
    if obj.instance_type == 'COLLECTION' and obj.instance_collection:
        grp=obj.instance_collection
        ptr=grp.as_pointer()
        if ptr not in stack:
            stack.add(ptr)
            base=obj.matrix_world @ Matrix.Translation(-grp.instance_offset)
            for child in grp.all_objects:
                if child == obj:
                    continue
                pts.extend(collection_bounds_with_matrix(child, base, depth+1, stack))
            stack.remove(ptr)
    if not pts:
        return None
    lo=Vector([min(p[i] for p in pts) for i in range(3)])
    hi=Vector([max(p[i] for p in pts) for i in range(3)])
    return lo,hi

def collection_bounds_with_matrix(obj, parent_matrix, depth=0, stack=None):
    if depth > 10:
        return []
    if stack is None:
        stack=set()
    pts=[]
    world=parent_matrix @ obj.matrix_world
    try:
        if obj.type in {'MESH','CURVE','FONT','SURFACE','META'}:
            pts.extend(world @ Vector(p) for p in obj.bound_box)
    except Exception:
        pass
    if obj.instance_type == 'COLLECTION' and obj.instance_collection:
        grp=obj.instance_collection
        ptr=grp.as_pointer()
        if ptr not in stack:
            stack.add(ptr)
            base=world @ Matrix.Translation(-grp.instance_offset)
            for child in grp.all_objects:
                pts.extend(collection_bounds_with_matrix(child, base, depth+1, stack))
            stack.remove(ptr)
    return pts

def make_collection_snapshot(name, objects, offset=None):
    col=bpy.data.collections.get(name)
    if col:
        return col
    col=bpy.data.collections.new(name)
    for o in objects:
        try:
            col.objects.link(o)
        except Exception:
            pass
    if offset is not None:
        col.instance_offset = offset
    return col

def collection_instance(target_col, source_col, name, location, scale=1.0, rot_z=0.0):
    obj=bpy.data.objects.new(name, None)
    target_col.objects.link(obj)
    obj.instance_type='COLLECTION'
    obj.instance_collection=source_col
    obj.location=location
    obj.scale=(scale,scale,scale)
    obj.rotation_euler.z=math.radians(rot_z)
    return obj

# ==================== 房间材质 ====================
def style_existing_architecture(target):
    wall = mat("V8_OldGreyGreenPlaster", (0.30,0.31,0.29), rough=0.92)
    floor = mat("V8_WornDarkFloor", (0.18,0.17,0.15), rough=0.72)
    ceiling = mat("V8_CeilingDark", (0.055,0.065,0.064), rough=0.88)
    glass = mat("V8_WindowCoolGlass", (0.42,0.53,0.57), rough=0.24)

    wall_prefix=("RM_LeftWall","RM_RightWall","RM_Entry","RM_Back_","RM_Window_","RM_Doorway","SR_")
    for obj in target.objects:
        n=obj.name
        if n.startswith("RM_Floor"):
            assign_material(obj,floor)
        elif n.startswith(wall_prefix):
            if obj.type=='MESH':
                assign_material(obj,wall)
        elif n.startswith("RM_WindowGlass"):
            assign_material(obj,glass)
        elif n.startswith("RM_Ceiling") or n.startswith("SR_Ceiling"):
            if obj.type=='MESH':
                assign_material(obj,ceiling)

    # 不隐藏房间，不重建墙体；这里只把白盒材质变成更接近参考图的旧工作室材质。
    log("已给现有建筑统一旧灰绿墙面、深色磨损地面和暗色天花材质。")

# ==================== 完整电脑桌：只检查，不修改 ====================
def desk_already_present(target):
    exact=("PR_MainDesk_LOCKED_UNCHANGED",
           "PR_MainDesk_UNCHANGED",
           "L01_v4_Desk_Complete_KeepOriginal",
           "L01_v5_Desk_Complete_KeepOriginal",
           "L01_v6_Desk_Complete_KeepOriginal")
    for n in exact:
        o=target.objects.get(n)
        if o:
            return o
    for o in target.objects:
        if o.get("do_not_move_or_scale") or o.get("desk_internal_layout_preserved"):
            return o
    return None

def ensure_complete_desk(target, source, furniture):
    existing=desk_already_present(target)
    if existing:
        log("完整电脑桌已存在：完全不移动、不缩放、不旋转。", existing.name)
        return existing

    if source is None:
        raise RuntimeError("目标场景没有已摆好的完整电脑桌，原始 Scene 也未找到。为避免破坏当前文件，v8停止。")

    root=source.objects.get("Complete Office Workplace Setup")
    if root is None:
        raise RuntimeError("原始 Scene 找不到 Complete Office Workplace Setup。v8不会用新桌子替换原桌。")

    items={root}
    chair=source.objects.get("Ribbed Leather Manager Chair Black")
    if chair:
        items.add(chair)

    # 把桌面附近独立摆件一起纳入快照，但只复制链接关系，不修改源对象。
    lohi=collection_bounds(root)
    if lohi:
        lo,hi=lohi
        for ob in source.objects:
            if ob==root or ob==chair or ob.parent is not None:
                continue
            try:
                a,b=collection_bounds(ob)
                if not a: continue
                c=(a+b)*0.5
                dx=max(lo.x-c.x,0,c.x-hi.x)
                dy=max(lo.y-c.y,0,c.y-hi.y)
                if math.hypot(dx,dy)<1.0 and lo.z-0.4<c.z<hi.z+2.0:
                    items.add(ob)
            except Exception:
                pass

    full=set()
    for root_obj in items:
        full.add(root_obj)
        full.update([c for c in source.objects if c.parent==root_obj])
    low,high=collection_bounds(root)
    offset=Vector(((low.x+high.x)*0.5,(low.y+high.y)*0.5,low.z)) if low else Vector((0,0,0))
    snap=make_collection_snapshot("L01_v8_CompleteDesk_LOCKED_SOURCE", full, offset)
    inst=collection_instance(furniture,snap,"L01_v8_Desk_Complete_KeepOriginal",
                             (DESK_FALLBACK_XY[0],DESK_FALLBACK_XY[1],0),1.0,0)
    inst["do_not_move_or_scale"]=True
    inst["desk_internal_layout_preserved"]=True
    log("未发现已有桌实例，因此从原始 Scene 建立一次完整桌快照；内部布局保持原样。")
    return inst

# ==================== 书柜 + 原书 ====================
def locate_book_file():
    if BOOKCASE_FILE.strip():
        p=Path(bpy.path.abspath(BOOKCASE_FILE)).expanduser()
        if p.is_file():
            return p
        raise RuntimeError("BOOKCASE_FILE 指向的书柜文件不存在：" + str(p))
    if bpy.data.filepath:
        base=Path(bpy.data.filepath).parent
        candidates=[base/BOOKCASE_FILENAME,base.parent/BOOKCASE_FILENAME,
                    Path.home()/ "Documents"/BOOKCASE_FILENAME,
                    Path.home()/ "Downloads"/BOOKCASE_FILENAME,
                    Path.home()/ "Desktop"/BOOKCASE_FILENAME]
        for p in candidates:
            if p.is_file() and p.resolve()!=Path(bpy.data.filepath).resolve():
                return p
    return None

def load_book_scene(path):
    key=str(path.resolve())
    for s in bpy.data.scenes:
        if s.get("v8_book_source")==key:
            return s
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):
        preferred='Scene' if 'Scene' in src.scenes else (src.scenes[0] if src.scenes else None)
        if not preferred:
            raise RuntimeError("书柜 .blend 中没有可用 Scene。")
        dst.scenes=[preferred]
    scene=dst.scenes[0]
    scene.name="SRC_Bookcase_v8_Keep"
    scene["v8_book_source"]=key
    return scene

def root_objects(scene):
    return [o for o in scene.objects if o.parent is None]

def is_book(obj):
    n=obj.name.lower()
    if obj.instance_type=='COLLECTION' and obj.instance_collection:
        n+=" "+obj.instance_collection.name.lower()
    return any(k in n for k in ("book","novel","volume","magazine","textbook","leather-bound","书"))

def find_shelf(scene):
    shelves=[]
    for o in root_objects(scene):
        n=o.name.lower()
        if any(k in n for k in ("bookshelf","bookcase","书柜","书架")):
            b=collection_bounds(o)
            if b:
                lo,hi=b
                if (hi-lo).z>1.0:
                    shelves.append((o,lo,hi))
    if not shelves:
        return None,None,None

    best=None
    for shelf,lo,hi in shelves:
        pad=Vector((0.35,0.35,0.28))
        sl,sh=lo-pad,hi+pad
        books=[]
        for o in root_objects(scene):
            if o==shelf or o in [x[0] for x in shelves] or not is_book(o):
                continue
            b=collection_bounds(o)
            if not b: continue
            a,c=b
            center=(a+c)*0.5
            center_in=all(sl[i]<=center[i]<=sh[i] for i in range(3))
            overlap=[max(0,min(c[i],sh[i])-max(a[i],sl[i])) for i in range(3)]
            vol=max((c.x-a.x)*(c.y-a.y)*(c.z-a.z),0.00001)
            ratio=(overlap[0]*overlap[1]*overlap[2])/vol
            if center_in or ratio>0.12:
                books.append(o)
        score=len(books) + (0.5 if shelf.name=="Bookshelf" else 0)
        if best is None or score>best[0]:
            best=(score,shelf,lo,hi,books)
    return best[1],best[2],best[3]

def remove_old_book_instances(target):
    for o in list(target.objects):
        if o.name.startswith(("PR_Bookcase","PLACEHOLDER_BOOKCASE","PLACEHOLDER_Bookcase",
                              "L01_v4_Bookcase","L01_v6_Bookcase","L01_v7_Bookcase")):
            if o.instance_type=='COLLECTION' or o.name.startswith("PLACEHOLDER_"):
                bpy.data.objects.remove(o,do_unlink=True)

def ensure_bookcase(target, furniture):
    source_scene=None
    # 优先当前文件里已经导入的 v7 书柜源场景。
    for s in bpy.data.scenes:
        if s.get("day7_bookfile_v7") or s.name.startswith("SRC_Bookcase"):
            source_scene=s
            break

    if source_scene is None:
        path=locate_book_file()
        if path:
            source_scene=load_book_scene(path)
        else:
            # 如果目标里已有 v7/v6 书柜，就不强行导入第二份。
            existing=next((o for o in target.objects if o.name.startswith("L01_v7_Bookcase")),None)
            if existing:
                log("使用目标场景中已有 v7 书柜，不再重复导入。")
                return existing
            raise RuntimeError("找不到书柜源文件。请把 studio_original(1).blend 放到当前工作室 .blend 同目录，或填写 BOOKCASE_FILE。")

    shelf,lo,hi=find_shelf(source_scene)
    if shelf is None:
        raise RuntimeError("书柜源文件中找不到真正的 Bookshelf/Bookcase。")

    # 收集书柜和柜内原书。这里按几何位置筛选，柜外散书不会进入新实例。
    selected={shelf}
    pad=Vector((0.35,0.35,0.28))
    sl,sh=lo-pad,hi+pad
    for o in root_objects(source_scene):
        if o==shelf or not is_book(o):
            continue
        b=collection_bounds(o)
        if not b: continue
        a,c=b
        center=(a+c)*0.5
        if all(sl[i]<=center[i]<=sh[i] for i in range(3)):
            selected.add(o)

    # 把子物体也加入快照。
    all_selected=set()
    for o in selected:
        all_selected.add(o)
        all_selected.update([c for c in source_scene.objects if c.parent==o])

    remove_old_book_instances(target)

    offset=Vector(((lo.x+hi.x)*0.5,(lo.y+hi.y)*0.5,lo.z))
    snap=make_collection_snapshot("L01_v8_Bookcase_With_OriginalBooks_SOURCE",
                                  all_selected,offset)
    size=hi-lo
    # 90°旋转后长度/深度互换。
    length=size.y
    depth=size.x
    scale=min(SHELF_HEIGHT/max(size.z,0.001),
              SHELF_LENGTH/max(length,0.001))
    scale=max(0.0001,min(scale,100.0))
    final_depth=depth*scale
    x=-WALL_X+SHELF_WALL_GAP+final_depth*0.5
    inst=collection_instance(furniture,snap,"L01_v8_Bookcase_Full_OriginalBooks",
                             (x,SHELF_Y,0),scale,90)
    inst["bookcase_source"]=shelf.name
    inst["original_books_preserved"]=True
    inst["cabinet_height_m"]=round(size.z*scale,3)
    inst["cabinet_length_m"]=round(length*scale,3)
    log("书柜完成：",shelf.name,
        "最终尺寸约",round(length*scale,2),"×",round(final_depth,2),"×",round(size.z*scale,2),
        "柜内原书已保留。")
    return inst

# ==================== 参考图环境：顶部、墙面、储物、地面 ====================
def ceiling_and_services(col):
    metal=mat("V8_GridMetal",(0.055,0.065,0.063),rough=.55,metallic=.65)
    black=mat("V8_DuctBlack",(0.035,0.042,0.040),rough=.5,metallic=.72)
    lightmat=mat("V8_Fluorescent",(0.78,0.83,0.80),rough=.28)
    # 吊顶格栅：完整覆盖主要活动区，但不压低到玩家头顶。
    z=3.18
    for x in [ -4.0,-3.0,-2.0,-1.0,0.0,1.0,2.0,3.0,4.0 ]:
        box(col,"V8_CeilingGrid_X_%+.1f"%x,(x,0,z),(.035,10.2,.055),metal)
    for y in [ -4.5,-3.5,-2.5,-1.5,-0.5,0.5,1.5,2.5,3.5,4.5 ]:
        box(col,"V8_CeilingGrid_Y_%+.1f"%y,(0,y,z),(8.2,.035,.055),metal)

    # 三组长灯，参考工业工作室，不用橙黄光。
    for i,y in enumerate((-2.0,0.8,3.1)):
        box(col,"V8_CeilingLight_%02d"%i,(0.2,y,3.12),(2.2,.18,.055),lightmat,.008)
        data=bpy.data.lights.new("V8_AreaLight_%02d"%i,'AREA')
        data.energy=260
        data.color=(0.78,0.86,0.96)
        data.shape='RECTANGLE'
        data.size=2.0
        data.size_y=.15
        light=bpy.data.objects.new("V8_AreaLight_%02d"%i,data)
        col.objects.link(light)
        light.location=(0.2,y,3.08)
        light.rotation_euler=(0,0,0)

    # 后右侧管道：沿天花向前延伸。
    cylinder_between(col,"V8_Duct_Main",(3.85,4.8,3.02),(3.85,-4.3,3.02),.17,black,16)
    cylinder_between(col,"V8_Duct_Branch",(3.85,2.0,3.02),(2.7,2.0,3.02),.11,black,14)
    # 左墙竖向电缆管线。
    for xoff in (-4.28,-4.17):
        cylinder_between(col,"V8_WallConduit_Left",(xoff,4.6,.55),(xoff,4.6,3.05),.025,metal,10)
    log("顶部工业格栅、灯具、管线已加入。")

def back_window_and_radiator(col):
    frame=mat("V8_WindowFrame",(0.08,0.09,0.085),rough=.52,metallic=.55)
    glow=mat("V8_WindowLight",(0.70,0.82,0.88),rough=.22)
    # 后墙已有窗口，这里只增加边框/窗台层次，不重新挖洞。
    ww=2.6
    y=5.39
    for x in (-ww*.5,ww*.5):
        box(col,"V8_WindowFrame_Vert",(x,y,1.78),(.075,.075,1.86),frame,.01)
    for z in (.92,2.64):
        box(col,"V8_WindowFrame_Horz",(0,y,z),(2.67,.075,.075),frame,.01)
    box(col,"V8_WindowGlassInset",(0,5.345,1.78),(2.45,.018,1.55),glow)

    # 右侧暖气片，参考图中的竖向散热片。
    for i in range(11):
        x=2.05+i*.12
        box(col,"V8_RadiatorFin_%02d"%i,(x,5.20,1.0),(.07,.20,1.28),frame,.012)
    box(col,"V8_RadiatorTop",(2.65,5.20,1.63),(1.40,.23,.07),frame,.012)
    log("后窗与暖气片层次完成。")

def left_wall_design_board(col):
    board=mat("V8_BoardGreen",(0.14,0.18,0.16),rough=.95)
    paper_mats=[
        mat("V8_PaperCream",(0.72,0.68,0.57),rough=.9),
        mat("V8_PaperWarm",(0.58,0.55,0.47),rough=.92),
        mat("V8_PaperWhite",(0.82,0.81,0.74),rough=.9)
    ]
    # 左墙资料区，给书柜旁边留下入口与通行空间。
    box(col,"V8_DesignBoard",(-4.39,3.15,2.0),(.045,2.15,1.35),board,.01)
    papers=[
        (3.10,2.25,.75,1.05,0),(2.42,2.03,.58,.82,1),
        (3.72,2.16,.52,.72,2),(2.80,1.45,.40,.58,0),
        (3.95,1.38,.38,.55,1)
    ]
    for i,(y,z,w,h,mi) in enumerate(papers):
        box(col,"V8_DesignSheet_%02d"%i,(-4.355,y,z),(.022,w,h),paper_mats[mi],.002)
    # 大型平面图/概念图。
    box(col,"V8_LargeFloorPlan",(-4.36,-.10,2.0),(.024,1.25,1.05),paper_mats[2],.002)
    # 便签条。
    note_mat=mat("V8_StickyNote",(0.63,0.66,0.39),rough=.88)
    for i,y in enumerate((-.68,-.40,-.12,.16,.44)):
        box(col,"V8_Sticky_%02d"%i,(-4.345,y,2.62),(.018,.20,.16),note_mat,.002)
    log("左墙游戏设计稿、平面图、便签区完成。")

def right_storage(col):
    metal=mat("V8_ShelfMetal",(0.09,0.105,0.10),rough=.5,metallic=.68)
    shelfmat=mat("V8_ShelfSurface",(0.16,0.15,0.13),rough=.7)
    # 参考图右后方高金属储物架。
    x,y=RACK_XY
    h=2.15
    for dx in (-.72,.72):
        for dy in (-.28,.28):
            box(col,"V8_RackPost",(x+dx,y+dy,h*.5),(.055,.055,h),metal,.008)
    for z in (.35,.82,1.29,1.76,2.14):
        box(col,"V8_RackShelf",(x,y,z),(1.50,.62,.045),shelfmat,.006)
    # 架上少量箱盒，避免“随机堆物”。
    carton=mat("V8_StorageBox",(0.32,0.34,0.30),rough=.88)
    for i,(dx,dy,z,sx,sy) in enumerate([
        (-.42,-.12,.52,.34,.28),(.10,-.08,.95,.42,.30),
        (.36,.10,1.42,.28,.34),(-.18,.08,1.90,.46,.25)
    ]):
        box(col,"V8_StorageBox_%02d"%i,(x+dx,y+dy,z),(sx,sy,.28),carton,.012)
    # 线框收纳筐。
    wire=mat("V8_WireBasket",(0.12,.13,.12),rough=.42,metallic=.7)
    for i in range(2):
        bx=x-.30+i*.62
        for dx in (-.18,.18):
            cylinder_between(col,"V8_BasketWire",(bx+dx,y-.28,.30),(bx+dx,y+.05,.30),.009,wire,8)
        for dy in (-.28,.05):
            cylinder_between(col,"V8_BasketWire",(bx-.18,y+dy,.30),(bx+.18,y+dy,.30),.009,wire,8)

def simple_coffee_table(col):
    wood=mat("V8_CoffeeTableWood",(0.23,0.15,0.095),rough=.78)
    metal=mat("V8_CoffeeTableMetal",(0.08,0.085,0.08),rough=.45,metallic=.65)
    x,y=2.35,-2.45
    box(col,"V8_CoffeeTableTop",(x,y,.48),(1.15,.60,.07),wood,.018)
    for dx in (-.46,.46):
        for dy in (-.22,.22):
            box(col,"V8_CoffeeTableLeg",(x+dx,y+dy,.24),(.055,.055,.43),metal,.006)

def floor_props(col):
    crate=mat("V8_WoodCrate",(0.24,0.15,0.09),rough=.86)
    paper=mat("V8_FloorPaper",(0.66,0.62,0.51),rough=.92)
    # 参考图的少量落地资料/箱子，控制数量。
    box(col,"V8_FloorCrate_01",(-2.75,3.75,.22),(.72,.55,.42),crate,.015)
    box(col,"V8_FloorCrate_02",(-3.15,3.40,.18),(.55,.45,.34),crate,.012)
    for i,(x,y,z,rx,ry) in enumerate([
        (-1.90,-.80,.012,.55,.34),(2.10,-.95,.014,.42,.30),
        (-2.55,2.55,.013,.46,.30),(1.15,3.55,.013,.38,.28)
    ]):
        box(col,"V8_FloorSheet_%02d"%i,(x,y,z),(rx,ry,.015),paper,.002,
            rotation=(0,0,math.radians((i%2)*6-3)))

# ==================== 参考图风格灯光与第一人称相机 ====================
def camera_and_lighting(target, col):
    # 删除 v8 自己的相机/灯光后重建，不碰旧脚本相机。
    cam_data=bpy.data.cameras.new("V8_PlayerCamera_26mm")
    cam=bpy.data.objects.new("V8_PlayerCamera_26mm",cam_data)
    col.objects.link(cam)
    cam.location=(0.0,-4.55,1.60)
    goal=Vector((0.0,1.35,1.45))
    cam.rotation_euler=(goal-cam.location).to_track_quat("-Z","Y").to_euler()
    cam_data.lens=26
    cam_data.sensor_width=36

    # 后窗冷白光。
    data=bpy.data.lights.new("V8_WindowSoftLight",'AREA')
    data.energy=1050
    data.color=(0.72,0.82,0.95)
    data.shape='RECTANGLE'
    data.size=2.6
    data.size_y=1.6
    key=bpy.data.objects.new("V8_WindowSoftLight",data)
    col.objects.link(key)
    key.location=(0,4.70,2.20)
    key.rotation_euler=(Vector((0,0,1.0))-key.location).to_track_quat("-Z","Y").to_euler()

    # 非橙黄的低强度环境补光。
    fill_data=bpy.data.lights.new("V8_CoolFill",'AREA')
    fill_data.energy=180
    fill_data.color=(0.48,0.56,0.62)
    fill_data.size=5.0
    fill=bpy.data.objects.new("V8_CoolFill",fill_data)
    col.objects.link(fill)
    fill.location=(0,-1.0,2.6)
    fill.rotation_euler=(Vector((0,1.0,1.1))-fill.location).to_track_quat("-Z","Y").to_euler()

    target.camera=cam
    target["V8_first_person_camera"]="26mm / 1.60m"
    log("第一人称相机：入口高度1.6m、26mm轻广角。")

def scene_display_setup(target):
    try:
        if target.world is None:
            target.world=bpy.data.worlds.new("V8_World")
        target.world.color=(0.018,0.022,0.022)
    except Exception:
        pass
    try:
        target.view_settings.exposure=-0.25
    except Exception:
        pass
    try:
        for area in bpy.context.screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.shading.color_type='MATERIAL'
    except Exception:
        pass

# ==================== 主流程 ====================
def main():
    target=find_target()
    source=get_source_scene(target)
    if bpy.context.window:
        bpy.context.window.scene=target

    # 先清理 v8 自己上次的结果，再创建同一套环境，保证可以重复运行。
    clear_v8(target)

    # 独立集合：所有 v8 新建环境资产都在这里。
    env=ensure_collection(target,"L01_v8_ReferenceEnvironment")
    furniture=ensure_collection(target,"L01_v8_FurniturePlacement")

    # 1. 建筑表面风格化：不重建墙体，不改变房间尺寸。
    style_existing_architecture(target)

    # 2. 电脑桌：已有正确版本绝不碰。
    ensure_complete_desk(target,source,furniture)

    # 3. 书柜：恢复原书并放大。
    ensure_bookcase(target,furniture)

    # 4. 参考图完整环境。
    ceiling_and_services(env)
    back_window_and_radiator(env)
    left_wall_design_board(env)
    right_storage(env)
    simple_coffee_table(env)
    floor_props(env)

    # 5. 如果上一版已经存在脚本摆好的沙发/文件柜，只移动“预览实例”到参考图位置；
    #    不碰源文件资产。
    sofa=next((o for o in target.objects if o.name.startswith("PR_CornerSofa")),None)
    if sofa:
        sofa.location.x,sofa.location.y=SOFA_XY
        sofa.rotation_euler.z=math.radians(270)
        log("沙发预览实例移到右侧休息区。")
    cabinet=next((o for o in target.objects if o.name.startswith("PR_DrawerCabinet")),None)
    if cabinet:
        cabinet.location.x,cabinet.location.y=CABINET_XY
        log("文件柜预览实例移到右后侧。")

    # 6. 相机/灯光。
    camera_and_lighting(target,env)
    scene_display_setup(target)

    # 7. 为后续 Godot 解谜保留的语义标记。
    target["L01_v8_reference_scene"]="realistic abandoned game design studio"
    target["L01_v8_main_room_size"]="9x11x3.4m"
    target["L01_v8_hidden_room"]="preserved from previous version"
    target["L01_v8_locked_desk"]="complete original desk + chair + props untouched"
    target["L01_v8_bookcase"]="original books preserved"
    target["L01_v8_next_step"]="surreal spatial distortion / puzzle dressing"

    txt=bpy.data.texts.get("L01_v8_场景说明") or bpy.data.texts.new("L01_v8_场景说明")
    txt.clear()
    txt.write("《第七日》第一关 v8：参考图完整工作室场景\n")
    txt.write("主房间：9×11×3.4m；右侧隐藏房沿用上一版。\n")
    txt.write("完整电脑桌：锁定，原比例/原朝向/桌面摆件/办公椅均未修改。\n")
    txt.write("书柜：高约 %.2fm，保留原柜内书籍，柜外散书不导入。\n" % SHELF_HEIGHT)
    txt.write("环境：工业吊顶格栅、灯具、管线、后窗、暖气片、设计稿墙、金属储物架、茶几、少量地面资料。\n")
    txt.write("隐藏房：CRT / SAVE / LOAD / RESET / 木桌 / 木椅沿用上一版，不在本次环境布置中移动。\n")
    txt.write("下一阶段：在不破坏真实工作室基础的前提下，再加入非欧几里得空间错乱。\n")

    log("==========================================")
    log("v8 完成：完整3D场景已在现有工作室场景中生成。")
    log("原始 Scene 保留；完整电脑桌/办公椅未修改；书柜与原书已恢复。")
    log("请从入口相机查看整体，再手动【文件 → 另存为】。")
    popup("《第七日》v8 场景生成完成",[
        "完整工作室环境已生成，不是图片。",
        "电脑桌/椅/桌面摆件保持原样。",
        "书柜已放大并保留柜内原书。",
        "下一步可以继续做空间错乱和第一关谜题。"
    ])

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        log("❌ v8 执行失败：",type(exc).__name__,str(exc))
        popup("v8 执行失败",[type(exc).__name__+": "+str(exc)],'ERROR')
        raise
