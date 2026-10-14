"""
핵분열 연쇄반응 시뮬레이션 - 평면/디테일 버전 (Blender Python / bpy)
Nuclear Fission Chain Reaction - Flat Plane, Detailed Nuclei Version

이번 버전에서 바뀐 점:
- 핵 개수를 9개로 줄임 (예전엔 125개였음)
- 핵 하나하나를 양성자(파랑)/중성자(초록) 알갱이들이 뭉친 디테일한 덩어리로 표현
  (업로드해주신 이미지처럼)
- 여러 층(3D grid)이 아니라 한 평면(XY, Z=0) 위에만 배치
- 카메라도 위에서 내려다보는 각도로 변경
- 핵분열 시: 주황색 섬광(에너지) + 쪼개진 조각 2개가 날아감 + 새 중성자들이 다음 핵으로 발사

사용법:
1. Blender 'Scripting' 탭 → 반드시 '텍스트 에디터'(큰 코드 입력창)에 붙여넣기
   (화면 아래쪽의 작은 'Python Console'(>>> 표시)에 넣으면 안 됩니다. 거긴 한 줄씩 입력하는 곳이에요.)
   비어있는 텍스트 블록이 없다면 에디터 위쪽 'New' 버튼으로 새로 만든 뒤 붙여넣으세요.
   또는 'Open' 버튼으로 이 파일을 직접 열어도 됩니다.
2. 코드 입력창 위쪽의 ▶ (Run Script) 버튼 클릭
3. 아래 타임라인에서 스페이스바로 재생
"""

import bpy
import random
import math
from collections import deque

# ============================================================
# 1. 파라미터 (바꿔보면서 실험해보세요)
# ============================================================
NUM_NUCLEI = 9                # 전체 핵 개수 (3x3 평면 배치)
SPACING = 5.0                  # 핵 사이 거리
NUCLEONS_PER_NUCLEUS = 14      # 핵 하나를 이루는 알갱이(양성자+중성자) 수
CLUSTER_RADIUS = 0.55          # 알갱이들이 뭉쳐있는 반경
NUCLEON_RADIUS = 0.17          # 알갱이 하나의 크기

MULTIPLICATION_K = 2           # 분열당 튀어나가는 새 중성자 수
MAX_GENERATIONS = 3            # 연쇄반응 세대 수 (1+2+4=7개까지 분열, 9개 중 7개 사용)
TRAVEL_SPEED = 0.25             # 중성자 이동 속도 (프레임당 거리)
FRAGMENT_FLY_FRAMES = 18        # 쪼개진 조각이 날아가는 데 걸리는 프레임 수

FPS = 24

PROTON_COLOR = (0.15, 0.4, 0.95, 1.0)        # 양성자 = 파란색
NEUTRON_COLOR = (0.25, 0.75, 0.35, 1.0)      # 중성자 = 초록색
FREE_NEUTRON_COLOR = (1.0, 0.95, 0.3, 1.0)   # 날아다니는 자유 중성자 = 노란색
FLASH_COLOR = (1.0, 0.55, 0.05, 1.0)         # 핵분열 순간 섬광 = 주황색


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
# 3. 재질(색) - 한 번만 만들고 재사용 (속도를 위해)
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
# 4. 알갱이들이 뭉친 '디테일한 핵' 만들기
# ============================================================
def random_point_in_sphere(radius):
    while True:
        x = random.uniform(-radius, radius)
        y = random.uniform(-radius, radius)
        z = random.uniform(-radius, radius)
        if x * x + y * y + z * z <= radius * radius:
            return (x, y, z)


def create_nucleus(position, index, n_nucleons=NUCLEONS_PER_NUCLEUS, cluster_radius=CLUSTER_RADIUS):
    """position을 중심으로 작은 공들을 뭉쳐서 디테일한 핵 하나를 만든다.
    반환값: 이 핵 전체를 한 번에 움직이거나 사라지게 할 때 쓰는 부모 Empty."""
    bpy.ops.object.empty_add(location=position)
    empty = bpy.context.object
    empty.name = f"Nucleus_{index}"
    empty.empty_display_size = 0.05  # 화면에 십자 표시가 거슬리지 않게 작게

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
    """핵분열 후 생기는 작은 조각(파편)을 만든다. 처음엔 숨겨둔다."""
    frag = create_nucleus(position, index, n_nucleons=n_nucleons, cluster_radius=cluster_radius)
    frag.scale = (0, 0, 0)
    frag.keyframe_insert(data_path="scale", frame=1)
    return frag


def create_free_neutron(position, index):
    """핵에서 튀어나가 다른 핵으로 날아가는 자유 중성자 (알갱이 하나)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=NUCLEON_RADIUS * 1.15, location=position, segments=12, ring_count=8)
    obj = bpy.context.object
    obj.name = f"FreeNeutron_{index}"
    mat = get_material("FreeNeutronMat", FREE_NEUTRON_COLOR, emission_strength=2.5)
    obj.data.materials.append(mat)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path="scale", frame=1)
    return obj


def create_flash(position, index):
    """핵분열 순간의 에너지 섬광 효과 (이미지의 노란 별 모양 느낌)."""
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, location=position, subdivisions=2)
    obj = bpy.context.object
    obj.name = f"Flash_{index}"
    mat = get_material("FlashMat", FLASH_COLOR, emission_strength=6.0)
    obj.data.materials.append(mat)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path="scale", frame=1)
    return obj


# ============================================================
# 5. 애니메이션 함수들
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
    """원래 핵 덩어리를 분열 순간에 사라지게 한다 (조각은 따로 새로 만듦)."""
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

    # --- 6-1. 핵들을 한 평면(XY) 위에 3x3으로 배치 (Z는 항상 0) ---
    nuclei = {}
    side = int(math.sqrt(NUM_NUCLEI))
    half = (side - 1) / 2
    idx = 0
    for gx in range(side):
        for gy in range(side):
            jitter_x = random.uniform(-0.3, 0.3)
            jitter_y = random.uniform(-0.3, 0.3)
            pos = (
                (gx - half) * SPACING + jitter_x,
                (gy - half) * SPACING + jitter_y,
                0.0,  # <- 모든 핵이 같은 평면 위에 (Z = 0)
            )
            obj = create_nucleus(pos, idx)
            nuclei[idx] = {"obj": obj, "pos": pos, "fissioned": False}
            idx += 1
            if idx >= NUM_NUCLEI:
                break
        if idx >= NUM_NUCLEI:
            break

    # --- 6-2. 연쇄반응 시작 (가운데 핵부터) ---
    center_index = len(nuclei) // 2
    reaction_radius = SPACING * 1.6
    free_id = [0]
    fragment_id = [1000]
    flash_id = [0]
    current_frame = 10

    queue = deque()
    queue.append((center_index, current_frame))
    nuclei[center_index]["fissioned"] = True

    max_frame_used = current_frame
    generation = 0

    while queue and generation < MAX_GENERATIONS:
        next_queue = deque()
        while queue:
            target_index, arrival_frame = queue.popleft()
            data = nuclei[target_index]

            # 핵분열: 섬광 + 원래 핵이 사라짐 + 조각 2개가 날아감
            flash_id[0] += 1
            flash = create_flash(data["pos"], flash_id[0])
            animate_flash(flash, arrival_frame)

            animate_nucleus_split(data["obj"], arrival_frame)
            max_frame_used = max(max_frame_used, arrival_frame + 8)

            angle = random.uniform(0, math.pi * 2)
            for sign in (1, -1):
                fragment_id[0] += 1
                fdir = (math.cos(angle) * sign, math.sin(angle) * sign, 0.0)
                fend = (
                    data["pos"][0] + fdir[0] * 1.3,
                    data["pos"][1] + fdir[1] * 1.3,
                    0.0,
                )
                frag = create_fragment(data["pos"], fragment_id[0], n_nucleons=NUCLEONS_PER_NUCLEUS // 2)
                animate_fragment_flight(frag, data["pos"], fend, arrival_frame, FRAGMENT_FLY_FRAMES)
                max_frame_used = max(max_frame_used, arrival_frame + FRAGMENT_FLY_FRAMES)

            # 자유 중성자들을 주변의 안 쪼개진 핵으로 발사
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

    # --- 6-3. 씬 설정: 위에서 내려다보는 카메라 (평면이 잘 보이도록) ---
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = max_frame_used + 20
    scene.render.fps = FPS

    bpy.ops.object.camera_add(location=(0, 0, SPACING * side * 1.3))
    cam = bpy.context.object
    cam.rotation_euler = (0, 0, 0)  # 완전히 위에서 내려다보는 각도
    scene.camera = cam

    bpy.ops.object.light_add(type='SUN', location=(3, -3, 10))
    sun = bpy.context.object
    sun.data.energy = 3.0

    fissioned_count = sum(1 for n in nuclei.values() if n["fissioned"])
    print(f"완료! 전체 {len(nuclei)}개 핵 중 {fissioned_count}개 분열, 총 {generation}세대, 길이 {scene.frame_end}프레임")


run_simulation()
