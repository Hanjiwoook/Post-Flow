"""
거의 같은 사진(연사) 찾기.

dHash(difference hash)로 사진마다 64비트 지문을 만들고, 지문이 거의 같은 사진끼리 묶는다.
  1. 사진을 흑백 9x8 픽셀로 줄인다 (색과 크기 차이를 없앤다)
  2. 가로로 이웃한 픽셀끼리 밝기를 비교해 64개의 0/1을 만든다
  3. 두 지문에서 다른 비트 수(해밍 거리)가 작으면 거의 같은 사진이다

Pillow만 쓴다 (imagehash 라이브러리는 numpy, scipy가 필요해서 쓰지 않았다).

이 모듈은 "구도까지 거의 같은 사진"만 잡는다. 같은 음식을 다른 각도로 찍은 사진처럼
의미상 비슷한 사진은 글쓰기 AI가 사진을 보고 판단한다. 여기서 찾은 묶음은 그 AI에게 주는 힌트다.
"""
from typing import List

from PIL import Image, ImageFilter, ImageOps, ImageStat

HASH_SIZE = 8
# 이 값 이하로 다르면 거의 같은 사진으로 본다 (64비트 중).
# 2026-11-13 테스트 사진 20장 기준:
#   - 서로 다른 사진 쌍은 가장 가까운 것이 거리 18
#   - 연사를 흉내 낸 사진(3% 이동 + 밝기 8% 변화)은 가장 먼 것이 거리 9
#   - 같은 장면이지만 피사체가 움직인 사진 쌍(젓가락으로 든 차슈)은 거리 28 → 잡지 못한다
SIMILAR_THRESHOLD = 10
SHARPNESS_SIZE = 512


def _prepare(img: Image.Image) -> Image.Image:
    # 휴대폰 사진은 EXIF 회전 정보가 있어서, 먼저 실제 보이는 방향으로 돌린다
    return ImageOps.exif_transpose(img).convert("L")


def dhash(img: Image.Image, hash_size: int = HASH_SIZE) -> int:
    """사진의 dHash 지문 (hash_size*hash_size 비트 정수)."""
    small = _prepare(img).resize((hash_size + 1, hash_size), Image.LANCZOS)
    # getdata()는 Pillow 14에서 없어진다 (12.x부터 경고)
    pixels = list(small.get_flattened_data())
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a: int, b: int) -> int:
    """두 지문에서 다른 비트 수."""
    return bin(a ^ b).count("1")


def sharpness(img: Image.Image) -> float:
    """선명도 점수. 윤곽선이 뚜렷할수록 크다 (흔들리거나 흐린 사진은 작다)."""
    gray = _prepare(img)
    gray.thumbnail((SHARPNESS_SIZE, SHARPNESS_SIZE))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(edges).var[0]


def group_similar(images: List[Image.Image], threshold: int = SIMILAR_THRESHOLD) -> List[List[int]]:
    """
    거의 같은 사진끼리 묶은 목록. 2장 이상인 묶음만 돌려준다.
    각 묶음 안은 선명한 사진이 앞에 온다. 묶음끼리는 첫 사진 번호 순서.
    예: [[16, 15]]  → 사진 15와 16은 연사이고, 16이 더 선명하다

    A~B, B~C가 가까우면 A, B, C를 한 묶음으로 본다 (연사가 여러 장일 때).
    """
    hashes = [dhash(img) for img in images]
    parent = list(range(len(images)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            if hamming(hashes[i], hashes[j]) <= threshold:
                parent[find(j)] = find(i)

    groups = {}
    for i in range(len(images)):
        groups.setdefault(find(i), []).append(i)

    result = []
    for members in sorted(groups.values(), key=min):
        if len(members) >= 2:
            scores = {i: sharpness(images[i]) for i in members}
            result.append(sorted(members, key=lambda i: -scores[i]))
    return result
