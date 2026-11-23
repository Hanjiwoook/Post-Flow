import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/memo_logic.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/services/draft_store.dart';
import 'package:frontend/screens/home_screen.dart';
import 'package:frontend/widgets/saved_draft_card.dart';
import 'package:provider/provider.dart';

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
  final sep = Platform.pathSeparator;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('post_flow_draft_test');
    store = DraftStore('${tmp.path}${sep}sub${sep}drafts', legacyPath: '${tmp.path}${sep}sub${sep}current_draft.json');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  Future<void> waitSave() => Future<void>.delayed(const Duration(milliseconds: 700));

  group('DraftStore', () {
    test('글마다 따로 저장하고, 불러오고, 지운다 (폴더가 없으면 만든다)', () {
      expect(store.list(), isEmpty);
      store.save('d1', post(), ['C:/a.jpg']);
      store.save('d2', {...post(), 'title': '두 번째 글'}, []);
      expect(store.load('d1')!['post']['title'], '유카이도 후기');
      expect(store.load('d1')!['local_image_paths'], ['C:/a.jpg']);
      expect(store.load('d2')!['post']['title'], '두 번째 글'); // 앞 글을 덮지 않는다
      expect(DateTime.tryParse(store.load('d1')!['saved_at']), isNotNull);
      expect(store.dir.listSync().where((f) => f.path.endsWith('.tmp')), isEmpty);
      store.delete('d1');
      expect(store.load('d1'), isNull);
      expect(store.list().map((d) => d['id']), ['d2']);
    });

    test('목록은 최근에 저장한 것부터, 깨진 파일은 뺀다', () async {
      store.save('old', post(), []);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      store.save('new', post(), []);
      File('${store.dir.path}${sep}broken.json').writeAsStringSync('{"post": {"title": "중간에 끊');
      expect(store.list().map((d) => d['id']), ['new', 'old']);
      expect(store.load('broken'), isNull);
    });

    test('예전 current_draft.json은 처음 한 번 drafts로 옮긴다', () {
      final legacy = store.legacyFile!..parent.createSync(recursive: true);
      legacy.writeAsStringSync(jsonEncode({'saved_at': '2026-11-20T21:05:00', 'local_image_paths': [], 'post': post()}));
      final drafts = store.list();
      expect(drafts.length, 1);
      expect(drafts.single['post']['title'], '유카이도 후기');
      expect(drafts.single['saved_at'], '2026-11-20T21:05:00');
      expect(legacy.existsSync(), isFalse);
      expect(store.list().length, 1); // 다시 옮기지 않는다
    });
  });

  group('자동 저장', () {
    test('상태가 바뀌면 0.5초 뒤 저장되고, 다시 켜서 이어서 열 수 있다', () async {
      final provider = PostProvider(store: store)..loadFromHistory(post());
      provider.addMemo(0, '새 메모');
      expect(store.list(), isEmpty); // 바로 저장하지 않는다 (연달아 바뀌면 마지막 것만)
      await waitSave();
      final id = provider.currentDraftId!;
      expect(List.from(store.load(id)!['post']['memos']).length, 3);

      // 글 칸에서 직접 고친 것 (알림 없음) → markEdited로 저장
      (provider.generatedPost!['blocks'] as List)[0]['value'] = '직접 고친 글';
      provider.markEdited();
      await waitSave();

      // 검수 질문 답 (알림 없이 바뀜) → 저장 예약
      provider.setReviewAnswers([{'question': '국물은?', 'answer': '진했음'}]);
      await waitSave();

      final reopened = PostProvider(store: store);
      expect(reopened.resumeDraft(id), isTrue);
      expect((reopened.generatedPost!['blocks'] as List)[0]['value'], '직접 고친 글');
      expect(reopened.memos.length, 3);
      expect(reopened.review, isNotNull); // 검수 결과
      expect(reopened.generatedPost!['review_answers'], [
        {'question': '국물은?', 'answer': '진했음'}
      ]);
    });

    test('새 글을 써도 앞의 작업 중인 글이 남는다', () async {
      final provider = PostProvider(store: store)..loadFromHistory(post());
      provider.addMemo(0, '첫 글 메모');
      await waitSave();
      final first = provider.currentDraftId!;

      provider.loadFromHistory({...post(), 'title': '두 번째 글'}); // 다른 글을 열고 고친다
      provider.addMemo(0, '둘째 글 메모');
      await waitSave();
      expect(provider.currentDraftId, isNot(first));
      expect(store.list().map((d) => d['post']['title']), ['두 번째 글', '유카이도 후기']);
    });

    test('이력 글은 열어 보기만 하면 저장하지 않고, 다시 열면 작업본(메모 포함)이 열린다', () async {
      final provider = PostProvider(store: store)..loadFromHistory({...post(), 'id': 7});
      await waitSave();
      expect(store.list(), isEmpty); // 보기만 함
      expect(provider.currentDraftId, 'h7');

      provider.addMemo(0, '이력 글 메모');
      await waitSave();
      provider.loadFromHistory({...post(), 'id': 7, 'memos': []}); // 서버의 이력 글 (메모 없음)
      expect(provider.memos.length, 3); // 작업본이 열린다
    });

    test('저장본을 열기만 하면 목록 순서가 바뀌지 않는다', () async {
      store.save('d1', post(), []);
      final savedAt = store.load('d1')!['saved_at'];
      final provider = PostProvider(store: store);
      expect(provider.resumeDraft('d1'), isTrue);
      await waitSave();
      expect(store.load('d1')!['saved_at'], savedAt);
    });

    test('지우면 저장본이 없어지고, 열려 있던 글이면 다시 저장하지 않는다', () async {
      final provider = PostProvider(store: store)..loadFromHistory(post());
      provider.addMemo(0, '메모');
      await waitSave();
      final id = provider.currentDraftId!;
      provider.discardDraft(id);
      provider.addMemo(0, '지운 뒤 메모');
      await waitSave();
      expect(provider.savedDrafts, isEmpty);
    });

    test('글이 없거나 새 사진만 고른 상태는 저장하지 않는다', () async {
      store.save('d1', post(), []);
      final provider = PostProvider(store: store);
      provider.clearImages();
      await waitSave();
      expect(store.list().map((d) => d['id']), ['d1']);
    });

    test('저장소가 없으면 아무것도 하지 않는다', () {
      final provider = PostProvider()..loadFromHistory(post());
      expect(provider.savedDrafts, isEmpty);
      expect(provider.resumeDraft('d1'), isFalse);
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

  test('저장 상태: 저장하면 시각이 남고, 저장하지 못하면 실패로 남는다', () {
    final provider = PostProvider(store: store)..loadFromHistory(post());
    expect(provider.saveState.value, isNull); // 아직 저장 안 함 (열기만 함)
    provider.saveNow();
    expect(provider.saveState.value!.ok, isTrue);

    // 저장 폴더 자리에 파일이 있으면 폴더를 만들 수 없어 실패한다
    final blocker = File('${tmp.path}${Platform.pathSeparator}blocked')..writeAsStringSync('x');
    final broken = PostProvider(store: DraftStore('${blocker.path}${Platform.pathSeparator}drafts'))
      ..loadFromHistory(post());
    broken.saveNow();
    expect(broken.saveState.value!.ok, isFalse);
  });

  testWidgets('편집 화면 저장 표시: 저장 전에는 안 보이고, 저장되면 시각, 실패하면 경고', (tester) async {
    final state = ValueNotifier<DraftSaveState?>(null);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: DraftSaveLabel(state: state))));
    expect(find.textContaining('저장'), findsNothing);

    state.value = DraftSaveState(DateTime(2026, 11, 23, 14, 5));
    await tester.pump();
    expect(find.text('✓ 자동 저장됨 14:05'), findsOneWidget);

    state.value = DraftSaveState(DateTime(2026, 11, 23, 14, 6), error: '디스크 가득 참');
    await tester.pump();
    expect(find.text('⚠ 저장 실패 14:06'), findsOneWidget);
  });

  testWidgets('홈 화면: 작업 중인 글은 최근 5개만 보이고 [더 보기]로 나머지를 펼친다', (tester) async {
    tester.view.physicalSize = const Size(1400, 6000);
    addTearDown(tester.view.resetPhysicalSize);
    for (var i = 0; i < 7; i++) {
      store.save('d$i', {...post(), 'title': '글 $i'}, []);
    }
    final provider = PostProvider(store: store);
    await tester.pumpWidget(ChangeNotifierProvider<PostProvider>.value(
      value: provider,
      child: const MaterialApp(home: HomeScreen()),
    ));
    await tester.pump();
    expect(find.text('✏️ 작업 중인 글 7개'), findsOneWidget);
    expect(find.byType(SavedDraftCard), findsNWidgets(5));
    await tester.tap(find.text('더 보기 (2개 더)'));
    await tester.pump();
    expect(find.byType(SavedDraftCard), findsNWidgets(7));
    expect(find.text('접기'), findsOneWidget);
  });
}
