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
        newMemo(id: 'r1', blockIndex: 0, comment: '날씨 추측', suggestion: '날씨 문장은 빼기', source: 'review', kind: '사실'),
        newMemo(id: 't1', blockIndex: titleIndex, comment: '항동 라멘 넣어 줘'),
      ],
    };

void main() {
  Future<PostProvider> pumpEditor(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1200, 9000);
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
    expect(find.textContaining('메모를 다 적었으면 위의 [AI에게 확인]을 눌러 주세요'), findsOneWidget);
    expect(find.textContaining('지금 AI에게 보낼 메모: 3개'), findsOneWidget);
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

  testWidgets('섹션 삭제 창은 사진이 남는다고 안내하고, 지우면 그 글의 메모도 지워진다', (tester) async {
    final provider = await pumpEditor(tester);
    await tester.tap(find.byIcon(Icons.delete_outline).last); // 마지막 글(2번)
    await tester.pumpAndSettle();
    expect(find.textContaining("사진은 지워지지 않고 아래 '글에서 뺀 사진'으로 옮겨져요"), findsOneWidget);
    expect(find.textContaining('글과 이미지가 모두 제거됩니다'), findsNothing);
    await tester.tap(find.text('삭제'));
    await tester.pumpAndSettle();
    expect(provider.memos.map((m) => m['id']), isNot(contains('u1')));
  });

  testWidgets('검수 메모의 고칠 방향은 접혀 있다가 누르면 펼쳐진다', (tester) async {
    await pumpEditor(tester);
    expect(find.text('날씨 추측'), findsOneWidget);
    expect(find.text('→ 날씨 문장은 빼기'), findsNothing);
    await tester.tap(find.text('고칠 방향 보기'));
    await tester.pump();
    expect(find.text('→ 날씨 문장은 빼기'), findsOneWidget);
    expect(find.text('고칠 방향 접기'), findsOneWidget);
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

  group('받은 안', () {
    Future<PostProvider> pumpWithProposal(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 9000);
      addTearDown(tester.view.resetPhysicalSize);
      final data = post();
      data['memos'] = [
        {
          ...newMemo(id: 'u1', blockIndex: 2, comment: '맛 표현 살려 줘'),
          'status': 'proposed',
          'proposal': {
            'edits': [
              {'block_index': 0, 'before': '안녕하세요~!', 'after': '안녕하세요~! 오늘은 라멘이에요'},
              {'block_index': 2, 'before': '라멘이 나왔어요', 'after': '라멘이 나왔어요\n국물이 진했어요'},
            ],
            'opinion': '앞 문장도 같이 다듬었어요',
            'notes': ['범위 밖 블록 5의 수정을 버렸어요'],
          },
        },
        {
          ...newMemo(id: 't1', blockIndex: titleIndex, comment: '항동 라멘'),
          'status': 'proposed',
          'proposal': {
            'edits': [{'block_index': titleIndex, 'before': '유카이도 후기', 'after': '항동 라멘 유카이도'}],
            'opinion': '',
            'notes': [],
          },
        },
      ];
      final provider = PostProvider()..loadFromHistory(data);
      await tester.pumpWidget(ChangeNotifierProvider<PostProvider>.value(
        value: provider,
        child: const MaterialApp(home: PostEditorScreen()),
      ));
      return provider;
    }

    Finder inMemo(String id, Finder f) => find.descendant(of: find.byKey(ValueKey(id)), matching: f);

    testWidgets('원래 → 고친 글, 의견, 코드 검증 메모가 보인다', (tester) async {
      await pumpWithProposal(tester);
      expect(inMemo('u1', find.text('앞 글')), findsOneWidget);
      expect(inMemo('u1', find.text('이 글')), findsOneWidget);
      expect(inMemo('u1', find.text('− 라멘이 나왔어요')), findsNothing); // 그대로인 줄은 지운 줄이 아니다
      expect(inMemo('u1', find.text('+ 국물이 진했어요')), findsOneWidget);
      expect(inMemo('u1', find.text('− 안녕하세요~!')), findsOneWidget);
      expect(inMemo('u1', find.text('💬 앞 문장도 같이 다듬었어요')), findsOneWidget);
      expect(inMemo('u1', find.text('(코드 검증) 범위 밖 블록 5의 수정을 버렸어요')), findsOneWidget);
    });

    testWidgets('승인하면 미리 본 그대로 글과 제목에 들어간다', (tester) async {
      final provider = await pumpWithProposal(tester);
      await tester.tap(inMemo('u1', find.text('승인')));
      await tester.pump();
      final blocks = provider.generatedPost!['blocks'] as List;
      expect(blocks[0]['value'], '안녕하세요~! 오늘은 라멘이에요');
      expect(blocks[2]['value'], '라멘이 나왔어요\n국물이 진했어요');
      expect(blocks[1]['value'], '유카이도'); // 인용구는 그대로
      expect(find.text('끝난 메모 1개 보기'), findsOneWidget);

      await tester.tap(inMemo('t1', find.text('승인')));
      await tester.pump();
      expect(provider.generatedPost!['title'], '항동 라멘 유카이도');
      expect(find.widgetWithText(TextField, '항동 라멘 유카이도'), findsOneWidget); // 제목 칸도 바뀜
    });

    testWidgets('제목 칸을 직접 고쳤으면 제목 안은 승인할 수 없다', (tester) async {
      final provider = await pumpWithProposal(tester);
      await tester.enterText(find.widgetWithText(TextField, '유카이도 후기'), '내가 고친 제목');
      await tester.tap(inMemo('t1', find.text('승인')));
      await tester.pump();
      expect(provider.generatedPost!['title'], '내가 고친 제목');
      expect(find.textContaining('넣을 수 없어요'), findsWidgets);
    });

    testWidgets('거절하면 글은 그대로이고, 끝난 메모는 접혀 있다가 펼칠 수 있다', (tester) async {
      final provider = await pumpWithProposal(tester);
      await tester.tap(inMemo('u1', find.text('거절')));
      await tester.pump();
      expect((provider.generatedPost!['blocks'] as List)[2]['value'], '라멘이 나왔어요');
      expect(find.byKey(const ValueKey('u1')), findsNothing); // 끝난 메모는 접힘
      await tester.tap(find.text('끝난 메모 1개 보기'));
      await tester.pump();
      expect(find.text('거절함'), findsOneWidget);
      await tester.tap(find.text('끝난 메모 접기'));
      await tester.pump();
      expect(find.text('거절함'), findsNothing);
    });
  });

  test('칠할 구간: 첫 위치만, 겹치면 앞의 것', () {
    final r = highlightRanges('라멘이 나왔어요 라멘이', [
      const MapEntry('라멘이', Colors.blue),
      const MapEntry('이 나와', Colors.orange), // 앞 구간과 겹침
      const MapEntry('없는 글', Colors.blue),
      const MapEntry('', Colors.blue),
    ]);
    expect(r.map((e) => [e.start, e.end]), [[0, 3]]);
  });

  group('넓은 화면', () {
    Future<PostProvider> pumpWide(WidgetTester tester, Map<String, dynamic> data) async {
      tester.view.physicalSize = const Size(1600, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final provider = PostProvider()..loadFromHistory(data);
      await tester.pumpWidget(ChangeNotifierProvider<PostProvider>.value(
        value: provider,
        child: const MaterialApp(home: PostEditorScreen()),
      ));
      return provider;
    }

    testWidgets('메모는 글 오른쪽 옆에 있고, 드래그한 부분은 글 안에 칠해진다', (tester) async {
      await pumpWide(tester, post());
      final text = tester.getRect(find.widgetWithText(TextField, '라멘이 나왔어요'));
      final memo = tester.getRect(find.byKey(const ValueKey('u1')));
      expect(memo.left, greaterThanOrEqualTo(text.right)); // 글 옆
      expect(memo.top, lessThan(text.bottom)); // 글 아래가 아니라 같은 높이
      expect(memo.left - text.left, lessThan(600)); // 글 칸 바로 옆 (화면 오른쪽 끝이 아님)
      // 화면(1600)이 최대 폭(1240)보다 넓으면 내용이 가운데로 모인다
      expect(text.left, greaterThan((1600 - 1240) / 2 - 1));

      final field = tester.widget<TextField>(find.widgetWithText(TextField, '라멘이 나왔어요'));
      final span = field.controller!.buildTextSpan(
          context: tester.element(find.widgetWithText(TextField, '라멘이 나왔어요')), withComposing: false);
      final parts = span.children!.cast<TextSpan>();
      expect(parts.map((p) => p.text), ['라멘이 ', '나왔어요']);
      expect(parts[1].style?.backgroundColor, isNotNull);
    });

    testWidgets('승인하면 글 칸도 고친 글로 바뀐다', (tester) async {
      final data = post();
      data['memos'] = [
        {
          ...newMemo(id: 'u1', blockIndex: 2, comment: 'x', quote: '나왔어요'),
          'status': 'proposed',
          'proposal': {
            'edits': [{'block_index': 2, 'before': '라멘이 나왔어요', 'after': '라멘이 드디어 나왔어요'}],
            'opinion': '',
            'notes': [],
          },
        },
      ];
      await pumpWide(tester, data);
      await tester.tap(find.text('승인'));
      await tester.pump();
      expect(find.widgetWithText(TextField, '라멘이 드디어 나왔어요'), findsOneWidget);
    });
  });
}
