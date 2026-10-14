"""
핵분열 연쇄반응 3D 시뮬레이션 (Blender Python / bpy)
Nuclear Fission Chain Reaction 3D Simulation for Blender

사용법:
1. Blender 상단의 'Scripting' 탭을 클릭
2. 왼쪽 코드 입력창에 이 파일 내용을 전부 붙여넣기
3. 위에 있는 ▶ (Run Script) 버튼 클릭
4. 아래쪽 타임라인에서 재생(스페이스바)하면 애니메이션이 재생됨

이 스크립트는 현재 씬(Scene)에 있는 모든 오브젝트를 지우고 새로 만듭니다.
작업 중이던 다른 모델이 있다면 미리 저장해두세요.

원리:
- 원자핵(nucleus)들을 3D 공간에 격자 형태로 배치
- 중성자(neutron) 하나가 중앙 핵에 날아가 부딪힘
- 부딪힌 핵은 "핵분열"하며 색이 바뀌고 커졌다 작아짐 (에너지 방출 표현)
- 동시에 새 중성자 2개가 튀어나가 주변의 아직 안 쪼개진 핵으로 날아감
- 이 과정이 반복되며 연쇄반응이 퍼져나감 (k=2인 경우 기하급수적으로 증가)
"""

import bpy
import random
import math
from collections import deque

# ============================================================
# 1. 시뮬레이션 파라미터 (여기 숫자들을 바꿔보면서 실험해보세요!)
# ============================================================

GRID_SIZE = 5          # 핵을 한 변에 몇 개씩 배치할지 (5면 5x5x5 = 125개)
SPACING = 2.5           # 핵과 핵 사이 거리 (Blender 단위)
MULTIPLICATION_K = 2    # 핵분열 하나당 새로 튀어나가는 중성자 수 (증배계수 k)
MAX_GENERATIONS = 6     # 연쇄반응을 몇 세대까지 진행할지 (너무 크면 프레임이 엄청 늘어남)
TRAVEL_SPEED = 0.15     # 중성자가 1프레임에 이동하는 거리 (작을수록 천천히 날아감)
FPS = 24                # 초당 프레임 수

NUCLEUS_RADIUS = 0.5
NEUTRON_RADIUS = 0.15


# ============================================================
# 2. 씬 초기화 (기존 오브젝트 전부 삭제)
# ============================================================
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # 안 쓰는 메시 데이터 정리
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


# ============================================================
# 3. 재질(색) 만들기 헬퍼 함수
# ============================================================
def make_material(name, color_rgba, emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color_rgba
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color_rgba
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


# ============================================================
# 4. 핵(nucleus) 오브젝트 생성
# ============================================================
def create_nucleus(position, index):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=NUCLEUS_RADIUS, location=position)
    obj = bpy.context.object
    obj.name = f"Nucleus_{index}"

    mat = make_material(f"NucleusMat_{index}", (0.1, 0.3, 0.9, 1.0))  # 파란색 = 안정 상태
    obj.data.materials.append(mat)
    return obj


# ============================================================
# 5. 중성자(neutron) 오브젝트 생성
# ============================================================
def create_neutron(position, index):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=NEUTRON_RADIUS, location=position)
    obj = bpy.context.object
    obj.name = f"Neutron_{index}"

    mat = make_material(f"NeutronMat_{index}", (1.0, 1.0, 0.2, 1.0), emission_strength=2.0)  # 노란색 + 발광
    obj.data.materials.append(mat)
    obj.scale = (0, 0, 0)  # 처음엔 안 보이게 (발사되기 전까지 숨김)
    obj.keyframe_insert(data_path="scale", frame=1)
    return obj


# ============================================================
# 6. 핵이 "핵분열"하는 애니메이션 (색 변화 + 커졌다 작아짐)
# ============================================================
def animate_fission(nucleus_obj, frame):
    mat = nucleus_obj.data.materials[0]
    bsdf = mat.node_tree.nodes.get("Principled BSDF")

    # 분열 직전: 원래 크기, 파란색
    nucleus_obj.scale = (1, 1, 1)
    nucleus_obj.keyframe_insert(data_path="scale", frame=frame - 1)
    bsdf.inputs["Base Color"].default_value = (0.1, 0.3, 0.9, 1.0)
    bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame - 1)

    # 분열 순간: 확 커지면서 주황색 (에너지 방출)
    nucleus_obj.scale = (1.8, 1.8, 1.8)
    nucleus_obj.keyframe_insert(data_path="scale", frame=frame)
    bsdf.inputs["Base Color"].default_value = (1.0, 0.4, 0.05, 1.0)
    bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame)

    # 분열 직후: 다시 작아지며 회색(다 쓴 핵, 비활성) 으로 변함
    nucleus_obj.scale = (0.7, 0.7, 0.7)
    nucleus_obj.keyframe_insert(data_path="scale", frame=frame + 8)
    bsdf.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1.0)
    bsdf.inputs["Base Color"].keyframe_insert(data_path="default_value", frame=frame + 8)


# ============================================================
# 7. 중성자가 날아가는 애니메이션
# ============================================================
def animate_neutron_flight(neutron_obj, start_pos, end_pos, start_frame, end_frame):
    neutron_obj.location = start_pos
    neutron_obj.scale = (1, 1, 1)
    neutron_obj.keyframe_insert(data_path="location", frame=start_frame)
    neutron_obj.keyframe_insert(data_path="scale", frame=start_frame)

    neutron_obj.location = end_pos
    neutron_obj.keyframe_insert(data_path="location", frame=end_frame)

    # 도착 후 사라짐 (흡수됨)
    neutron_obj.scale = (0, 0, 0)
    neutron_obj.keyframe_insert(data_path="scale", frame=end_frame + 2)


def distance(p1, p2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))


# ============================================================
# 8. 메인 시뮬레이션
# ============================================================
def run_simulation():
    clear_scene()

    # --- 8-1. 핵들을 격자로 배치 ---
    nuclei = {}  # index -> {"obj": ..., "pos": ..., "fissioned": False}
    half = (GRID_SIZE - 1) / 2
    idx = 0
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            for z in range(GRID_SIZE):
                pos = (
                    (x - half) * SPACING,
                    (y - half) * SPACING,
                    (z - half) * SPACING,
                )
                obj = create_nucleus(pos, idx)
                nuclei[idx] = {"obj": obj, "pos": pos, "fissioned": False}
                idx += 1

    # --- 8-2. 연쇄반응 시작: 정중앙 핵을 첫 분열 지점으로 ---
    center_index = len(nuclei) // 2
    reaction_radius = SPACING * 1.8  # 이 거리 안의 핵만 타격 대상으로 삼음

    neutron_count = [0]
    current_frame = 10  # 처음 몇 프레임은 정지 장면

    # (nucleus_index, arrival_frame) 형태로 처리 대기열 관리
    queue = deque()
    queue.append((center_index, current_frame))
    nuclei[center_index]["fissioned"] = True

    max_frame_used = current_frame
    generation = 0

    while queue and generation < MAX_GENERATIONS:
        next_queue = deque()
        while queue:
            target_index, arrival_frame = queue.popleft()
            nucleus_data = nuclei[target_index]

            # 핵분열 애니메이션 재생
            animate_fission(nucleus_data["obj"], arrival_frame)
            max_frame_used = max(max_frame_used, arrival_frame + 8)

            # 주변의 아직 안 쪼개진 핵들 중 가까운 것들을 찾아서 중성자 발사
            candidates = []
            for other_index, other_data in nuclei.items():
                if other_data["fissioned"]:
                    continue
                d = distance(nucleus_data["pos"], other_data["pos"])
                if d <= reaction_radius:
                    candidates.append((d, other_index))

            candidates.sort(key=lambda c: c[0])
            targets = candidates[:MULTIPLICATION_K]

            for d, other_index in targets:
                nuclei[other_index]["fissioned"] = True  # 예약(타겟팅)

                neutron_count[0] += 1
                neutron_obj = create_neutron(nucleus_data["pos"], neutron_count[0])

                travel_frames = max(3, int(d / TRAVEL_SPEED))
                hit_frame = arrival_frame + travel_frames

                animate_neutron_flight(
                    neutron_obj,
                    nucleus_data["pos"],
                    nuclei[other_index]["pos"],
                    arrival_frame,
                    hit_frame,
                )

                next_queue.append((other_index, hit_frame))
                max_frame_used = max(max_frame_used, hit_frame + 8)

        queue = next_queue
        generation += 1

    # --- 8-3. 씬 길이 / 카메라 / 조명 설정 ---
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = max_frame_used + 20
    scene.render.fps = FPS

    # 카메라
    bpy.ops.object.camera_add(location=(0, -GRID_SIZE * SPACING * 1.8, GRID_SIZE * SPACING * 0.8))
    cam = bpy.context.object
    cam.rotation_euler = (math.radians(65), 0, 0)
    scene.camera = cam

    # 조명
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.object
    sun.data.energy = 3.0

    print(f"시뮬레이션 완료! 총 {len(nuclei)}개 핵 중 {sum(1 for n in nuclei.values() if n['fissioned'])}개가 분열함")
    print(f"총 {generation} 세대 진행, 애니메이션 길이: {scene.frame_end} 프레임")


run_simulation()
