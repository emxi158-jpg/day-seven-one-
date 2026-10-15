# -*- coding: utf-8 -*-
"""第七日 · 第一关 6×8m 工作室预览布局。
在 studio_original.blend 的「脚本」工作区运行。
原始模型不移动、不拆分；新建独立场景并通过集合实例摆放。
"""
import bpy
import math
from mathutils import Vector, Euler

SCENE = "LEVEL01_Workshop_Preview"
ASSETS = [
    ("Complete Office Workplace Setup", "PR_MainDesk", (0.1, 0.8), 180, (2.7, 2.3, 2.4)),
    ("Corner Sofa", "PR_Sofa", (2.0, -1.7), 270, (1.65, 2.15, 1.5)),
    ("Drawer Cabinet", "PR_Drawer", (2.35, 1.75), 0, (1.05, 1.1, 1.7)),
    ("PROP_Bookcase", "PR_Bookcase", (-2.35, 1.3), 90, (1.15, 2.2, 2.6)),
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

def place(target, source_name, label, xy, heading, max_dims):
    coll = bpy.data.collections.get(source_name)
    if not coll:
        print("未识别模型集合:", source_name)
        return False
    limit = bounds(coll)
    if not limit:
        print("集合无可用几何体:", source_name)
        return False
    low, high = limit
    dim = high - low
    angle = math.radians(heading)
    ca, sa = abs(math.cos(angle)), abs(math.sin(angle))
    dx, dy = ca * dim.x + sa * dim.y, sa * dim.x + ca * dim.y
    factor = min(max_dims[0]/max(dx,0.0001),
                 max_dims[1]/max(dy,0.0001),
                 max_dims[2]/max(dim.z,0.0001))
    if factor <= 0 or factor > 10000:
        return False
    ob = bpy.data.objects.new(label, None)
    target.objects.link(ob)
    ob.instance_type = 'COLLECTION'
    ob.instance_collection = coll
    ob.rotation_euler.z = angle
    ob.scale = (factor,) * 3
    center_bottom = Vector(((low.x+high.x)*0.5, (low.y+high.y)*0.5, low.z))
    rotated = Euler((0,0,angle)).to_matrix() @ center_bottom
    ob.location = Vector((xy[0],xy[1],0)) - factor * rotated
    print("已摆放:", label, "等比缩放:", round(factor,4))
    return True

def marker(coll, name, pos):
    ob = bpy.data.objects.new(name, None)
    coll.objects.link(ob)
    ob.location = pos
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = .26

def build():
    # 每次运行生成独立新场景；Blender 自动在同名场景后加 .001 等后缀。
    # 旧的预览场景和源模型都不会被删除或覆盖。
    s = bpy.data.scenes.new(SCENE)
    room, props, hints, view = (
        group(s.collection,"RM_Architecture"),
        group(s.collection,"PR_Furniture_Instances"),
        group(s.collection,"PZ_Puzzle_Markers"),
        group(s.collection,"LT_Camera_Light"))
    plaster = mat("L01_Plasters",(0.69,0.69,0.67))
    timber = mat("L01_FloorWood",(0.38,0.28,0.21))
    pale = mat("L01_Ceiling",(0.78,0.78,0.76))
    glass = mat("L01_Window",(0.37,0.48,0.51))
    box(room,"RM_Floor",(0,0,-.1),(6,8,.2),timber)
    box(room,"RM_Left",(-3,0,1.5),(.16,8,3),plaster)
    box(room,"RM_Right",(3,0,1.5),(.16,8,3),plaster)
    # 南侧入口 (y=-4)，留 1.2m 宽门洞
    box(room,"RM_EntranceLeft",(-1.8,-4,1.5),(2.4,.16,3),plaster)
    box(room,"RM_EntranceRight",(1.8,-4,1.5),(2.4,.16,3),plaster)
    box(room,"RM_EntranceTop",(0,-4,2.72),(1.2,.16,.56),plaster)
    # 北侧窗户 (y=4)，留 2m 窗口
    box(room,"RM_BackLeft",(-2,4,1.5),(2,.16,3),plaster)
    box(room,"RM_BackRight",(2,4,1.5),(2,.16,3),plaster)
    box(room,"RM_BackSill",(0,4,.45),(2,.16,.90),plaster)
    box(room,"RM_BackTop",(0,4,2.69),(2,.16,.62),plaster)
    box(room,"RM_WindowGlass",(0,4,1.65),(1.91,.015,1.48),glass)
    roof = box(room,"RM_Ceiling_HiddenForLayout",(0,0,3.08),(6,8,.16),pale)
    # hide_set 需要物体已处于当前视图层，新创建场景尚未激活会报错。
    roof.hide_viewport = True
    for name, label, xy, heading, max_dims in ASSETS:
        placed = place(props, name, label, xy, heading, max_dims)
        if not placed and name == "PROP_Bookcase":
            box(props,"PLACEHOLDER_Bookcase",(-2.57,1.30,1.03),(.62,1.70,2.06),timber)
    for name, pos in [
        ("SPAWN_Player_1m6",(0,-3.2,1.6)),
        ("PZ_HiddenDoor_RightWall",(2.84,-.55,1.5)),
        ("PZ_CRT_OnDesk",(0,.6,1.05)),
        ("PZ_OldHardDrive_7",(0,.9,.16)),
        ("SP_Bookcase_ToCeiling",(-2.86,2.7,2.45))]:
        marker(hints,name,pos)
    camera_data = bpy.data.cameras.new("PlayerView_25mm")
    camera_data.lens = 25
    cam = bpy.data.objects.new("PlayerView_25mm",camera_data)
    view.objects.link(cam)
    cam.location = (0,-3.2,1.6)
    cam.rotation_euler = (Vector((0,1,1.4))-cam.location).to_track_quat('-Z','Y').to_euler()
    s.camera = cam
    lamp_data = bpy.data.lights.new("CoolWindowLight",'AREA')
    lamp_data.energy = 520
    lamp_data.color = (.78,.87,1.)
    light = bpy.data.objects.new("CoolWindowLight",lamp_data)
    view.objects.link(light)
    light.location = (0,3.25,2.75)
    light.rotation_euler = (Vector((0,0,.9))-light.location).to_track_quat('-Z','Y').to_euler()
    if bpy.context.window:
        bpy.context.window.scene = s
    print("第一关预览场景已创建。请另存为 level01_layout_preview.blend，不要覆盖原文件。")

build()
