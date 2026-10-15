# -*- coding: utf-8 -*-
"""
《第七日》第一关 · 家具细化修复 v4

针对已有的 LEVEL01_Workshop_With_SaveRoom 场景进行修复：
- 把原来已摆好的「完整电脑桌 + 桌面所有摆件 + 办公椅」组成一个快照集合实例；
  scale=(1,1,1)，rotation=(0,0,0)，只整体移动，原布局不变。
- 不动 9×11m 主房间、右侧附加隐藏房、CRT/SAVE/LOAD 占位。
- 从外部另一份 .blend 的【原场景】取出真正书柜与柜内书，忽略散落柜外的书。
- 不删除/不移动任何源文件资产。

使用：打开上次生成的（包含 Scene 和 LEVEL01_Workshop_With_SaveRoom 的）.blend，
在 Blender 中文版「脚本」工作区打开本 .py → 运行脚本。
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
        raise RuntimeError("未找到已生成的主房间+隐藏房间场景（LEVEL01_Workshop_With_SaveRoom）。先运行 v3 生成建筑，再运行本脚本。")
    source=bpy.data.scenes.get(SOURCE_SCENE_NAME)
    if source is None or source==target:
        raise RuntimeError("未找到保存完整办公桌布置的原始场景 Scene。请在包含原始模型的 .blend 里运行。")

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