import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/screens/post_editor_screen.dart';

void main() {
  group('buildEditorLayout', () {
    test('사진 분류명과 섹션 제목이 달라도 image_indices대로 사진이 배치된다', () {
      // 실제 사례: 사진 분석은 "FOOD_ITEM:갈매기살", 글은 "[음식:갈매기살 & 쟁반국수]"로 이름이 달랐다
      final blocks = [
        {'type': 'text', 'value': '[인사말] 안녕하세요'},
        {'type': 'image', 'image_indices': [0, 1]},
        {'type': 'text', 'value': '[음식:갈매기살 & 쟁반국수] 맛있어요'},
      ];
      final layout = buildEditorLayout(blocks, 2);

      expect(layout.sections.map((s) => s.title), ['인사말', '음식:갈매기살 & 쟁반국수']);
      expect(layout.sections[1].imageIndices, [0, 1]);
      expect(layout.unplacedImages, isEmpty);
    });

    test('범위를 벗어나거나 중복된 번호는 무시하고, 빠진 사진은 배치 안 된 사진으로 모은다', () {
      final blocks = [
        {'type': 'image', 'image_indices': [0, 7, -1]}, // 7, -1은 없는 사진
        {'type': 'text', 'value': '[외관] 외관'},
        {'type': 'image', 'image_indices': [0, 1]}, // 0은 이미 위에서 사용
        {'type': 'text', 'value': '[내부] 내부'},
      ];
      final layout = buildEditorLayout(blocks, 3);

      expect(layout.sections[0].imageIndices, [0]);
      expect(layout.sections[1].imageIndices, [1]);
      expect(layout.unplacedImages, [2]);
    });

    test('글 없이 연달아 오는 사진 블록은 사진만 있는 섹션이 된다', () {
      final blocks = [
        {'type': 'image', 'image_indices': [0]},
        {'type': 'image', 'image_indices': [1]},
        {'type': 'text', 'value': '[메뉴판] 메뉴'},
      ];
      final layout = buildEditorLayout(blocks, 2);

      expect(layout.sections.map((s) => s.title), ['사진', '메뉴판']);
      expect(layout.sections[0].imageBlockIndex, 0);
      expect(layout.sections[1].imageIndices, [1]);
    });
  });

  group('PostProvider.moveImageToSection', () {
    test('사진을 다른 섹션의 사진 블록으로 옮긴다', () {
      final provider = PostProvider();
      provider.loadFromHistory({
        'blocks': [
          {'type': 'image', 'image_indices': [0, 1]},
          {'type': 'text', 'value': '[외관] 외관'},
          {'type': 'image', 'image_indices': [2]},
          {'type': 'text', 'value': '[내부] 내부'},
        ],
      });

      provider.moveImageToSection(1, 3); // 1번 사진 -> [내부]

      final blocks = provider.generatedPost!['blocks'] as List;
      expect(blocks[0]['image_indices'], [0]);
      expect(blocks[2]['image_indices'], [2, 1]);
    });

    test('사진 블록이 없는 섹션으로 옮기면 글 앞에 사진 블록을 새로 만든다', () {
      final provider = PostProvider();
      provider.loadFromHistory({
        'blocks': [
          {'type': 'text', 'value': '[인사말] 안녕'},
          {'type': 'text', 'value': '[총평 & 마무리] 끝'},
        ],
      });

      provider.moveImageToSection(0, 1); // 배치 안 된 0번 사진 -> [총평]

      final blocks = provider.generatedPost!['blocks'] as List;
      expect(blocks.length, 3);
      expect(blocks[1]['type'], 'image');
      expect(blocks[1]['image_indices'], [0]);
      expect(blocks[2]['value'], '[총평 & 마무리] 끝');
    });
  });
}
