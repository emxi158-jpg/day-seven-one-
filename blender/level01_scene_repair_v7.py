# -*- coding: utf-8 -*-
"""《第七日》第一关 · v7 现有场景定点修复（Blender 4.x / 5.x）
只改：书柜+原已摆好的柜内书、隐藏房独立木桌木椅CRT材质。
不改：主房间、隐藏房建筑、完整办公桌、办公椅、桌面物品。
用法：打开【已摆好电脑桌】的工作室 .blend，再运行本 .py。
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector, Matrix

# 若书柜 .blend 不在当前工程同一目录，请改为绝对路径：
# 例：BOOKCASE_FILE = r"C:\Users\xxx\Documents\studio_original(1).blend"
BOOKCASE_FILE = ""
BOOKCASE_FILENAME = "studio_original(1).blend"
BOOKCASE_PREFERRED = "Bookshelf"  # 次选 Antique Bookcase
SHELF_HEIGHT_M = 2.38
SHELF_LENGTH_M = 2.65
SHELF_Y = 1.65
SHELF_WALL_GAP = 0.13

def log(*msg):
    print("[第七日 v7]", *msg)

def popup(title, lines, icon='INFO'):
    def draw(self, context):
        for line in lines:
            self.layout.label(text=str(line)[:120])
    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        pass

def get_target():
    def has_room(scene):
        return any(obj.name.startswith(("RM_MainFloor", "RM_Floor")) for obj in scene.objects)
    current = bpy.context.scene
    if current and has_room(current):
        return current
    available = [s for s in bpy.data.scenes if has_room(s)]
    if not available:
        raise RuntimeError("当前 .blend 没有工作室建筑。请打开 v5/v6 已生成并保存的房间文件；本脚本不会重新建房。")
    return available[-1]

def locate_book_file():
    if BOOKCASE_FILE.strip():
        p = Path(bpy.path.abspath(BOOKCASE_FILE)).expanduser()
        if not p.is_file():
            raise RuntimeError("书柜文件路径无效：" + str(p))
        return p
    choices = []
    if bpy.data.filepath:
        home = Path(bpy.data.filepath).parent
        choices.extend([home/BOOKCASE_FILENAME, home.parent/BOOKCASE_FILENAME])
    user = Path.home()
    for base in (user/"Documents", user/"Downloads", user/"Desktop", user/"文档", user/"下载"):
        choices.append(base/BOOKCASE_FILENAME)
    # 保持确定性：仅使用明确文件名，不搜索同名备份或猜测另一份blend。
    for p in choices:
        if p.is_file() and (not bpy.data.filepath or p.resolve()!=Path(bpy.data.filepath).resolve()):
            return p
    raise RuntimeError(
        "找不到书柜源文件 studio_original(1).blend。"
        "请把它放在当前工作室 .blend 同一文件夹，"
        "或将脚本顶部 BOOKCASE_FILE 填为书柜文件完整路径。")

def load_book_scene(path):
    source_key = str(path.resolve())
    for scene in bpy.data.scenes:
        if scene.get("day7_bookfile_v7") == source_key:
            return scene
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        preferred = 'Scene' if 'Scene' in src.scenes else (src.scenes[0] if src.scenes else None)
        if not preferred:
            raise RuntimeError("书柜文件中找不到任何 Blender 场景。")
        dst.scenes = [preferred]
    book_scene = dst.scenes[0] if dst.scenes else None
    if book_scene is None:
        raise RuntimeError("书柜文件里的场景未能载入，检查 Blender 文件是否损坏。")
    book_scene.name="SRC_Bookcase_v7_Keep"
    book_scene["day7_bookfile_v7"] = source_key
    return book_scene

def mesh_points(obj, mat=None, stack=None, depth=0):
    if depth>9:
        return []
    if mat is None:
        mat=obj.matrix_world.copy()
    if stack is None:
        stack=set()
    pts=[]
    if obj.type in {'MESH','CURVE','FONT','SURFACE','META'}:
        try:
            pts.extend(mat @ Vector(c) for c in obj.bound_box)
        except (AttributeError, ValueError):
            pass
    if obj.instance_type=="COLLECTION" and obj.instance_collection:
        grp=obj.instance_collection
        addr=grp.as_pointer()
        if addr not in stack:
            stack.add(addr)
            base=mat @ Matrix.Translation(-grp.instance_offset)
            for o in grp.all_objects:
                pts.extend(mesh_points(o,base @ o.matrix_world,stack,depth+1))
            stack.remove(addr)
    return pts

def bbox(obj):
    pts=mesh_points(obj)
    if not pts:
        at=obj.matrix_world.translation.copy()
        return at,at
    low=Vector([min(p[i] for p in pts) for i in range(3)])
    high=Vector([max(p[i] for p in pts) for i in range(3)])
    return low,high

def booklike(obj):
    txt=obj.name.lower()
    if obj.instance_type=="COLLECTION" and obj.instance_collection:
        txt+=" "+obj.instance_collection.name.lower()
    return any(t in txt for t in ("book","novel","volume","magazine","书","leather-bound"))

def walk_children(obj, available, collected):
    if obj in collected:
        return
    collected.add(obj)
    for c in obj.children:
        if c in available:
            walk_children(c,available,collected)

def candidate_shelves(scene):
    roots=[o for o in scene.objects if o.parent is None]
    result=[]
    for o in roots:
        txt=o.name.lower()
        if o.instance_type=="COLLECTION" and o.instance_collection:
            txt+=" "+o.instance_collection.name.lower()
        if any(t in txt for t in ("bookshelf","bookcase","书架","书柜")):
            lo,hi=bbox(o)
            delta=hi-lo
            if max(delta)>0.15:
                result.append(o)
    return result

def identify_books(scene):
    roots=[o for o in scene.objects if o.parent is None]
    candidates=candidate_shelves(scene)
    if not candidates:
        raise RuntimeError("书柜源文件中没找到 Bookshelf 或 Antique Bookcase 对象，请发我源文件的大纲视图截图。")
    options=[]
    for shelf in candidates:
        lo,hi=bbox(shelf)
        dim=hi-lo
        # 柜体边缘略向外扩大，以接纳侧边横放/斜靠的书，但跳过远离书柜的散书。
        margin_xy=max(.18,min(.70,max(dim.x,dim.y)*.18))
        padding=Vector((margin_xy,margin_xy,max(.14,dim.z*.09)))
        lo2,hi2=lo-padding,hi+padding
        matched=[]
        for other in roots:
            if other is shelf or other in candidates or not booklike(other):
                continue
            a,b=bbox(other)
            centroid=(a+b)*.5
            center_ok=all(lo2[i]<=centroid[i]<=hi2[i] for i in range(3))
            overlap=[max(0.,min(b[i],hi2[i])-max(a[i],lo2[i])) for i in range(3)]
            total=max((b.x-a.x)*(b.y-a.y)*(b.z-a.z),.00001)
            overlap_ratio=overlap[0]*overlap[1]*overlap[2]/total
            if center_ok or overlap_ratio>=.18:
                matched.append(other)
        score=len(matched)
        if shelf.name.startswith(BOOKCASE_PREFERRED):
            score+=.2
        options.append((score,shelf,matched))
        log("备选书柜",shelf.name,"柜体尺寸",tuple(round(v,2) for v in dim),
            "相邻独立书组数",len(matched))
    options.sort(key=lambda rec:rec[0],reverse=True)
    _,shelf,matched=options[0]
    selected=set()
    available=set(scene.objects)
    for o in [shelf]+matched:
        walk_children(o,available,selected)
    return shelf, matched, selected

def collection(parent,name):
    col=bpy.data.collections.new(name)
    parent.children.link(col)
    return col

def drop_existing_preview_books(target):
    prefixes=(
        "PR_Bookcase","PLACEHOLDER_BOOKCASE","PLACEHOLDER_Bookcase",
        "L01_v4_Bookcase_Clean","L01_v6_Bookcase_FullBooks",
        "L01_v7_Bookcase_Full_OriginalBooks")
    count=0
    for obj in list(target.objects):
        if not obj.name.startswith(prefixes):
            continue
        # 只有脚本实例和占位才可移除，绝不删除与原场景共享的书柜资产。
        if obj.instance_type!="COLLECTION" and not obj.name.startswith(("PLACEHOLDER_",)):
            continue
        for c in list(obj.users_collection):
            if obj.name in c.objects:
                c.objects.unlink(obj)
        if obj.users==0:
            bpy.data.objects.remove(obj)
        count+=1
    return count

def add_bookcase(target, source, shelf, matched, selected):
    low,hi=bbox(shelf)
    size=hi-low
    angle=math.radians(90)
    c,s=abs(math.cos(angle)),abs(math.sin(angle))
    depth=c*size.x+s*size.y
    length=s*size.x+c*size.y
    scale=min(SHELF_HEIGHT_M/max(size.z,.00001),
              SHELF_LENGTH_M/max(length,.00001))
    if scale<.00001 or scale>10000:
        raise RuntimeError("书柜尺寸数据异常，未修改已生成的房间。")
    # 新集合只引用原始书柜、柜内书，不动源文件里任何物体和材质。
    col=bpy.data.collections.new("L01_v7_ShelfPlusBooks_SOURCE")
    for ob in selected:
        col.objects.link(ob)
    col.instance_offset=Vector(((low.x+hi.x)*.5,(low.y+hi.y)*.5,low.z))
    dest=next((c for c in target.collection.children if c.name.startswith(("PR_ExistingAssets_Instances","PR_Furniture_Instances","PR_Updated_Furniture_v4"))),None)
    if dest is None:
        dest=collection(target.collection,"PR_v7_Furniture")
    x=-4.42+SHELF_WALL_GAP+depth*scale*.5
    # 替换前确保书柜源、尺寸和书都已准备好。
    removed=drop_existing_preview_books(target)
    instance=bpy.data.objects.new("L01_v7_Bookcase_Full_OriginalBooks",None)
    dest.objects.link(instance)
    instance.instance_type='COLLECTION'
    instance.instance_collection=col
    instance.scale=(scale,)*3
    instance.rotation_euler.z=angle
    instance.location=(x,SHELF_Y,0)
    instance["from_source"]=source.name
    instance["books_groups_included"]=len(matched)
    instance["objects_included"]=len(selected)
    log("书柜修复，来源",shelf.name,"缩放",round(scale,4),
        "书柜最终长/深/高",*[round(val*scale,2) for val in (length,depth,size.z)],
        "柜内书组",len(matched),"源对象",len(selected),"替换旧件",removed)
    return len(matched),len(selected),removed

def mat(name,rgb,rough=.7,metal=0.,emission=None):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color=(*rgb,1.0)
    m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value=(*rgb,1.)
        p.inputs["Roughness"].default_value=rough
        p.inputs["Metallic"].default_value=metal
        if emission:
            p.inputs["Emission Color"].default_value=(*emission,1.)
            p.inputs["Emission Strength"].default_value=1.
    return m

def wood_mat(name,base,dark):
    m=mat(name,base)
    nt=m.node_tree
    p=nt.nodes.get("Principled BSDF")
    if p:
        noise=nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value=15.5
        noise.inputs["Detail"].default_value=2.0
        tex=nt.nodes.new("ShaderNodeTexCoord")
        vector=nt.nodes.new("ShaderNodeVectorMath")
        vector.operation='MULTIPLY'
        vector.inputs[1].default_value=(2.,10.,2.)
        ramp=nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color=(*dark,1)
        ramp.color_ramp.elements[1].color=(*base,1)
        nt.links.new(tex.outputs["Generated"],vector.inputs[0])
        nt.links.new(vector.outputs["Vector"],noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"],ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"],p.inputs["Base Color"])
    return m

def prism(group,name,location,dimensions,material,bevel=0.0):
    dx,dy,dz=[d*.5 for d in dimensions]
    mesh=bpy.data.meshes.new(name+"_mesh")
    mesh.from_pydata(
      [(-dx,-dy,-dz),(dx,-dy,-dz),(dx,dy,-dz),(-dx,dy,-dz),
       (-dx,-dy,dz),(dx,-dy,dz),(dx,dy,dz),(-dx,dy,dz)],
      [],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    mesh.update()
    ob=bpy.data.objects.new(name,mesh)
    group.objects.link(ob)
    ob.location=location
    mesh.materials.append(material)
    if bevel:
        mod=ob.modifiers.new("SubtleEdgeSoftening","BEVEL")
        mod.width=min(bevel,min(dimensions)*.16)
        mod.segments=2
    return ob

def clear_old_save_props(target):
    """旧脚本的占位道具只在家具集合中删除，绝对不会碰 SR_Floor / SR_Wall。"""
    count=0
    names=("SR_WoodTable","SR_WoodChair","SR_Chair","SR_Table","SR_CRT",
           "V6_SR_","V7_SR_")
    for parent in target.collection.children:
        if not parent.name.startswith(("PR_SaveRoomPlaceholders","V7_SaveRoomFurniture")):
            continue
        for obj in list(parent.objects):
            if not obj.name.startswith(names):
                continue
            parent.objects.unlink(obj)
            if obj.users==0:
                bpy.data.objects.remove(obj)
            count+=1
    return count

def create_hidden_furniture(target):
    removed=clear_old_save_props(target)
    group=next((c for c in target.collection.children if c.name.startswith("V7_SaveRoomFurniture")),None)
    if group is None:
        group=collection(target.collection,"V7_SaveRoomFurniture_Visible")
    oak=wood_mat("V7_WornDarkOak",(0.48,.27,.13),(.18,.085,.035))
    lighter=wood_mat("V7_WoodChair",(0.56,.37,.21),(.27,.15,.074))
    metal=mat("V7_OxidisedMetal",(.14,.14,.135),rough=.53,metal=.55)
    plastic=mat("V7_AgedCRTBeige",(.62,.55,.41),rough=.73)
    glass=mat("V7_CRT_BlackGlass",(.012,.026,.027),rough=.18)
    green=mat("V7_CRT_GreenGlow",(.35,.92,.63),rough=.3,emission=(.15,.64,.33))
    paper=mat("V7_Paper",(.78,.71,.54),rough=.9)
    # 木桌沿着隐藏房最右侧摆放，深木桌板+四腿+支撑横档。
    X,Y=6.98,.35
    prism(group,"V7_SR_Table_Top",(X,Y,.76),(.80,1.30,.085),oak,.014)
    for dx in (-.31,.31):
        for dy in (-.53,.53):
            prism(group,"V7_SR_Table_Leg",(X+dx,Y+dy,.36),(.064,.066,.72),oak,.005)
    for dy in (-.54,.54):
        prism(group,"V7_SR_Table_Apron",(X,Y+dy,.63),(.68,.046,.12),lighter,.004)
    # 旧木椅靠近隐藏门，坐面和椅背有明确的木色。
    X,Y=5.94,.34
    prism(group,"V7_SR_Chair_Seat",(X,Y,.46),(.49,.48,.065),lighter,.016)
    for dx in (-.19,.19):
        for dy in (-.19,.19):
            prism(group,"V7_SR_Chair_Leg",(X+dx,Y+dy,.23),(.053,.053,.46),oak,.005)
    for y in (-.19,.19):
        prism(group,"V7_SR_Chair_BackPost",(X-.22,Y+y,.75),(.055,.055,.66),oak,.004)
    for z in (.79,.96):
        prism(group,"V7_SR_Chair_BackSlat",(X-.22,Y,z),(.060,.47,.095),lighter,.005)
    # CRT: 面向小房间入口（西侧），独立机壳、深色玻璃屏幕和金属边框。
    prism(group,"V7_SR_CRT_Case",(6.98,.35,1.03),(.40,.59,.39),plastic,.027)
    prism(group,"V7_SR_CRT_FrontBezel",(6.769,.35,1.04),(.025,.54,.34),metal,.013)
    prism(group,"V7_SR_CRT_Screen",(6.751,.35,1.05),(.012,.47,.26),glass,.008)
    prism(group,"V7_SR_CRT_Stand",(7.0,.35,.82),(.29,.26,.07),plastic,.01)
    prism(group,"V7_SR_CRT_Button",(6.746,.60,.909),(.014,.026,.017),green,.003)
    for y in (.11,.17,.23,.47,.53,.59):
        prism(group,"V7_SR_CRT_Vent",(7.184,y,1.03),(.007,.012,.19),metal,.002)
    prism(group,"V7_SR_PaperNote",(6.95,-.15,.807),(.23,.24,.012),paper,.002)
    # 在屏幕前添加真正使用发光材质的菜单文字。
    font=bpy.data.curves.new("V7_CRT_Font","FONT")
    font.body="PLAYER: ZERO\nSAVE / LOAD\nRESET"
    font.size=.058
    font.space_line=1.25
    label=bpy.data.objects.new("V7_SR_CRT_TEXT_SAVE_LOAD",font)
    group.objects.link(label)
    label.location=(6.740,.53,.1+1.008)
    label.rotation_euler=(math.pi/2,0,-math.pi/2)
    font.materials.append(green)
    log("隐藏房间：隐藏/删除旧占位",removed,"创建有材质家具",len(group.objects))
    return removed, len(group.objects)

def add_log(target,path,shelf,saved,changed,removed,number):
    report=bpy.data.texts.get("L01_v7_修复结果") or bpy.data.texts.new("L01_v7_修复结果")
    report.clear()
    report.write("《第七日》第一关：v7 修复结果\n")
    report.write("目标场景："+target.name+"\n")
    report.write("书柜源："+str(path)+"\n")
    report.write("书柜资产："+shelf.name+"\n")
    report.write("已收录的柜旁书籍组合："+str(saved)+"\n")
    report.write("书柜实例包含原对象数："+str(changed)+"\n")
    report.write("替换旧书柜物件数："+str(removed)+"\n")
    report.write("创建隐藏房家具对象数："+str(number)+"\n")
    report.write("完整电脑桌未触碰。房间建筑未触碰。\n")

def main():
    target=get_target()
    path=locate_book_file()          # 提前检查，不允许没找到文件就默默不改
    book_scene=load_book_scene(path)
    shelf,matched,selected=identify_books(book_scene)
    if not selected:
        raise RuntimeError("没有找到可用于修复书柜的对象。")
    # 只有源书柜检查通过后才开始修改现有工作室。
    saved,changed,old=add_bookcase(target,book_scene,shelf,matched,selected)
    removed,number=create_hidden_furniture(target)
    if bpy.context.window:
        bpy.context.window.scene=target
    # 实体视图默认只显示白色：改为按材质色显示。
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type=='VIEW_3D':
                shading=area.spaces.active.shading
                if shading.type=='SOLID':
                    shading.color_type='MATERIAL'
    add_log(target,path,shelf,saved,changed,old,number)
    target["DaySeven_layout_refinement"] = "v7_shelf_books_and_save_room_materials"
    log("✅ 修复已应用：",target.name,"书柜:",shelf.name,
        "独立书组:",saved,"原对象:",changed,"隐藏房家具:",number)
    popup("《第七日》v7 修复完成",[
        "目标场景："+target.name,
        "书柜："+shelf.name+" | 带入书组："+str(saved)+" | 原对象："+str(changed),
        "隐藏房新家具："+str(number)+" 件；完整电脑桌完全未触碰。",
        "检查大纲视图：V7_SaveRoomFurniture_Visible / L01_v7_Bookcase_Full_OriginalBooks"
    ])

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        log("❌ ",str(exc))
        popup("v7 未执行成功",[str(exc)],'ERROR')
        raise
