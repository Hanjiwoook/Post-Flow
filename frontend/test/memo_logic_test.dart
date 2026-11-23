import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/memo_logic.dart';

List<Map<String, dynamic>> blocks() => [
      {'type': 'text', 'value': '안녕하세요~!\n금요일 점심에'}, // 0
      {'type': 'quote', 'value': '유카이도', 'style': 'default'}, // 1
      {'type': 'map', 'value': '유카이도'}, // 2
      {'type': 'image', 'image_indices': [0]}, // 3
      {'type': 'text', 'value': '가게 앞이에요'}, // 4
      {'type': 'image', 'image_indices': [1]}, // 5
      {'type': 'text', 'value': '라멘이 나왔어요\n맛있었어요'}, // 6
    ];

Map<String, dynamic> post() => {'title': '유카이도 후기', 'blocks': blocks(), 'memos': <Map<String, dynamic>>[]};

Map<String, dynamic> proposed(String id, int at, List<Map<String, dynamic>> edits) =>
    {...newMemo(id: id, blockIndex: at, comment: '고쳐 줘'), 'status': 'proposed', 'proposal': {'edits': edits, 'opinion': 'ok', 'notes': []}};

void main() {
  group('검수 지적 → 메모', () {
    test('붙일 블록', () {
      final b = blocks();
      expect(memoTargetForIssue(-1, b), titleIndex);
      expect(memoTargetForIssue(-2, b), isNull); // 글 전체는 검수 화면에 남긴다
      expect(memoTargetForIssue(4, b), 4);
      expect(memoTargetForIssue(3, b), 4); // 사진 묶음 → 바로 뒤 사진 설명 글
      expect(memoTargetForIssue(1, b), isNull); // 인용구
      expect(memoTargetForIssue(2, b), isNull); // 지도
      expect(memoTargetForIssue(99, b), isNull);
    });

    test('메모로 바꾸고 처음부터 체크', () {
      final review = {
        'issues': [
          {'block_index': 0, 'kind': '사실', 'problem': '날씨 추측', 'suggestion': '빼기', 'quote': '금요일 점심에'},
          {'block_index': -2, 'kind': '말투', 'problem': '~구요 반복', 'suggestion': '섞기'},
          {'block_index': 5, 'kind': '사진', 'problem': '사진 순서', 'suggestion': '', 'quote': '라멘'},
        ]
      };
      final memos = memosFromReview(review, blocks(), idPrefix: 'r1_');
      expect(memos.map((m) => m['block_index']), [0, 6]);
      expect(memos.first['comment'], '날씨 추측');
      expect(memos.first['suggestion'], '빼기');
      expect(memoPayload(memos.first)['comment'], '날씨 추측 → 빼기'); // AI에게는 둘 다
      expect(memoPayload(memos.first)['kind'], '사실');
      expect(memos.first['quote'], '금요일 점심에'); // 검수 메모도 문제 문장을 글 안에 칠한다
      expect(memos.last['quote'], ''); // 사진 묶음 지적을 뒤 글에 옮긴 것은 문장 표시 없음
      expect(memos.last['comment'], '사진 순서');
      expect(memos.every((m) => m['source'] == 'review' && m['checked'] == true && m['status'] == 'draft'), isTrue);
      expect(issuesNotAsMemo(review, blocks()).length, 1);
    });

    test('다시 검수하면 보내지 않은 검수 메모만 바뀌고, 안 받은·끝난 메모와 내 메모는 남는다', () {
      final existing = [
        newMemo(id: 'u1', blockIndex: 4, comment: '내 메모'),
        {...newMemo(id: 'r1_0', blockIndex: 0, comment: 'a', source: 'review'), 'status': 'approved'},
        newMemo(id: 'r1_1', blockIndex: 6, comment: 'b', source: 'review'), // draft → 바뀜
        {...newMemo(id: 'r1_2', blockIndex: 4, comment: 'c', quote: '가게 앞', source: 'review'), 'status': 'proposed'},
        {...newMemo(id: 'r1_3', blockIndex: 6, comment: 'd', source: 'review'), 'status': 'rejected'},
      ];
      final merged = mergeReviewMemos(existing, [
        newMemo(id: 'r2_0', blockIndex: 6, comment: 'e', source: 'review'),
        newMemo(id: 'r2_1', blockIndex: 4, comment: '다른 말', quote: '가게 앞', source: 'review'), // r1_2와 같은 문장 → 중복
        newMemo(id: 'r2_2', blockIndex: 6, comment: 'd', source: 'review'), // r1_3과 같은 문제 → 중복
      ]);
      expect(merged.map((m) => m['id']), ['u1', 'r1_0', 'r1_2', 'r1_3', 'r2_0']);
    });
  });

  test('보낼 메모와 안 붙이기', () {
    final memos = [
      newMemo(id: 'a', blockIndex: 0, comment: 'x'),
      {...newMemo(id: 'b', blockIndex: 4, comment: 'y'), 'checked': false},
      proposed('c', 6, []),
    ];
    expect(pendingMemos(memos).map((m) => m['id']), ['a']);
    final attached = attachProposals(memos, {
      'proposals': [
        {'memo_id': 'a', 'edits': [], 'opinion': '근거가 없어요', 'notes': []},
        {'memo_id': 'zz', 'edits': [], 'opinion': '', 'notes': []},
      ]
    });
    expect(attached[0]['status'], 'proposed');
    expect(attached[0]['proposal']['opinion'], '근거가 없어요');
    expect(attached[1]['status'], 'draft');
  });

  group('승인', () {
    test('안 그대로 넣고 다른 블록은 그대로', () {
      final p = post();
      p['memos'] = [
        proposed('a', 6, [
          {'block_index': 6, 'before': '라멘이 나왔어요\n맛있었어요', 'after': '라멘이 나왔어요\n국물이 진했어요'},
          {'block_index': 4, 'before': '가게 앞이에요', 'after': '가게 앞이에요!'},
        ]),
        proposed('t', titleIndex, [
          {'block_index': titleIndex, 'before': '유카이도 후기', 'after': '항동 라멘 유카이도'},
        ]),
      ];
      approveMemo(p, 'a');
      approveMemo(p, 't');
      final b = p['blocks'] as List;
      expect(b[6]['value'], '라멘이 나왔어요\n국물이 진했어요');
      expect(b[4]['value'], '가게 앞이에요!');
      expect(p['title'], '항동 라멘 유카이도');
      for (final i in [0, 1, 2, 3, 5]) {
        expect(b[i], blocks()[i]);
      }
      expect(p['edited_blocks'], [4, 6]);
      expect(memosOf(p).every((m) => m['status'] == 'approved'), isTrue);
    });

    test('글이 바뀌었으면 넣지 않는다 (겹치는 안, 직접 고친 글)', () {
      final p = post();
      p['memos'] = [
        proposed('a', 6, [{'block_index': 6, 'before': '라멘이 나왔어요\n맛있었어요', 'after': 'A안'}]),
        proposed('b', 4, [{'block_index': 6, 'before': '라멘이 나왔어요\n맛있었어요', 'after': 'B안'}]),
      ];
      approveMemo(p, 'a');
      expect(staleBlocks(p, memosOf(p)[1]), [6]);
      expect(() => approveMemo(p, 'b'), throwsException);
      expect((p['blocks'] as List)[6]['value'], 'A안');
      expect(memosOf(p)[1]['status'], 'proposed');
    });

    test('안을 받지 않은 메모는 승인할 수 없다', () {
      final p = post();
      p['memos'] = [newMemo(id: 'a', blockIndex: 0, comment: 'x')];
      expect(() => approveMemo(p, 'a'), throwsException);
    });
  });

  test('답장하면 앞의 안과 답장이 대화로 남고 다시 보낼 메모가 된다', () {
    final m = replyToMemo(
        proposed('a', 6, [{'block_index': 6, 'before': 'x', 'after': '국물이 진했어요'}]), ' 짜다는 말도 넣어 줘 ');
    expect(m['status'], 'draft');
    expect(m['proposal'], isNull);
    final thread = m['thread'] as List;
    expect(thread[0]['role'], 'ai');
    expect(thread[0]['text'], contains('[6] 국물이 진했어요'));
    expect(thread[0]['text'], contains('의견: ok'));
    expect(thread[1], {'role': 'user', 'text': '짜다는 말도 넣어 줘'});
    expect(memoPayload(m)['thread'], thread);
  });

  test('메모 내용을 고치면 받은 안은 버린다', () {
    final m = editMemoComment(proposed('a', 6, []), '다르게');
    expect([m['comment'], m['status'], m['proposal']], ['다르게', 'draft', null]);
  });

  group('블록 번호 밀림', () {
    test('블록을 지우면 그 블록 메모는 지우고 뒤는 당긴다', () {
      final memos = [
        newMemo(id: 'a', blockIndex: 4, comment: 'x'),
        proposed('b', 6, [{'block_index': 6, 'before': 'x', 'after': 'y'}]),
        newMemo(id: 't', blockIndex: titleIndex, comment: 'z'),
      ];
      final out = shiftMemos(memos, removedAt: 4);
      expect(out.map((m) => m['id']), ['b', 't']);
      expect(out[0]['block_index'], 5);
      expect(out[0]['proposal']['edits'][0]['block_index'], 5);
      expect(out[1]['block_index'], titleIndex);
    });

    test('안이 지운 블록을 고치려 했으면 안을 버린다', () {
      final out = shiftMemos([
        proposed('b', 6, [{'block_index': 4, 'before': 'x', 'after': 'y'}]),
      ], removedAt: 4);
      expect([out[0]['block_index'], out[0]['status'], out[0]['proposal']], [5, 'draft', null]);
    });

    test('끼워 넣으면 그 자리부터 민다', () {
      final out = shiftMemos([newMemo(id: 'a', blockIndex: 4, comment: 'x'), newMemo(id: 'b', blockIndex: 0, comment: 'x')],
          insertedAt: 4);
      expect(out.map((m) => m['block_index']), [5, 0]);
    });
  });

  test('줄 단위 비교', () {
    final d = lineDiff('안녕하세요~!\n햇살이 따뜻하게\n금요일 점심이었어요', '안녕하세요~!\n금요일 점심에\n다녀왔어요');
    expect(d.map((e) => '${e.key}${e.value}'), [' 안녕하세요~!', '-햇살이 따뜻하게', '-금요일 점심이었어요', '+금요일 점심에', '+다녀왔어요']);
    expect(lineDiff('a\nb', 'a\nb').every((e) => e.key == ' '), isTrue);
    expect(lineDiff('a\nb\nc', 'a\nc').map((e) => e.key), [' ', '-', ' ']);
  });

  test('안의 블록 위치 이름', () {
    expect(editPlaceLabel(titleIndex, titleIndex), '제목');
    expect(editPlaceLabel(6, 6), '이 글');
    expect(editPlaceLabel(4, 6), '앞 글');
    expect(editPlaceLabel(9, 6), '뒤 글');
  });
  group('검수 질문 답 → 메모', () {
    final questions = [
      {'question': '라멘 맛은?', 'block_index': 6},
      {'question': '가게 분위기는?', 'block_index': 3}, // 사진 묶음 → 바로 뒤 글(4)
      {'question': '동행은?', 'block_index': -2}, // 자리 없음
      {'question': '예전 검수'}, // block_index 없음
    ];
    var n = 0;
    String id() => 'a${n++}';
    List<Map<String, dynamic>> sync(List<Map<String, dynamic>> memos, Map<String, String> answers) =>
        syncAnswerMemos(memos, questions, answers, blocks(), id);

    test('자리', () {
      expect(answerTarget(questions[0], blocks()), 6);
      expect(answerTarget(questions[1], blocks()), 4);
      expect(answerTarget(questions[2], blocks()), isNull);
      expect(answerTarget(questions[3], blocks()), isNull);
    });

    test('답을 쓰면 자리가 있는 질문만 메모가 생긴다', () {
      final memos = sync([], {'라멘 맛은?': '국물이 진했어요', '동행은?': '친구랑', '예전 검수': '네'});
      expect(memos.length, 1);
      final m = memos.single;
      expect(m['source'], 'answer');
      expect(m['block_index'], 6);
      expect(m['checked'], true);
      expect(m['status'], 'draft');
      expect(m['comment'], '질문: 라멘 맛은?\n답: 국물이 진했어요');
    });

    test('빈 답은 메모를 만들지 않는다', () {
      expect(sync([], {'라멘 맛은?': '   '}), isEmpty);
    });

    test('같은 답이면 그대로, 답을 고치면 내용이 바뀐다', () {
      final first = sync([], {'라멘 맛은?': '진했어요'});
      expect(sync(first, {'라멘 맛은?': '진했어요'}), first);
      final changed = sync(first, {'라멘 맛은?': '짭조름했어요'});
      expect(changed.single['id'], first.single['id']);
      expect(changed.single['comment'], '질문: 라멘 맛은?\n답: 짭조름했어요');
    });

    test('안을 받은 뒤 답을 고치면 안을 버리고 다시 보낼 메모가 된다', () {
      final first = sync([], {'라멘 맛은?': '진했어요'});
      final withProposal = [
        {...first.single, 'status': 'proposed', 'proposal': {'edits': [], 'opinion': 'ok', 'notes': []}}
      ];
      final m = sync(withProposal, {'라멘 맛은?': '짭조름했어요'}).single;
      expect(m['status'], 'draft');
      expect(m['proposal'], isNull);
    });

    test('답을 지우면 반영 전 메모는 빠지고, 승인·거절한 메모와 다른 메모는 남는다', () {
      final first = sync([], {'라멘 맛은?': '진했어요', '가게 분위기는?': '아늑해요'});
      final approved = {...first[1], 'status': 'approved'};
      final mine = newMemo(id: 'u1', blockIndex: 0, comment: '인사 줄여 줘');
      final review = newMemo(id: 'r1', blockIndex: 6, comment: '맛 표현', source: 'review');
      final after = sync([first[0], approved, mine, review], {});
      expect(after.map((m) => m['id']), [approved['id'], 'u1', 'r1']);
    });

    test('승인한 질문에 다시 답하면 새 메모가 생긴다', () {
      final approved = {...sync([], {'라멘 맛은?': '진했어요'}).single, 'status': 'approved'};
      final after = sync([approved], {'라멘 맛은?': '짭조름했어요'});
      expect(after.length, 2);
      expect(after[0], approved);
      expect(after[1]['status'], 'draft');
    });

    test('서버로 보낼 때 source가 answer로 간다', () {
      final m = sync([], {'라멘 맛은?': '진했어요'}).single;
      expect(memoPayload(m)['source'], 'answer');
    });
  });
}
