"""
핵분열 연쇄반응 시뮬레이션 - 일직선 버전 (Blender Python / bpy)
Nuclear Fission Chain Reaction - Straight Line Version

이번 버전에서 바뀐 점:
- 핵들을 격자가 아니라 한 줄로 길게 일직선 배치 (10개)
- 시작할 때 바깥에서 중성자 하나가 날아와서 맨 처음 핵을 맞히며 반응 시작
  (이전 버전은 중앙 핵이 "이미 분열 중"인 상태로 시작했는데, 이번엔 실제로 때리는 장면이 있음)
- 나머지 로직(섬광, 조각 2개로 분열, 연쇄반응)은 이전 버전과 동일

사용법:
1. Blender 'Scripting' 탭 → 텍스트 에디터(큰 코드 입력창)에 붙여넣기
   (아래쪽 작은 'Python Console'에는 넣지 마세요! 한 줄씩 입력하는 곳이라 에러 납니다)
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
NUM_NUCLEI = 10                # 일직선으로 배치할 핵 개수
SPACING = 4.5                   # 핵 사이 거리 (이게 길이를 결정함)
NUCLEONS_PER_NUCLEUS = 14
CLUSTER_RADIUS = 0.55
NUCLEON_RADIUS = 0.17

MULTIPLICATION_K = 2            # 분열당 튀어나가는 새 중성자 수
MAX_GENERATIONS = NUM_NUCLEI    # 줄 전체를 다 돌 수 있을 만큼 넉넉하게
TRAVEL_SPEED = 0.25
FRAGMENT_FLY_FRAMES = 18

INCOMING_NEUTRON_START_FRAME = 1
INCOMING_NEUTRON_HIT_FRAME = 16   # 첫 중성자가 날아와 맞는 시점

FPS = 24

PROTON_COLOR = (0.15, 0.4, 0.95, 1.0)
NEUTRON_COLOR = (0.25, 0.75, 0.35, 1.0)
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
# 6. 메인 시뮬레이션
# ============================================================
def run_simulation():
    clear_scene()

    # --- 6-1. 핵들을 일직선으로 배치 (X축 방향, Y=Z=0) ---
    nuclei = {}
    half = (NUM_NUCLEI - 1) / 2
    for i in range(NUM_NUCLEI):
        pos = ((i - half) * SPACING, 0.0, 0.0)
        obj = create_nucleus(pos, i)
        nuclei[i] = {"obj": obj, "pos": pos, "fissioned": False}

    free_id = [0]
    fragment_id = [1000]
    flash_id = [0]

    # --- 6-2. 바깥에서 중성자가 날아와 맨 왼쪽 핵을 때리면서 반응 시작 ---
    first_index = 0
    first_pos = nuclei[first_index]["pos"]
    incoming_start = (first_pos[0] - SPACING * 2.2, 0.0, 0.0)

    free_id[0] += 1
    incoming_neutron = create_free_neutron(incoming_start, free_id[0])
    animate_neutron_flight(
        incoming_neutron, incoming_start, first_pos,
        INCOMING_NEUTRON_START_FRAME, INCOMING_NEUTRON_HIT_FRAME
    )

    queue = deque()
    queue.append((first_index, INCOMING_NEUTRON_HIT_FRAME))
    nuclei[first_index]["fissioned"] = True

    max_frame_used = INCOMING_NEUTRON_HIT_FRAME
    reaction_radius = SPACING * 1.6
    generation = 0

    # --- 6-3. 연쇄반응 진행 (줄을 따라 쭉 퍼져나감) ---
    while queue and generation < MAX_GENERATIONS:
        next_queue = deque()
        while queue:
            target_index, arrival_frame = queue.popleft()
            data = nuclei[target_index]

            flash_id[0] += 1
            flash = create_flash(data["pos"], flash_id[0])
            animate_flash(flash, arrival_frame)

            animate_nucleus_split(data["obj"], arrival_frame)
            max_frame_used = max(max_frame_used, arrival_frame + 8)

            # 조각 2개는 줄과 수직 방향(Y축 쪽)으로 날아가게 해서 중성자 경로와 안 겹치게
            for sign in (1, -1):
                fragment_id[0] += 1
                fend = (data["pos"][0], data["pos"][1] + sign * 1.3, 0.0)
                frag = create_fragment(data["pos"], fragment_id[0], n_nucleons=NUCLEONS_PER_NUCLEUS // 2)
                animate_fragment_flight(frag, data["pos"], fend, arrival_frame, FRAGMENT_FLY_FRAMES)
                max_frame_used = max(max_frame_used, arrival_frame + FRAGMENT_FLY_FRAMES)

            # 새 중성자들을 줄 위의 아직 안 쪼개진 핵으로 발사
            candidates = []
            for other_index, other_data in nuclei.items():
                if other_data["fissioned"]:
                    continue
                d = distance(data["pos"], other_data["pos"])
                if d <= reaction_radius:
                    candidates.append((d, other_index))
            candidates.sort(key=lambda c: c[0])
            targets = candidates[:MULTIPLICATION_K]

            for d, other_index in targets:
                nuclei[other_index]["fissioned"] = True
                free_id[0] += 1
                neutron_obj = create_free_neutron(data["pos"], free_id[0])
                travel_frames = max(5, int(d / TRAVEL_SPEED))
                hit_frame = arrival_frame + travel_frames
                animate_neutron_flight(neutron_obj, data["pos"], nuclei[other_index]["pos"], arrival_frame, hit_frame)
                next_queue.append((other_index, hit_frame))
                max_frame_used = max(max_frame_used, hit_frame + 8)

        queue = next_queue
        generation += 1

    # --- 6-4. 씬 설정: 줄 전체가 잘 보이도록 카메라 배치 ---
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = max_frame_used + 20
    scene.render.fps = FPS

    line_length = NUM_NUCLEI * SPACING
    bpy.ops.object.camera_add(location=(0, -line_length * 0.55, line_length * 0.4))
    cam = bpy.context.object
    cam.rotation_euler = (math.radians(65), 0, 0)
    scene.camera = cam
    cam.data.lens = 24  # 광각: 긴 줄이 화면에 다 들어오도록

    bpy.ops.object.light_add(type='SUN', location=(3, -5, 10))
    sun = bpy.context.object
    sun.data.energy = 3.0

    fissioned_count = sum(1 for n in nuclei.values() if n["fissioned"])
    print(f"완료! 전체 {len(nuclei)}개 핵 중 {fissioned_count}개 분열, 총 {generation}세대, 길이 {scene.frame_end}프레임")


run_simulation()
