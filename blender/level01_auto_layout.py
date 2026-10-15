# -*- coding: utf-8 -*-
"""第七日第一关 · 大房间布局 v2
先在原始 Blender 场景中选择书柜全部组件或书柜集合实例，再运行。
办公桌整体：原比例、原朝向、内部各物体原位置；仅整个组合平移。
原始办公桌和书柜本体不会被改动；新场景仅创建集合实例。
"""
import bpy
import math
from mathutils import Vector, Euler

SCENE = "LEVEL01_Workshop_9x11_v2"
ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT = 9.0, 11.0, 3.4

# 收藏源集合, 实例名, 目标XY, 角度, 目标最大宽深高, 是否强制原尺寸
ASSETS = [
    ("Complete Office Workplace Setup", "PR_CompleteDesk_UNCHANGED", (0.0, 1.2), 0, None, True),
    ("Corner Sofa", "PR_CornerSofa", (3.05, -1.6), 270, (1.7, 2.5, 1.08), False),
    ("Drawer Cabinet", "PR_DrawerCabinet", (3.64, 2.1), 0, (1.05, .78, 1.6), False),
]

def mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgba, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgba, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.88
    return m

def group(parent, name):
    coll = bpy.data.collections.new(name)
    parent.children.link(coll)
    return coll

def box(coll, name, pos, dims, surface):
    x, y, z = [s * 0.5 for s in dims]
    verts = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
             (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),
             (1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    ob.location = pos
    mesh.materials.append(surface)
    return ob

def bounds(coll):
    vertices = []
    for ob in coll.all_objects:
        if ob.type not in {'MESH','CURVE','FONT','SURFACE','META'}:
            continue
        try:
            vertices.extend(ob.matrix_world @ Vector(v) for v in ob.bound_box)
        except (ValueError, AttributeError):
            pass
    if not vertices:
        return None
    low = Vector(tuple(min(v[i] for v in vertices) for i in range(3)))
    high = Vector(tuple(max(v[i] for v in vertices) for i in range(3)))
    return low, high

def get_bookcase_source():
    """仅从当前原始场景选择或明确书柜集合识别，不猜测散落的书本。"""
    current = bpy.context.scene
    selected = [] if (current and current.name.startswith("LEVEL01_Workshop")) else list(bpy.context.selected_objects)
    if len(selected) == 1 and selected[0].instance_type == 'COLLECTION' and selected[0].instance_collection:
        print("书柜：使用选中的 BlenderKit 集合", selected[0].instance_collection.name)
        return selected[0].instance_collection
    if selected:
        members = set()
        def include(obj):
            if obj in members:
                return
            members.add(obj)
            for child in obj.children:
                include(child)
        for obj in selected:
            include(obj)
        if 0 < len(members) <= 350 and any(o.type == "MESH" for o in members):
            col = bpy.data.collections.new("L01_SELECTED_BOOKCASE_SOURCE")
            for obj in members:
                col.objects.link(obj)
            print("书柜：整体引用选中对象和子对象", len(members))
            return col
    for col in bpy.data.collections:
        if col.name.startswith(("LEVEL01", "RM_", "PR_", "PZ_", "LT_")):
            continue
        name = col.name.lower()
        if any(term in name for term in ("bookcase","bookshelf","书柜","书架")) and len(col.all_objects) > 0:
            print("书柜：使用集合",col.name)
            return col
    print("没有识别出书柜；本次只放占位模型。请在原始场景选中完整书柜后再运行。")
    return None

def place(target, coll, label, xy, heading, max_dims=None, preserve_original=False):
    if coll is None:
        print("未找到模型集合:",label)
        return False
    bbox = bounds(coll)
    if bbox is None:
        print("集合没有可用网格:",coll.name)
        return False
    low,high = bbox
    ext = high-low
    angle = 0.0 if preserve_original else math.radians(heading)
    ca,sa = abs(math.cos(angle)),abs(math.sin(angle))
    width = ca*ext.x + sa*ext.y
    depth = sa*ext.x + ca*ext.y
    if preserve_original:
        scale = 1.0
    else:
        scale = min(max_dims[0]/max(width,0.00001),
                    max_dims[1]/max(depth,0.00001),
                    max_dims[2]/max(ext.z,0.00001))
        scale = max(0.0001,min(scale,1000.0))
    inst = bpy.data.objects.new(label,None)
    target.objects.link(inst)
    inst.instance_type = 'COLLECTION'
    inst.instance_collection = coll
    inst.rotation_euler.z = angle
    inst.scale = (scale,scale,scale)
    center_bottom = Vector(((low.x+high.x)*.5,(low.y+high.y)*.5,low.z))
    rot = Euler((0.0,0.0,angle)).to_matrix()
    inst.location = Vector((xy[0],xy[1],0)) - scale * (rot @ (center_bottom - coll.instance_offset))
    print("%s 原尺寸保留=%s 组合等比系数=%.4f 实际参考占地=(%.2fm×%.2fm)" %
          (label,str(preserve_original),scale,width*scale,depth*scale))
    if preserve_original and (width > ROOM_WIDTH*.7 or depth > ROOM_DEPTH*.6):
        print("提醒：办公桌可能有远距离散件或导入单位偏差，但根据你的要求不会缩放和拆分。")
    return True

def marker(coll, name, pos):
    ob = bpy.data.objects.new(name, None)
    coll.objects.link(ob)
    ob.location = pos
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = .26

def build():
    # 读取书柜选择：必须在切换到新场景之前
    bookshelf = get_bookcase_source()
    scene = bpy.data.scenes.new(SCENE)
    room = group(scene.collection,"RM_Architecture")
    props = group(scene.collection,"PR_Furniture_Instances")
    hints = group(scene.collection,"PZ_Puzzle_Markers")
    view = group(scene.collection,"LT_Camera_Light")

    plaster = mat("L01_Plasters",(0.69,0.69,0.67))
    timber = mat("L01_FloorWood",(0.38,0.28,0.21))
    pale = mat("L01_Ceiling",(0.78,0.78,0.76))
    glass = mat("L01_Window",(0.37,0.48,0.51))
    half_w,half_d = ROOM_WIDTH*.5,ROOM_DEPTH*.5
    h = ROOM_HEIGHT
    box(room,"RM_Floor",(0,0,-.10),(ROOM_WIDTH,ROOM_DEPTH,.2),timber)
    box(room,"RM_Left",(-half_w,0,h*.5),(.16,ROOM_DEPTH,h),plaster)
    box(room,"RM_Right",(half_w,0,h*.5),(.16,ROOM_DEPTH,h),plaster)

    entrance_width, entrance_height = 1.35, 2.38
    side = (ROOM_WIDTH-entrance_width)*.5
    side_x = entrance_width*.5+side*.5
    box(room,"RM_EntranceLeft",(-side_x,-half_d,h*.5),(side,.16,h),plaster)
    box(room,"RM_EntranceRight",(side_x,-half_d,h*.5),(side,.16,h),plaster)
    box(room,"RM_EntranceTop",(0,-half_d,(entrance_height+h)*.5),
        (entrance_width,.16,h-entrance_height),plaster)

    window_width,window_bottom,window_top = 2.5,.95,2.72
    side = (ROOM_WIDTH-window_width)*.5
    side_x = window_width*.5+side*.5
    box(room,"RM_BackLeft",(-side_x,half_d,h*.5),(side,.16,h),plaster)
    box(room,"RM_BackRight",(side_x,half_d,h*.5),(side,.16,h),plaster)
    box(room,"RM_BackSill",(0,half_d,window_bottom*.5),
        (window_width,.16,window_bottom),plaster)
    box(room,"RM_BackTop",(0,half_d,(window_top+h)*.5),
        (window_width,.16,h-window_top),plaster)
    box(room,"RM_WindowGlass",(0,half_d,(window_bottom+window_top)*.5),
        (window_width-.06,.012,window_top-window_bottom),glass)
    roof = box(room,"RM_Ceiling_HiddenForLayout",(0,0,h+.08),
        (ROOM_WIDTH,ROOM_DEPTH,.16),pale)
    roof.hide_viewport = True

    for source,label,xy,heading,dims,locked in ASSETS:
        place(props,bpy.data.collections.get(source),label,xy,heading,dims,locked)

    if not place(props,bookshelf,"PR_Bookcase",(-3.72,2.05),90,(.75,2.2,2.42),False):
        box(props,"PLACEHOLDER_Bookcase_Select_Then_Rerun",(-3.8,2.0,1.12),
            (.60,1.85,2.24),timber)

    for name,position in [
        ("SPAWN_Player_1m6",(0,-half_d+1.0,1.6)),
        ("PZ_HiddenDoor_RightWall",(half_w-.25,-.55,1.5)),
        ("PZ_CRT_NearDesk",(0,1.2,1.05)),
        ("PZ_HardDrive_7",(0,1.65,.18)),
        ("SP_BookcaseCeiling",(-half_w+.3,3.1,h-.35))]:
        marker(hints,name,position)

    cam_data = bpy.data.cameras.new("PlayerView_25mm")
    cam_data.lens = 25
    cam = bpy.data.objects.new("PlayerView_25mm",cam_data)
    view.objects.link(cam)
    cam.location = (0,-half_d+1.0,1.6)
    cam.rotation_euler = (Vector((0,1.1,1.25))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.camera = cam
    lamp_data = bpy.data.lights.new("CoolWindowLight",'AREA')
    lamp_data.energy = 670
    lamp_data.color = (.78,.87,1.0)
    lamp = bpy.data.objects.new("CoolWindowLight",lamp_data)
    view.objects.link(lamp)
    lamp.location = (0,half_d-.7,h-.5)
    lamp.rotation_euler = (Vector((0,0,1.0))-lamp.location).to_track_quat('-Z','Y').to_euler()
    if bpy.context.window:
        bpy.context.window.scene = scene
    print("完成 9m×11m×3.4m 预览；整套电脑桌未缩放、未旋转，原组合未改变。")
    print("请在 Blender 中【文件 → 另存为】，不要覆盖 studio_original.blend。")

build()
