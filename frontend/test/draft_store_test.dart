import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/memo_logic.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/services/draft_store.dart';
import 'package:frontend/widgets/saved_draft_card.dart';

Map<String, dynamic> post() => {
      'title': '유카이도 후기',
      'blocks': [
        {'type': 'text', 'value': '라멘이 나왔어요'},
      ],
      'images': [],
      'review': {'overall': '좋아요', 'issues': []},
      'memos': [
        newMemo(id: 'u1', blockIndex: 0, comment: '맛 표현'),
        {...newMemo(id: 'u2', blockIndex: 0, comment: 'x'), 'status': 'approved'},
      ],
    };

void main() {
  late Directory tmp;
  late DraftStore store;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('post_flow_draft_test');
    store = DraftStore('${tmp.path}${Platform.pathSeparator}sub${Platform.pathSeparator}current_draft.json');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  group('DraftStore', () {
    test('저장하고 불러오고 지운다 (폴더가 없으면 만든다)', () {
      expect(store.load(), isNull);
      store.save(post(), ['C:/a.jpg']);
      final data = store.load()!;
      expect(data['post']['title'], '유카이도 후기');
      expect(data['local_image_paths'], ['C:/a.jpg']);
      expect(DateTime.tryParse(data['saved_at']), isNotNull);
      expect(File('${store.file.path}.tmp').existsSync(), isFalse);
      store.clear();
      expect(store.load(), isNull);
    });

    test('깨진 파일은 없는 것으로 본다', () {
      store.file.parent.createSync(recursive: true);
      store.file.writeAsStringSync('{"post": {"title": "중간에 끊');
      expect(store.load(), isNull);
    });
  });

  group('자동 저장', () {
    test('상태가 바뀌면 0.5초 뒤 저장되고, 다시 켜서 이어서 열 수 있다', () async {
      final provider = PostProvider(store: store)..loadFromHistory(post());
      provider.addMemo(0, '새 메모');
      expect(store.load(), isNull); // 바로 저장하지 않는다 (연달아 바뀌면 마지막 것만)
      await Future<void>.delayed(const Duration(milliseconds: 700));
      expect(List.from(store.load()!['post']['memos']).length, 3);

      // 글 칸에서 직접 고친 것 (알림 없음) → markEdited로 저장
      (provider.generatedPost!['blocks'] as List)[0]['value'] = '직접 고친 글';
      provider.markEdited();
      await Future<void>.delayed(const Duration(milliseconds: 700));

      // 검수 질문 답 (알림 없이 바뀜) → 저장 예약
      provider.setReviewAnswers([{'question': '국물은?', 'answer': '진했음'}]);
      await Future<void>.delayed(const Duration(milliseconds: 700));

      final reopened = PostProvider(store: store);
      expect(reopened.resumeSavedDraft(), isTrue);
      expect((reopened.generatedPost!['blocks'] as List)[0]['value'], '직접 고친 글');
      expect(reopened.memos.length, 3);
      expect(reopened.review, isNotNull); // 검수 결과
      expect(reopened.generatedPost!['review_answers'], [
        {'question': '국물은?', 'answer': '진했음'}
      ]);
    });

    test('지우면 저장본이 없어지고, 글이 없을 때는 저장본을 지우지 않는다', () async {
      store.save(post(), []);
      final provider = PostProvider(store: store);
      provider.clearImages(); // 글이 없는 상태로 알림
      await Future<void>.delayed(const Duration(milliseconds: 700));
      expect(store.load(), isNotNull);
      provider.discardSavedDraft();
      expect(provider.savedDraft, isNull);
    });

    test('저장소가 없으면 아무것도 하지 않는다', () {
      final provider = PostProvider()..loadFromHistory(post());
      expect(provider.savedDraft, isNull);
      expect(provider.resumeSavedDraft(), isFalse);
    });
  });

  testWidgets('홈 화면 카드: 제목, 저장 시각, 남은 메모, 이어서 작업하기', (tester) async {
    var resumed = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SavedDraftCard(
          draft: {'saved_at': '2026-11-20T21:05:00', 'post': post()},
          onResume: () => resumed = true,
          onDiscard: () {},
        ),
      ),
    ));
    expect(find.text('유카이도 후기'), findsOneWidget);
    expect(find.text('11/20 21:05 저장 · 메모 2개 (남은 것 1개) · 검수 받음'), findsOneWidget);
    await tester.tap(find.text('이어서 작업하기'));
    expect(resumed, isTrue);
  });
}
