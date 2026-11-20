import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/screens/review_screen.dart';
import 'package:provider/provider.dart';

final blocks = [
  {'type': 'text', 'value': '안녕하세요~!\n금요일 점심에 혼자'},
  {'type': 'quote', 'value': '유카이도', 'style': 'default'},
  {'type': 'map', 'value': '유카이도'},
  {'type': 'image', 'image_indices': [0, 9]},
  {'type': 'text', 'value': '연동로11길에 있는 케렌시아 건물 1층이에요'},
];

// 11/17 실제 검수 결과(유카이도)를 줄인 것
Map<String, dynamic> realReview() => {
      'overall': '형식과 사실 근거는 탄탄하고 사진 설명도 잘 맞는 초안입니다.',
      'scores': [
        {'criterion': '형식 일치', 'score': 5, 'comment': '틀을 잘 지켰어요'},
        {'criterion': '맛 표현', 'score': 2, 'comment': '차슈 부드러움과 짠맛 말고는 얇아요'},
      ],
      'issues': [
        {'block_index': -1, 'kind': '형식', 'problem': '제목이 키워드 나열식입니다.', 'suggestion': '직접 먹은 경험 중심으로'},
        {'block_index': 4, 'kind': '말투', 'problem': '설명이 깁니다.', 'suggestion': '짧게'},
      ],
      'missing_info': ['면 식감과 굵기', '국물의 맛과 향'],
      'questions': [
        {
          'question': '국물은 어떤 맛이었나요?',
          'reason': '국물 묘사가 짠맛 한 가지뿐입니다.',
          'example_answers': ['진하고 고소한데 약간 느끼했어요', '잡내 없이 깔끔했어요'],
        },
        {'question': '면은 어땠나요?', 'reason': '', 'example_answers': ['꼬들했어요']},
      ],
      'needs_revision': true,
      'usage': {'model': 'claude-sonnet-5-5', 'cost_usd': 0.057},
    };

void main() {
  group('issueLocation', () {
    test('제목·글 전체·블록 종류별로 읽을 수 있는 위치를 만든다', () {
      expect(issueLocation(-1, blocks), '제목');
      expect(issueLocation(-2, blocks), '글 전체');
      expect(issueLocation(0, blocks), '글 · 안녕하세요~! 금요일 점심에 혼자');
      expect(issueLocation(1, blocks), '인용구 · 유카이도');
      expect(issueLocation(2, blocks), '지도');
      expect(issueLocation(3, blocks), '사진 묶음');
      expect(issueLocation(4, blocks), '글 · 연동로11길에 있는 케렌시아 건물…');
      expect(issueLocation(99, blocks), '99번 블록');
    });
  });

  group('collectAnswers', () {
    test('답한 질문만 모은다 (빈 답은 건너뜀)', () {
      final q = realReview()['questions'] as List;
      final answers = collectAnswers(q, {0: ' 잡내 없이 깔끔했어요 ', 1: '   '});
      expect(answers, [
        {'question': '국물은 어떤 맛이었나요?', 'answer': '잡내 없이 깔끔했어요'},
      ]);
    });
  });

  group('applyRevisionResult', () {
    test('제목·블록·형식 검사·고친 블록 번호·바꾼 이유를 반영하고, 한 번 고쳤다고 표시한다', () {
      final post = {'title': '옛 제목', 'blocks': blocks.map((b) => Map<String, dynamic>.from(b)).toList()};
      final newBlocks = blocks.map((b) => Map<String, dynamic>.from(b)).toList();
      newBlocks[4]['value'] = '연동로11길 케렌시아 건물 1층이에요';
      PostProvider.applyRevisionResult(post, {
        'title': '새 제목',
        'blocks': newBlocks,
        'edited_blocks': [4],
        'change_notes': ['[4]: 설명을 짧게 줄임'],
        'format_check': {'passed': true, 'results': []},
      });
      expect(post['title'], '새 제목');
      expect((post['blocks'] as List)[4]['value'], '연동로11길 케렌시아 건물 1층이에요');
      expect((post['blocks'] as List)[3]['image_indices'], [0, 9]); // 사진 블록은 그대로
      expect(post['edited_blocks'], [4]);
      expect(post['change_notes'], ['[4]: 설명을 짧게 줄임']);
      expect(post['revised'], isTrue);
    });

    test('블록 수가 달라지면 사진 위치가 어긋나므로 반영하지 않는다', () {
      final post = {'title': '옛 제목', 'blocks': blocks.map((b) => Map<String, dynamic>.from(b)).toList()};
      expect(
        () => PostProvider.applyRevisionResult(post, {'title': '새 제목', 'blocks': blocks.sublist(0, 3)}),
        throwsException,
      );
      expect(post['title'], '옛 제목');
      expect(post['revised'], isNull);
    });
  });

  Widget screenWith(Map<String, dynamic> post) {
    final provider = PostProvider()..loadFromHistory(post);
    return ChangeNotifierProvider<PostProvider>.value(
      value: provider,
      child: const MaterialApp(home: ReviewScreen()),
    );
  }

  testWidgets('검수 화면: 총평·점수·지적 위치·질문이 보이고, 예시 답을 누르면 답 칸에 들어간다', (tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(screenWith({'title': '제목', 'blocks': blocks, 'review': realReview()}));

    expect(find.textContaining('형식과 사실 근거는 탄탄하고'), findsOneWidget);
    expect(find.text('2/5'), findsOneWidget);
    // 제목·글 지적 2개는 편집 화면 메모로 옮겼다는 안내만 보인다
    expect(find.textContaining('지적 2개는 편집 화면의 해당 글에 주황 메모로'), findsOneWidget);
    expect(find.textContaining('글 전체 지적'), findsNothing);
    expect(find.text('Q1. 국물은 어떤 맛이었나요?'), findsOneWidget);
    expect(find.text('✍️ 반영해서 고쳐쓰기'), findsOneWidget);

    await tester.tap(find.text('잡내 없이 깔끔했어요'));
    await tester.pump();
    expect(find.widgetWithText(TextField, '잡내 없이 깔끔했어요'), findsOneWidget);
  });

  testWidgets('이미 고쳐 쓴 글은 고쳐쓰기 버튼이 잠긴다 (고쳐쓰기는 한 번만)', (tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(screenWith({'title': '제목', 'blocks': blocks, 'review': realReview(), 'revised': true}));

    final button = tester.widget<ElevatedButton>(find.ancestor(
        of: find.text('이미 한 번 고쳐 썼어요 (고쳐쓰기는 한 번만)'), matching: find.byWidgetPredicate((w) => w is ElevatedButton)));
    expect(button.onPressed, isNull);
  });

  testWidgets('글 전체 지적은 검수 화면에 남는다', (tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    addTearDown(tester.view.resetPhysicalSize);
    final review = realReview();
    (review['issues'] as List).add({'block_index': -2, 'kind': '말투', 'problem': '~구요가 반복돼요', 'suggestion': '섞기'});
    await tester.pumpWidget(screenWith({'title': '제목', 'blocks': blocks, 'review': review}));
    expect(find.text('글 전체 지적 1개'), findsOneWidget);
    expect(find.text('~구요가 반복돼요'), findsOneWidget);
    expect(find.text('글 전체'), findsOneWidget);
  });

  testWidgets('쓴 답은 저장되어 메모 고치기에 쓰이고, 화면을 다시 열면 그대로 있다', (tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    addTearDown(tester.view.resetPhysicalSize);
    final provider = PostProvider()..loadFromHistory({'title': '제목', 'blocks': blocks, 'review': realReview()});
    Widget app() => ChangeNotifierProvider<PostProvider>.value(
          value: provider,
          child: const MaterialApp(home: ReviewScreen()),
        );
    await tester.pumpWidget(app());
    await tester.tap(find.text('잡내 없이 깔끔했어요'));
    await tester.pump();
    expect(provider.generatedPost!['review_answers'], [
      {'question': '국물은 어떤 맛이었나요?', 'answer': '잡내 없이 깔끔했어요'},
    ]);

    await tester.pumpWidget(const SizedBox()); // 화면 닫기
    await tester.pumpWidget(app()); // 다시 열기
    expect(find.widgetWithText(TextField, '잡내 없이 깔끔했어요'), findsOneWidget);
  });
}
