import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/memo_logic.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/screens/post_editor_screen.dart';
import 'package:frontend/widgets/memo_widgets.dart';
import 'package:provider/provider.dart';

Map<String, dynamic> post() => {
      'title': '유카이도 후기',
      'blocks': [
        {'type': 'text', 'value': '안녕하세요~!'},
        {'type': 'quote', 'value': '유카이도', 'style': 'default'},
        {'type': 'text', 'value': '라멘이 나왔어요'},
      ],
      'images': [],
      'memos': [
        newMemo(id: 'u1', blockIndex: 2, comment: '맛 표현 살려 줘', quote: '나왔어요'),
        newMemo(id: 'r1', blockIndex: 0, comment: '날씨 추측 → 빼기', source: 'review', kind: '사실'),
        newMemo(id: 't1', blockIndex: titleIndex, comment: '항동 라멘 넣어 줘'),
      ],
    };

void main() {
  Future<PostProvider> pumpEditor(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    addTearDown(tester.view.resetPhysicalSize);
    final provider = PostProvider()..loadFromHistory(post());
    await tester.pumpWidget(ChangeNotifierProvider<PostProvider>.value(
      value: provider,
      child: const MaterialApp(home: PostEditorScreen()),
    ));
    return provider;
  }

  testWidgets('메모는 단 블록 아래에 보이고, 내 메모와 검수 지적이 구분된다', (tester) async {
    await pumpEditor(tester);
    expect(find.text('맛 표현 살려 줘'), findsOneWidget);
    expect(find.text('“나왔어요”'), findsOneWidget);
    expect(find.text('항동 라멘 넣어 줘'), findsOneWidget);
    expect(find.text('내 메모'), findsNWidgets(2));
    expect(find.text('검수 지적 · 사실'), findsOneWidget);
    // 인용구 카드에는 메모 버튼이 없다: 제목 + 글 2개 = 3개
    expect(find.byIcon(Icons.sticky_note_2_outlined), findsNWidgets(3));
  });

  testWidgets('체크 해제·지우기·메모 버튼으로 새 메모', (tester) async {
    final provider = await pumpEditor(tester);

    await tester.tap(find.byType(Checkbox).first); // 제목 메모 (화면 맨 위)
    await tester.pump();
    expect(provider.memos.firstWhere((m) => m['id'] == 't1')['checked'], isFalse);

    await tester.tap(find.descendant(of: find.byKey(const ValueKey('r1')), matching: find.byIcon(Icons.close)));
    await tester.pump();
    expect(provider.memos.map((m) => m['id']), isNot(contains('r1')));

    await tester.tap(find.byIcon(Icons.sticky_note_2_outlined).last); // 마지막 글 블록(2번)
    await tester.pumpAndSettle();
    await tester.enterText(find.descendant(of: find.byType(AlertDialog), matching: find.byType(TextField)), '이건 빼도 돼');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    final added = provider.memos.last;
    expect([added['block_index'], added['comment'], added['source'], added['checked']], [2, '이건 빼도 돼', 'user', true]);
  });

  testWidgets('메모 고치기', (tester) async {
    final provider = await pumpEditor(tester);
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('u1')), matching: find.byIcon(Icons.edit_outlined)));
    await tester.pumpAndSettle();
    await tester.enterText(find.descendant(of: find.byType(AlertDialog), matching: find.byType(TextField)), '짧게');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(provider.memos.firstWhere((m) => m['id'] == 'u1')['comment'], '짧게');
  });

  test('메모 색과 이름', () {
    expect(memoColor({'source': 'review'}), Colors.orange);
    expect(memoColor({'source': 'user'}), Colors.blue);
    expect(memoLabel({'source': 'review', 'kind': ''}), '검수 지적');
  });
}
