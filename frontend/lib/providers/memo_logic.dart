// 메모로 부분 고치기: 메모 목록을 다루는 규칙 (화면·서버와 나눠서 flutter test로 확인한다).
//
// 메모 하나 (Map):
//   id, block_index(제목이면 -1), quote(드래그한 부분), comment, source('user' | 'review'), kind(검수 지적 종류),
//   checked(AI에게 보낼지), status, proposal({edits: [{block_index, before, after}], opinion, notes}), thread([{role, text}])
// status: 'draft'(보낼 메모) → 'proposed'(안 받음) → 'approved' | 'rejected'
//
// 승인은 AI를 다시 부르지 않는다. 안의 before가 지금 글과 같을 때만 그대로 넣는다.
// 다른 안을 승인했거나 직접 고쳐서 글이 달라졌으면 넣지 않는다 (안에 없는 블록이 바뀌거나 덮어쓰는 일을 막는다).

const int titleIndex = -1;

List<Map<String, dynamic>> memosOf(Map<String, dynamic> post) {
  final raw = post['memos'];
  if (raw is! List) return [];
  return raw.map((m) => Map<String, dynamic>.from(m as Map)).toList();
}

Map<String, dynamic> newMemo({
  required String id,
  required int blockIndex,
  required String comment,
  String quote = '',
  String source = 'user',
  String? kind,
}) =>
    {
      'id': id,
      'block_index': blockIndex,
      'quote': quote,
      'comment': comment,
      'source': source,
      if (kind != null) 'kind': kind,
      'checked': true,
      'status': 'draft',
      'proposal': null,
      'thread': <Map<String, String>>[],
    };

/// 지적이 가리키는 블록에서 메모를 달 글 블록을 찾는다. 달 곳이 없으면 null.
///   제목(-1) → 제목, 글 전체(-2) → 없음(검수 화면에 남김), text → 그대로,
///   사진 묶음 → 바로 뒤 사진 설명 글 (사진·지도·구분선만 건너뜀), 인용구·지도 → 없음
int? memoTargetForIssue(int blockIndex, List<dynamic> blocks) {
  if (blockIndex == titleIndex) return titleIndex;
  if (blockIndex < 0 || blockIndex >= blocks.length) return null;
  final type = (blocks[blockIndex] as Map)['type'] ?? 'text';
  if (type == 'text') return blockIndex;
  if (type != 'image') return null;
  for (var i = blockIndex + 1; i < blocks.length; i++) {
    final t = (blocks[i] as Map)['type'] ?? 'text';
    if (t == 'text') return i;
    if (!const {'image', 'map', 'divider', 'sticker'}.contains(t)) return null;
  }
  return null;
}

/// 검수 지적 → 메모. 처음부터 체크해 둔다.
List<Map<String, dynamic>> memosFromReview(Map<String, dynamic> review, List<dynamic> blocks, {String idPrefix = 'r'}) {
  final out = <Map<String, dynamic>>[];
  final issues = List<dynamic>.from(review['issues'] ?? []);
  for (var n = 0; n < issues.length; n++) {
    final it = issues[n] as Map;
    final target = memoTargetForIssue(it['block_index'] is int ? it['block_index'] as int : -2, blocks);
    if (target == null) continue;
    final problem = '${it['problem'] ?? ''}'.trim();
    final suggestion = '${it['suggestion'] ?? ''}'.trim();
    // quote(문제 문장)는 지적이 가리킨 블록 기준이라, 사진 묶음 지적을 뒤 글에 옮겨 단 경우에는 쓰지 않는다
    final quote = target == it['block_index'] ? '${it['quote'] ?? ''}'.trim() : '';
    out.add(newMemo(
      id: '$idPrefix$n',
      blockIndex: target,
      comment: suggestion.isEmpty ? problem : '$problem → $suggestion',
      quote: quote,
      source: 'review',
      kind: '${it['kind'] ?? ''}',
    ));
  }
  return out;
}

/// 다시 검수하면: 승인한 검수 메모와 내 메모는 남기고, 나머지 검수 메모는 새 지적으로 바꾼다.
List<Map<String, dynamic>> mergeReviewMemos(List<Map<String, dynamic>> existing, List<Map<String, dynamic>> fromReview) {
  return [
    ...existing.where((m) => m['source'] != 'review' || m['status'] == 'approved'),
    ...fromReview,
  ];
}

/// 지적이 메모로 옮겨지지 않는 것(글 전체 등)만 남긴다. 검수 화면에 그대로 보여 준다.
List<dynamic> issuesNotAsMemo(Map<String, dynamic> review, List<dynamic> blocks) {
  return List<dynamic>.from(review['issues'] ?? [])
      .where((it) => memoTargetForIssue((it as Map)['block_index'] is int ? it['block_index'] as int : -2, blocks) == null)
      .toList();
}

/// [AI에게 확인]으로 보낼 메모: 체크했고 아직 안을 받지 않은 것
List<Map<String, dynamic>> pendingMemos(List<Map<String, dynamic>> memos) =>
    memos.where((m) => m['checked'] == true && m['status'] == 'draft').toList();

/// 서버(/memo-edit)로 보내는 모양
Map<String, dynamic> memoPayload(Map<String, dynamic> m) => {
      'id': m['id'],
      'block_index': m['block_index'],
      'quote': m['quote'] ?? '',
      'comment': m['comment'] ?? '',
      'source': m['source'] ?? 'user',
      'thread': List<dynamic>.from(m['thread'] ?? []),
    };

/// /memo-edit 결과를 메모에 붙인다. 결과에 없는 메모는 그대로 둔다.
List<Map<String, dynamic>> attachProposals(List<Map<String, dynamic>> memos, Map<String, dynamic> result) {
  final byId = <String, Map<String, dynamic>>{};
  for (final p in List<dynamic>.from(result['proposals'] ?? [])) {
    final map = Map<String, dynamic>.from(p as Map);
    byId['${map['memo_id']}'] = map;
  }
  return memos.map((m) {
    final p = byId['${m['id']}'];
    if (p == null) return m;
    return {...m, 'status': 'proposed', 'proposal': p};
  }).toList();
}

String currentValue(Map<String, dynamic> post, int blockIndex) {
  if (blockIndex == titleIndex) return '${post['title'] ?? ''}';
  final blocks = List<dynamic>.from(post['blocks'] ?? []);
  if (blockIndex < 0 || blockIndex >= blocks.length) return '';
  return '${(blocks[blockIndex] as Map)['value'] ?? ''}';
}

/// 안을 그대로 넣을 수 없는 블록 번호 (지금 글이 안의 '원래 글'과 다르거나 블록이 없음). 비었으면 승인할 수 있다.
List<int> staleBlocks(Map<String, dynamic> post, Map<String, dynamic> memo) {
  final proposal = memo['proposal'];
  if (proposal is! Map) return [];
  final blocks = List<dynamic>.from(post['blocks'] ?? []);
  final stale = <int>[];
  for (final e in List<dynamic>.from(proposal['edits'] ?? [])) {
    final i = (e as Map)['block_index'] as int;
    final exists = i == titleIndex ||
        (i >= 0 && i < blocks.length && ((blocks[i] as Map)['type'] ?? 'text') == 'text');
    if (!exists || currentValue(post, i) != '${e['before'] ?? ''}') stale.add(i);
  }
  return stale;
}

/// 승인: 안을 미리 본 그대로 글에 넣는다. 넣을 수 없으면 아무것도 바꾸지 않고 Exception.
/// 바뀐 블록은 edited_blocks에 더한다 (편집 화면 초록 테두리).
void approveMemo(Map<String, dynamic> post, String memoId) {
  final memos = memosOf(post);
  final idx = memos.indexWhere((m) => m['id'] == memoId);
  if (idx < 0) throw Exception('메모를 찾을 수 없어요');
  final memo = memos[idx];
  if (memo['status'] != 'proposed' || memo['proposal'] is! Map) throw Exception('아직 받은 안이 없어요');
  final stale = staleBlocks(post, memo);
  if (stale.isNotEmpty) {
    throw Exception('글이 그 사이 바뀌어서 이 안을 넣을 수 없어요. 답장해서 다시 요청해 주세요');
  }
  final blocks = List<dynamic>.from(post['blocks'] ?? []).map((b) => Map<String, dynamic>.from(b as Map)).toList();
  final edited = <int>{...List<int>.from(post['edited_blocks'] ?? [])};
  for (final e in List<dynamic>.from((memo['proposal'] as Map)['edits'] ?? [])) {
    final i = (e as Map)['block_index'] as int;
    final after = '${e['after'] ?? ''}';
    if (i == titleIndex) {
      post['title'] = after;
    } else {
      blocks[i]['value'] = after;
      edited.add(i);
    }
  }
  post['blocks'] = blocks;
  post['edited_blocks'] = edited.toList()..sort();
  memos[idx] = {...memo, 'status': 'approved', 'checked': false};
  post['memos'] = memos;
}

/// 안을 받은 메모에 답장: 앞의 안과 답장을 대화에 남기고, 다시 보낼 메모로 되돌린다.
Map<String, dynamic> replyToMemo(Map<String, dynamic> memo, String reply) {
  final p = memo['proposal'];
  final thread = List<dynamic>.from(memo['thread'] ?? []);
  if (p is Map) {
    final edits = List<dynamic>.from(p['edits'] ?? [])
        .map((e) => '[${(e as Map)['block_index'] == titleIndex ? '제목' : e['block_index']}] ${e['after']}')
        .join('\n');
    final opinion = '${p['opinion'] ?? ''}'.trim();
    thread.add({'role': 'ai', 'text': [if (edits.isNotEmpty) '고친 안:\n$edits' else '고친 안 없음', if (opinion.isNotEmpty) '의견: $opinion'].join('\n')});
  }
  thread.add({'role': 'user', 'text': reply.trim()});
  return {...memo, 'thread': thread, 'status': 'draft', 'proposal': null, 'checked': true};
}

/// 메모 내용을 고치면 받은 안은 버리고 다시 보낼 메모가 된다. (승인한 메모는 화면에서 고칠 수 없다)
Map<String, dynamic> editMemoComment(Map<String, dynamic> memo, String comment) =>
    {...memo, 'comment': comment, 'status': 'draft', 'proposal': null, 'checked': true};

/// 블록을 지우거나 끼워 넣어 번호가 밀릴 때 메모 번호를 맞춘다.
///   removedAt: 지운 블록 → 그 블록의 메모는 지우고, 뒤 번호는 1씩 당긴다
///   insertedAt: 끼워 넣은 자리 → 그 자리부터 1씩 민다
/// 받은 안의 번호도 같이 옮긴다. 안이 지운 블록을 고치려 했으면 안을 버리고 다시 보낼 메모로 되돌린다.
List<Map<String, dynamic>> shiftMemos(List<Map<String, dynamic>> memos, {int? removedAt, int? insertedAt}) {
  int? move(int i) {
    if (i == titleIndex) return i;
    if (removedAt != null) {
      if (i == removedAt) return null;
      return i > removedAt ? i - 1 : i;
    }
    if (insertedAt != null && i >= insertedAt) return i + 1;
    return i;
  }

  final out = <Map<String, dynamic>>[];
  for (final m in memos) {
    final at = move(m['block_index'] as int);
    if (at == null) continue;
    var updated = {...m, 'block_index': at};
    final p = m['proposal'];
    if (p is Map && m['status'] != 'approved') {
      final edits = <Map<String, dynamic>>[];
      var broken = false;
      for (final e in List<dynamic>.from(p['edits'] ?? [])) {
        final to = move((e as Map)['block_index'] as int);
        if (to == null) {
          broken = true;
        } else {
          edits.add({...Map<String, dynamic>.from(e), 'block_index': to});
        }
      }
      updated = broken
          ? {...updated, 'proposal': null, 'status': 'draft'}
          : {...updated, 'proposal': {...Map<String, dynamic>.from(p), 'edits': edits}};
    }
    out.add(updated);
  }
  return out;
}

/// 줄 단위 비교 (원래 → 고친 글). op: ' ' 그대로, '-' 지운 줄, '+' 넣은 줄.
/// 바뀐 곳을 한눈에 보이게 하려는 것이고, 실제로 넣는 글은 안의 after 그대로다.
List<MapEntry<String, String>> lineDiff(String before, String after) {
  final a = before.split('\n');
  final b = after.split('\n');
  // 가장 긴 공통 줄 (LCS)
  final lcs = List.generate(a.length + 1, (_) => List.filled(b.length + 1, 0));
  for (var i = a.length - 1; i >= 0; i--) {
    for (var j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] == b[j] ? lcs[i + 1][j + 1] + 1 : (lcs[i + 1][j] >= lcs[i][j + 1] ? lcs[i + 1][j] : lcs[i][j + 1]);
    }
  }
  final out = <MapEntry<String, String>>[];
  var i = 0, j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] == b[j]) {
      out.add(MapEntry(' ', a[i]));
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.add(MapEntry('-', a[i++]));
    } else {
      out.add(MapEntry('+', b[j++]));
    }
  }
  while (i < a.length) {
    out.add(MapEntry('-', a[i++]));
  }
  while (j < b.length) {
    out.add(MapEntry('+', b[j++]));
  }
  return out;
}

/// 안의 블록이 메모 기준으로 어디인지: 제목 / 이 글 / 앞 글 / 뒤 글
String editPlaceLabel(int editIndex, int memoIndex) {
  if (editIndex == titleIndex) return '제목';
  if (editIndex == memoIndex) return '이 글';
  return editIndex < memoIndex ? '앞 글' : '뒤 글';
}
