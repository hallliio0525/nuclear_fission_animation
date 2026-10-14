"""
핵분열 연쇄반응 시뮬레이션 - 가지치기(트리) 버전 (Blender Python / bpy)
Nuclear Fission Chain Reaction - Branching Tree Version

업로드하신 이미지처럼:
- 맨 왼쪽: 중성자 하나가 핵 1개를 때림
- 그 핵이 분열하며 중성자 K개를 방출 -> 오른쪽의 새 핵 K개를 때림 (1세대)
- 그 K개가 각각 또 분열하며 K개씩 더 방출 -> K*K개를 때림 (2세대)
- ... 이런 식으로 오른쪽으로 갈수록 점점 넓게 가지치며 퍼짐

이번 버전은 '가까운 핵을 찾아서' 때리는 게 아니라, 처음부터 트리 구조
(부모->자식 관계)를 직접 계산해서 그 모양대로 핵을 배치합니다. 그래서
정확히 "1 -> K -> K*K -> ..." 모양으로 퍼져나가요.

사용법:
1. Blender 'Scripting' 탭 → 텍스트 에디터(큰 코드 입력창)에 붙여넣기
   (아래쪽 작은 'Python Console'에는 넣지 마세요!)
2. ▶ (Run Script) 버튼 클릭
3. 스페이스바로 재생
"""

import bpy
import random
import math
from collections import deque

# ============================================================
# 1. 파라미터
# ============================================================
MULTIPLICATION_K = 2      # 핵분열 하나당 튀어나가는 중성자(= 다음 세대 핵) 수
                           # 이미지처럼 3개씩 퍼지게 하고 싶으면 3으로 바꾸세요
                           # (단, 3이면 세대마다 핵 개수가 1,3,9,27로 늘어나서 꽤 많아져요)
MAX_GENERATIONS = 3        # 몇 세대까지 퍼질지 (K=2일 때 총 1+2+4+8=15개 핵)

SPACING_X = 4.5            # 세대(generation)끼리의 가로 간격 - 오른쪽으로 갈수록 이만큼 멀어짐
BASE_SPREAD = 6.0          # 자식들이 부모 기준 위아래로 퍼지는 기본 폭

NUCLEONS_PER_NUCLEUS = 14
CLUSTER_RADIUS = 0.55
NUCLEON_RADIUS = 0.17

TRAVEL_SPEED = 0.22
FRAGMENT_FLY_FRAMES = 16

INCOMING_NEUTRON_START_FRAME = 1
INCOMING_NEUTRON_HIT_FRAME = 16

FPS = 24

PROTON_COLOR = (0.9, 0.05, 0.05, 1.0)    # 양성자 = 빨간색
NEUTRON_COLOR = (0.95, 0.95, 0.95, 1.0)  # 중성자 = 하얀색
FREE_NEUTRON_COLOR = (1.0, 0.95, 0.3, 1.0)
FLASH_COLOR = (1.0, 0.55, 0.05, 1.0)


# ============================================================
# 2. 씬 초기화
# ============================================================
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


# ============================================================
# 3. 재질
# ============================================================
_MATERIAL_CACHE = {}

def get_material(name, color, emission_strength=0.0):
    if name in _MATERIAL_CACHE:
        return _MATERIAL_CACHE[name]
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    if emission_strength > 0 and "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    _MATERIAL_CACHE[name] = mat
    return mat


# ============================================================
# 4. 디테일한 핵(알갱이 뭉치) 만들기
# ============================================================
def random_point_in_sphere(radius):
    while True:
        x = random.uniform(-radius, radius)
        y = random.uniform(-radius, radius)
        z = random.uniform(-radius, radius)
        if x * x + y * y + z * z <= radius * radius:
            return (x, y, z)


def create_nucleus(position, index, n_nucleons=NUCLEONS_PER_NUCLEUS, cluster_radius=CLUSTER_RADIUS):
    bpy.ops.object.empty_add(location=position)
    empty = bpy.context.object
    empty.name = f"Nucleus_{index}"
    empty.empty_display_size = 0.05

    proton_mat = get_material("ProtonMat", PROTON_COLOR)
    neutron_mat = get_material("NeutronMat", NEUTRON_COLOR)

    for i in range(n_nucleons):
        offset = random_point_in_sphere(cluster_radius)
        world_pos = (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=NUCLEON_RADIUS, location=world_pos, segments=12, ring_count=8)
        nucleon = bpy.context.object
        nucleon.name = f"Nucleus_{index}_p{i}"
        nucleon.data.materials.append(proton_mat if random.random() < 0.55 else neutron_mat)
        nucleon.parent = empty
        nucleon.matrix_parent_inverse = empty.matrix_world.inverted()

    return empty


def create_fragment(position, index, n_nucleons, cluster_radius=CLUSTER_RADIUS * 0.75):
    frag = create_nucleus(position, index, n_nucleons=n_nucleons, cluster_radius=cluster_radius)
    frag.scale = (0, 0, 0)
    frag.keyframe_insert(data_path="scale", frame=1)
    return frag


def create_free_neutron(position, index):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=NUCLEON_RADIUS * 1.15, location=position, segments=12, ring_count=8)
    obj = bpy.context.object
    obj.name = f"FreeNeutron_{index}"
    mat = get_material("FreeNeutronMat", FREE_NEUTRON_COLOR, emission_strength=2.5)
    obj.data.materials.append(mat)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path="scale", frame=1)
    return obj


def create_flash(position, index):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, location=position, subdivisions=2)
    obj = bpy.context.object
    obj.name = f"Flash_{index}"
    mat = get_material("FlashMat", FLASH_COLOR, emission_strength=6.0)
    obj.data.materials.append(mat)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path="scale", frame=1)
    return obj


# ============================================================
# 5. 애니메이션 함수
# ============================================================
def animate_flash(flash_obj, frame):
    flash_obj.scale = (0, 0, 0)
    flash_obj.keyframe_insert(data_path="scale", frame=frame - 1)
    flash_obj.scale = (3.0, 3.0, 3.0)
    flash_obj.keyframe_insert(data_path="scale", frame=frame + 2)
    flash_obj.scale = (0, 0, 0)
    flash_obj.keyframe_insert(data_path="scale", frame=frame + 8)


def animate_neutron_flight(neutron_obj, start_pos, end_pos, start_frame, end_frame):
    neutron_obj.location = start_pos
    neutron_obj.scale = (1, 1, 1)
    neutron_obj.keyframe_insert(data_path="location", frame=start_frame)
    neutron_obj.keyframe_insert(data_path="scale", frame=start_frame)
    neutron_obj.location = end_pos
    neutron_obj.keyframe_insert(data_path="location", frame=end_frame)
    neutron_obj.scale = (0, 0, 0)
    neutron_obj.keyframe_insert(data_path="scale", frame=end_frame + 2)


def animate_nucleus_split(nucleus_empty, fission_frame):
    nucleus_empty.scale = (1, 1, 1)
    nucleus_empty.keyframe_insert(data_path="scale", frame=fission_frame - 1)
    nucleus_empty.scale = (0, 0, 0)
    nucleus_empty.keyframe_insert(data_path="scale", frame=fission_frame + 1)


def animate_fragment_flight(fragment_empty, start_pos, end_pos, start_frame, fly_frames):
    fragment_empty.location = start_pos
    fragment_empty.keyframe_insert(data_path="location", frame=start_frame)
    fragment_empty.keyframe_insert(data_path="scale", frame=start_frame)

    fragment_empty.scale = (1, 1, 1)
    fragment_empty.keyframe_insert(data_path="scale", frame=start_frame + 3)

    fragment_empty.location = end_pos
    fragment_empty.keyframe_insert(data_path="location", frame=start_frame + fly_frames)


def distance(p1, p2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))


# ============================================================
# 6. 트리(가지치기) 구조 계산
# ============================================================
def build_tree():
    """
    핵들의 부모-자식 관계와 위치를 미리 계산한다.
    세대(gen)가 깊어질수록 가로(X)로 멀어지고, 형제들은 부모를 기준으로
    위아래(Y)로 퍼진다. 형제 간 간격은 세대가 깊어질수록 절반씩 좁아져서
    (진짜 나무처럼) 전체 폭이 너무 넓어지지 않게 한다.
    """
    nodes = {}
    next_id = [0]

    root_id = next_id[0]
    next_id[0] += 1
    nodes[root_id] = {"pos": (0.0, 0.0, 0.0), "parent": None, "children": [], "gen": 0}

    frontier = [root_id]
    for gen in range(1, MAX_GENERATIONS + 1):
        spread = BASE_SPREAD / (MULTIPLICATION_K ** (gen - 1))
        new_frontier = []
        for parent_id in frontier:
            parent = nodes[parent_id]
            py = parent["pos"][1]
            for j in range(MULTIPLICATION_K):
                offset = (j - (MULTIPLICATION_K - 1) / 2) * spread
                child_pos = (gen * SPACING_X, py + offset, 0.0)
                cid = next_id[0]
                next_id[0] += 1
                nodes[cid] = {"pos": child_pos, "parent": parent_id, "children": [], "gen": gen}
                parent["children"].append(cid)
                new_frontier.append(cid)
        frontier = new_frontier

    return nodes, root_id


# ============================================================
# 7. 메인 시뮬레이션
# ============================================================
def run_simulation():
    clear_scene()

    # --- 7-1. 트리 구조 계산 후, 모든 핵을 미리 배치 ---
    tree, root_id = build_tree()
    for node_id, node in tree.items():
        node["obj"] = create_nucleus(node["pos"], node_id)
        node["fissioned"] = False

    free_id = [0]
    fragment_id = [1000]
    flash_id = [0]

    # --- 7-2. 바깥에서 중성자가 날아와 맨 왼쪽(루트) 핵을 때리며 시작 ---
    root_pos = tree[root_id]["pos"]
    incoming_start = (root_pos[0] - SPACING_X * 1.8, root_pos[1], 0.0)

    free_id[0] += 1
    incoming_neutron = create_free_neutron(incoming_start, free_id[0])
    animate_neutron_flight(
        incoming_neutron, incoming_start, root_pos,
        INCOMING_NEUTRON_START_FRAME, INCOMING_NEUTRON_HIT_FRAME
    )

    queue = deque()
    queue.append((root_id, INCOMING_NEUTRON_HIT_FRAME))
    tree[root_id]["fissioned"] = True
    max_frame_used = INCOMING_NEUTRON_HIT_FRAME

    # --- 7-3. 트리를 따라 연쇄반응 진행 (부모 -> 자식으로 명확하게) ---
    while queue:
        node_id, arrival_frame = queue.popleft()
        node = tree[node_id]

        flash_id[0] += 1
        flash = create_flash(node["pos"], flash_id[0])
        animate_flash(flash, arrival_frame)

        animate_nucleus_split(node["obj"], arrival_frame)
        max_frame_used = max(max_frame_used, arrival_frame + 8)

        # 쪼개진 조각 2개는 자식이 뻗어나가는 방향과 반대로(왼쪽 위/아래) 살짝 튐
        for sign in (1, -1):
            fragment_id[0] += 1
            fend = (node["pos"][0] - 0.8, node["pos"][1] + sign * 1.2, 0.0)
            frag = create_fragment(node["pos"], fragment_id[0], n_nucleons=NUCLEONS_PER_NUCLEUS // 2)
            animate_fragment_flight(frag, node["pos"], fend, arrival_frame, FRAGMENT_FLY_FRAMES)
            max_frame_used = max(max_frame_used, arrival_frame + FRAGMENT_FLY_FRAMES)

        # 자식 핵들로 중성자 발사 (트리 구조 그대로, 거리 탐색 없음)
        for child_id in node["children"]:
            child = tree[child_id]
            child["fissioned"] = True

            free_id[0] += 1
            neutron_obj = create_free_neutron(node["pos"], free_id[0])
            d = distance(node["pos"], child["pos"])
            travel_frames = max(5, int(d / TRAVEL_SPEED))
            hit_frame = arrival_frame + travel_frames
            animate_neutron_flight(neutron_obj, node["pos"], child["pos"], arrival_frame, hit_frame)

            queue.append((child_id, hit_frame))
            max_frame_used = max(max_frame_used, hit_frame + 8)

    # --- 7-4. 씬 설정: 트리 전체가 보이도록 카메라 배치 ---
    all_x = [n["pos"][0] for n in tree.values()]
    all_y = [n["pos"][1] for n in tree.values()]
    width = max(all_x) - min(all_x)
    height = max(all_y) - min(all_y)
    center_x = (max(all_x) + min(all_x)) / 2
    center_y = (max(all_y) + min(all_y)) / 2

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = max_frame_used + 20
    scene.render.fps = FPS

    cam_distance = max(width, height) * 1.0 + 10
    bpy.ops.object.camera_add(location=(center_x, center_y - cam_distance * 0.7, cam_distance * 0.6))
    cam = bpy.context.object
    cam.rotation_euler = (math.radians(60), 0, 0)
    cam.data.lens = 22
    scene.camera = cam

    bpy.ops.object.light_add(type='SUN', location=(center_x, center_y - 5, 12))
    sun = bpy.context.object
    sun.data.energy = 3.0

    fissioned_count = sum(1 for n in tree.values() if n["fissioned"])
    print(f"완료! 전체 {len(tree)}개 핵 중 {fissioned_count}개 분열, {MAX_GENERATIONS}세대, 길이 {scene.frame_end}프레임")


run_simulation()
