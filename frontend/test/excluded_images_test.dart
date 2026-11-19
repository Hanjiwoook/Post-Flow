import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/post_editor_screen.dart';

void main() {
  group('excludedImageReasons', () {
    test('AI가 뺀 사진 번호와 이유를 짝지어 준다 (11/18 유카이도 실제 결과)', () {
      final post = {
        'excluded_images': [
          {'index': 3, 'reason': '영수증이라 카드번호 등 개인정보가 보여서 뺐어요'},
          {'index': 8, 'reason': '종이 메뉴판이 옆으로 돌아가 있고 글씨가 흐려서'},
        ],
      };
      final reasons = excludedImageReasons(post);
      expect(reasons.keys, [3, 8]);
      expect(reasons[3], startsWith('영수증이라'));
    });

    test('예전 글이나 잘못된 항목은 건너뛴다', () {
      expect(excludedImageReasons({}), isEmpty);
      expect(excludedImageReasons({'excluded_images': [{'reason': '번호 없음'}, 'x']}), isEmpty);
    });

    test('뺀 사진은 섹션에 배치되지 않고 뺀 사진 칸으로 간다', () {
      final blocks = [
        {'type': 'text', 'value': '안녕하세요'},
        {'type': 'image', 'image_indices': [0]},
        {'type': 'text', 'value': '외관'},
      ];
      final layout = buildEditorLayout(blocks, 2); // 사진 1번은 AI가 뺌
      expect(layout.unplacedImages, [1]);
    });
  });
}
