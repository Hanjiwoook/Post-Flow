import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import '../services/draft_store.dart';
import 'memo_logic.dart';

// 서버의 job_id는 플랫폼별 발행 번호를 ", "로 이은 글자다 (예: "12" 또는 "12, 13").
List<int> parseJobIds(dynamic jobId) {
  return '${jobId ?? ''}'
      .split(',')
      .map((s) => int.tryParse(s.trim()))
      .whereType<int>()
      .toList();
}

class PostProvider with ChangeNotifier {
  // 작업 중인 글을 노트북 파일에 자동 저장한다 (앱을 꺼도 [이어서 작업하기]). 테스트에서는 넣지 않거나 임시 폴더를 쓴다.
  PostProvider({DraftStore? store}) : _store = store;
  final DraftStore? _store;
  Timer? _saveTimer;

  List<XFile> _selectedImages = [];
  bool _isLoading = false;
  bool _isRefining = false;
  Map<String, dynamic>? _generatedPost;

  // 검수(6-3): 결과와 고친 흔적은 generatedPost 안에 둔다 ('review', 'revised', 'edited_blocks', 'change_notes').
  // 새 글이나 다른 기록을 불러오면 함께 사라져서, 다른 글의 검수가 섞이지 않는다.
  bool _isReviewing = false;
  bool _isRevising = false;
  // 메모로 부분 고치기: 메모는 generatedPost['memos'], 검수 질문 답은 generatedPost['review_answers']
  final Set<String> _memosInFlight = {};
  int _memoSeq = 0;

  List<XFile> get selectedImages => _selectedImages;
  bool get isLoading => _isLoading;
  bool get isRefining => _isRefining;
  bool get isReviewing => _isReviewing;
  bool get isRevising => _isRevising;
  bool get isAskingMemos => _memosInFlight.isNotEmpty;
  bool isMemoInFlight(String id) => _memosInFlight.contains(id);
  List<Map<String, dynamic>> get memos => _generatedPost == null ? [] : memosOf(_generatedPost!);
  Map<String, dynamic>? get generatedPost => _generatedPost;
  Map<String, dynamic>? get review => _generatedPost?['review'] as Map<String, dynamic>?;
  // 고쳐쓰기는 글 하나에 한 번만 (11/13 결정: 검토 후 고쳐쓰기 최대 1회)
  bool get hasRevised => _generatedPost?['revised'] == true;

  // ---------------- 자동 저장 ----------------

  // 상태가 바뀔 때마다(notifyListeners) 0.5초 뒤 저장한다. 연달아 바뀌면 마지막 것만 저장.
  @override
  void notifyListeners() {
    super.notifyListeners();
    _scheduleSave();
  }

  /// 글 칸에서 직접 고친 것처럼 알림 없이 바뀐 것도 저장하게 한다.
  void markEdited() => _scheduleSave();

  void _scheduleSave() {
    if (_store == null || _generatedPost == null) return; // 글이 없을 때는 앞의 저장본을 지우지 않는다
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 500), saveNow);
  }

  void saveNow() {
    _saveTimer?.cancel();
    final post = _generatedPost;
    if (_store == null || post == null) return;
    try {
      _store.save(post, _selectedImages.map((x) => x.path).toList());
    } catch (e) {
      debugPrint('작업 중인 글 저장 실패: $e');
    }
  }

  /// 저장해 둔 글 (없으면 null). 홈 화면 [이어서 작업하기] 카드에 쓴다.
  Map<String, dynamic>? get savedDraft => _store?.load();

  /// 저장해 둔 글을 연다. 없으면 false.
  bool resumeSavedDraft() {
    final data = _store?.load();
    if (data == null) return false;
    _selectedImages = List<dynamic>.from(data['local_image_paths'] ?? []).map((p) => XFile('$p')).toList();
    _generatedPost = Map<String, dynamic>.from(data['post'] as Map);
    notifyListeners();
    return true;
  }

  void discardSavedDraft() {
    _saveTimer?.cancel();
    _store?.clear();
    super.notifyListeners(); // 지운 직후 다시 저장하지 않도록 저장 예약 없이 알린다
  }

  @override
  void dispose() {
    if (_saveTimer?.isActive ?? false) saveNow();
    super.dispose();
  }

  void setImages(List<XFile> images) {
    _selectedImages = images;
    _generatedPost = null;
    notifyListeners();
  }

  void loadFromHistory(Map<String, dynamic> historyData) {
    _selectedImages = []; // 이력에서 불러올 때는 로컬 XFile은 비움
    _generatedPost = Map<String, dynamic>.from(historyData);
    notifyListeners();
  }

  void clearImages() {
    _selectedImages = [];
    _generatedPost = null;
    notifyListeners();
  }

  void removeImage(int index) {
    if (index >= 0 && index < _selectedImages.length) {
      _selectedImages.removeAt(index);
      notifyListeners();
    }
  }

  // 템플릿 적용 로직 추가
  void applyTemplate(String templateName) {
    if (templateName == "맛집리뷰 템플릿") {
      _generatedPost = _generatedPost ?? {};
      _generatedPost!['template_name'] = templateName;
      _generatedPost!['blocks'] = [
        {"type": "quote", "value": "[인사말] 여러분의 맛집 메이트! 욱스의 욱이, 오늘도 기분 좋게 인사드려요!"},
        {"type": "quote", "value": "[매장 위치 & 정보]\n- 가게명: \n- 주소: \n- 전화번호: \n- 영업시간: \n- 주차: "},
        {"type": "quote", "value": "[외관] 매장 외부 모습과 분위기를 상세히 작성해주세요."},
        {"type": "quote", "value": "[내부] 매장 안 인테리어와 테이블 배치를 설명해주세요."},
        {"type": "quote", "value": "[메뉴판/음식] 주문한 메뉴의 비주얼과 맛을 생생하게 묘사해주세요."},
        {"type": "divider", "value": ""},
        {"type": "quote", "value": "[총평 & 마무리] 전체적인 만족도와 재방문 의사를 작성해주세요."},
      ];
      notifyListeners();
    }
  }

  Future<void> analyzeImages(String templateName, {Map<String, dynamic>? initialFacts}) async {
    if (_selectedImages.isEmpty) return;

    _isLoading = true;
    notifyListeners();

    try {
      final result = await ApiService.analyzeImages(
        _selectedImages, 
        'professional', 
        templateName: templateName,
        initialFacts: initialFacts // 이 부분 추가
      );
      _generatedPost = result;
      _generatedPost!['template_name'] = templateName;

      // 초기 팩트 정보가 있다면 덮어씌우기
      if (initialFacts != null) {
        final existingFacts = Map<String, dynamic>.from(_generatedPost!['facts'] ?? {});
        initialFacts.forEach((key, value) {
          if (value != null && value.toString().isNotEmpty) {
            existingFacts[key] = value;
          }
        });
        _generatedPost!['facts'] = existingFacts;
      }
    } catch (e) {

      print('Error analyzing images: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void updateTitle(String title) {
    if (_generatedPost == null) return;
    _generatedPost!['title'] = title;
  }

  // 특정 블록 삭제 기능 추가
  void removeBlock(int index) {
    if (_generatedPost == null || _generatedPost!['blocks'] == null) return;
    
    final List<dynamic> blocks = List<dynamic>.from(_generatedPost!['blocks']);
    if (index >= 0 && index < blocks.length) {
      blocks.removeAt(index);
      _generatedPost!['blocks'] = blocks;
      _shiftBlockRefs(removedAt: index);
      notifyListeners();
    }
  }

  // 사진을 다른 섹션으로 옮긴다.
  // 편집 화면과 네이버 발행이 모두 image 블록의 image_indices를 보므로, category가 아니라 image_indices를 바꾼다.
  // targetBlockIndex: 옮겨갈 섹션의 글 블록(또는 사진만 있는 섹션이면 그 image 블록) 위치
  void moveImageToSection(int imageIndex, int targetBlockIndex) {
    if (_generatedPost == null || _generatedPost!['blocks'] == null) return;

    final blocks = (_generatedPost!['blocks'] as List)
        .map((b) => Map<String, dynamic>.from(b as Map))
        .toList();
    if (targetBlockIndex < 0 || targetBlockIndex >= blocks.length) return;

    // 1. 원래 있던 image 블록에서 뺀다
    for (final b in blocks) {
      if (b['type'] == 'image') {
        b['image_indices'] = _toIntList(b['image_indices']).where((i) => i != imageIndex).toList();
      }
    }

    // 2. 목표 섹션의 image 블록에 넣는다 (섹션에 사진 블록이 없으면 글 바로 앞에 새로 만든다)
    int imageBlockIndex;
    if (blocks[targetBlockIndex]['type'] == 'image') {
      imageBlockIndex = targetBlockIndex;
    } else if (targetBlockIndex > 0 && blocks[targetBlockIndex - 1]['type'] == 'image') {
      imageBlockIndex = targetBlockIndex - 1;
    } else {
      blocks.insert(targetBlockIndex, {'type': 'image', 'value': null, 'image_indices': <int>[]});
      imageBlockIndex = targetBlockIndex;
      _shiftBlockRefs(insertedAt: targetBlockIndex);
    }
    blocks[imageBlockIndex]['image_indices'] = [
      ..._toIntList(blocks[imageBlockIndex]['image_indices']),
      imageIndex,
    ];

    _generatedPost!['blocks'] = blocks;
    notifyListeners();
  }

  // 블록이 지워지거나 끼워지면 메모와 '고침' 표시(edited_blocks)의 블록 번호를 맞춘다
  void _shiftBlockRefs({int? removedAt, int? insertedAt}) {
    final post = _generatedPost!;
    post['memos'] = shiftMemos(memosOf(post), removedAt: removedAt, insertedAt: insertedAt);
    final edited = <int>[];
    for (final i in _toIntList(post['edited_blocks'])) {
      if (removedAt != null) {
        if (i != removedAt) edited.add(i > removedAt ? i - 1 : i);
      } else {
        edited.add(insertedAt != null && i >= insertedAt ? i + 1 : i);
      }
    }
    post['edited_blocks'] = edited;
  }

  static List<int> _toIntList(dynamic raw) {
    if (raw is! List) return [];
    return raw.whereType<num>().map((n) => n.toInt()).toList();
  }

  void updateContent(String content) {
    if (_generatedPost == null) return;
    _generatedPost!['content'] = content;
  }

  Future<void> updateFact(String key, String value) async {
    if (_generatedPost == null) return;
    
    final facts = Map<String, dynamic>.from(_generatedPost!['facts'] ?? {});
    facts[key] = value;
    _generatedPost!['facts'] = facts;
    
    _isRefining = true;
    notifyListeners();
    
    try {
      final images = List<dynamic>.from(_generatedPost!['images'] ?? []);
      final blocks = List<dynamic>.from(_generatedPost!['blocks'] ?? []);
      
      // 기존 refineContent 대신 patchPost를 사용하여 속도 개선
      final result = await ApiService.patchPost(
        _generatedPost!['title'], 
        blocks, 
        facts, 
        images: images,
      );
      
      _generatedPost!['blocks'] = result['blocks'];
      _generatedPost!['facts'] = result['facts'];
      
    } catch (e) {
      print('Error patching fact: $e');
    } finally {
      _isRefining = false;
      notifyListeners();
    }
  }

  /// 지금 글(편집 화면에서 고친 내용 포함)을 검수 받는다. 실패하면 Exception을 다시 던진다.
  Future<void> requestReview() async {
    final post = _generatedPost;
    if (post == null) return;
    _isReviewing = true;
    notifyListeners();
    try {
      final result = await ApiService.reviewPost(
        post['title'] ?? '',
        List<dynamic>.from(post['blocks'] ?? []),
        Map<String, dynamic>.from(post['facts'] ?? {}),
        images: List<dynamic>.from(post['images'] ?? []),
        writingNotes: List<dynamic>.from(post['writing_notes'] ?? []),
      );
      post['review'] = result;
      // 지적은 해당 블록에 메모로 단다 (다시 검수하면 승인하지 않은 검수 메모는 새 지적으로 바뀐다)
      final prefix = 'r${++_memoSeq}_';
      post['memos'] = mergeReviewMemos(memosOf(post), memosFromReview(result, List<dynamic>.from(post['blocks'] ?? []), idPrefix: prefix));
    } finally {
      _isReviewing = false;
      notifyListeners();
    }
  }

  /// 검수 결과 + 사용자 답변으로 고쳐 쓴다. 실패하면 Exception을 다시 던진다.
  Future<void> requestRevision(List<Map<String, String>> answers) async {
    final post = _generatedPost;
    final currentReview = review;
    if (post == null || currentReview == null || hasRevised) return;
    _isRevising = true;
    notifyListeners();
    try {
      final result = await ApiService.revisePost(
        post['title'] ?? '',
        List<dynamic>.from(post['blocks'] ?? []),
        Map<String, dynamic>.from(post['facts'] ?? {}),
        currentReview,
        answers,
        images: List<dynamic>.from(post['images'] ?? []),
        writingNotes: List<dynamic>.from(post['writing_notes'] ?? []),
      );
      applyRevisionResult(post, result);
    } finally {
      _isRevising = false;
      notifyListeners();
    }
  }

  /// /revise 결과를 글에 반영한다. 서버는 글(text) 블록만 고치고 블록 수·순서는 그대로 돌려준다.
  /// 화면과 나눠 둔 이유: 반영 규칙을 flutter test로 확인하기 위해서다.
  static void applyRevisionResult(Map<String, dynamic> post, Map<String, dynamic> result) {
    final oldBlocks = List<dynamic>.from(post['blocks'] ?? []);
    final newBlocks = List<dynamic>.from(result['blocks'] ?? []);
    // 블록 수가 다르면 사진 위치가 어긋나므로 반영하지 않는다 (서버가 지키는 규칙이지만 한 번 더 막는다)
    if (newBlocks.length != oldBlocks.length) {
      throw Exception('고쳐 쓴 글의 블록 수가 달라서 반영하지 않았습니다 (원래 ${oldBlocks.length}개, 받은 글 ${newBlocks.length}개)');
    }
    post['title'] = result['title'] ?? post['title'];
    post['blocks'] = newBlocks.map((b) => Map<String, dynamic>.from(b as Map)).toList();
    if (result['format_check'] != null) post['format_check'] = result['format_check'];
    post['edited_blocks'] = List<int>.from(result['edited_blocks'] ?? []);
    post['change_notes'] = List<String>.from((result['change_notes'] ?? []).map((n) => '$n'));
    post['revised'] = true;
  }

  // ---------------- 메모로 부분 고치기 ----------------

  void _setMemos(List<Map<String, dynamic>> memos) {
    _generatedPost!['memos'] = memos;
    notifyListeners();
  }

  void _updateMemo(String id, Map<String, dynamic> Function(Map<String, dynamic>) change) {
    if (_generatedPost == null) return;
    _setMemos(memos.map((m) => m['id'] == id ? change(m) : m).toList());
  }

  void addMemo(int blockIndex, String comment, {String quote = ''}) {
    if (_generatedPost == null || comment.trim().isEmpty) return;
    final id = 'u${DateTime.now().microsecondsSinceEpoch}_${++_memoSeq}';
    _setMemos([...memos, newMemo(id: id, blockIndex: blockIndex, comment: comment.trim(), quote: quote)]);
  }

  void editMemo(String id, String comment) => _updateMemo(id, (m) => editMemoComment(m, comment.trim()));
  void toggleMemo(String id, bool checked) => _updateMemo(id, (m) => {...m, 'checked': checked});
  void rejectMemo(String id) => _updateMemo(id, (m) => {...m, 'status': 'rejected', 'checked': false});

  void deleteMemo(String id) {
    if (_generatedPost == null) return;
    _setMemos(memos.where((m) => m['id'] != id).toList());
  }

  /// 승인: 안을 그대로 글에 넣는다. 넣을 수 없으면 Exception (글은 그대로).
  void approveMemoProposal(String id) {
    if (_generatedPost == null) return;
    approveMemo(_generatedPost!, id);
    notifyListeners();
  }

  /// 검수 화면에서 쓴 질문 답. 메모 고치기의 사실 근거로 같이 보내고,
  /// 답을 넣을 자리가 있는 질문은 그 글에 '질문 답' 메모로 단다.
  void setReviewAnswers(List<Map<String, String>> answers) {
    final post = _generatedPost;
    if (post == null) return;
    post['review_answers'] = answers;
    final before = memosOf(post);
    final after = syncAnswerMemos(
      before,
      List<dynamic>.from((review ?? {})['questions'] ?? []),
      {for (final a in answers) a['question'] ?? '': a['answer'] ?? ''},
      List<dynamic>.from(post['blocks'] ?? []),
      // 저장본을 다시 열어도 앞의 메모 번호와 겹치지 않게 시각을 붙인다
      () => 'a${DateTime.now().microsecondsSinceEpoch}_${++_memoSeq}',
    );
    post['memos'] = after;
    // 메모가 바뀌었을 때만 화면을 다시 그린다. 답만 바뀌었으면 저장만 예약한다.
    if (jsonEncode(before) != jsonEncode(after)) {
      notifyListeners();
    } else {
      _scheduleSave();
    }
  }

  /// [AI에게 확인]: 체크한 메모(또는 ids로 고른 메모)를 보내 안을 받는다. 실패하면 Exception.
  Future<void> requestMemoEdits({List<String>? ids}) async {
    final post = _generatedPost;
    if (post == null) return;
    final targets = ids == null ? pendingMemos(memos) : memos.where((m) => ids.contains(m['id'])).toList();
    final sending = targets.where((m) => !_memosInFlight.contains(m['id'])).toList();
    if (sending.isEmpty) return;
    final sendingIds = sending.map((m) => '${m['id']}').toSet();
    _memosInFlight.addAll(sendingIds);
    notifyListeners();
    try {
      final result = await ApiService.memoEdit(
        post['title'] ?? '',
        List<dynamic>.from(post['blocks'] ?? []),
        Map<String, dynamic>.from(post['facts'] ?? {}),
        sending.map(memoPayload).toList(),
        images: List<dynamic>.from(post['images'] ?? []),
        writingNotes: List<dynamic>.from(post['writing_notes'] ?? []),
        answers: List<dynamic>.from(post['review_answers'] ?? []),
      );
      // 기다리는 동안 다른 글을 불러왔으면 버린다
      if (identical(post, _generatedPost)) post['memos'] = attachProposals(memosOf(post), result);
    } finally {
      _memosInFlight.removeAll(sendingIds);
      notifyListeners();
    }
  }

  /// 답장해서 다시 요청: 앞의 안과 답장을 대화로 남기고 그 메모만 다시 보낸다.
  Future<void> replyAndRetry(String id, String reply) async {
    if (_generatedPost == null || reply.trim().isEmpty) return;
    _updateMemo(id, (m) => replyToMemo(m, reply));
    await requestMemoEdits(ids: [id]);
  }

  // 발행 요청을 보내고, 결과 창(6-4)이 상태를 물어볼 발행 번호 목록을 돌려준다 (플랫폼마다 하나).
  Future<List<int>> publishPost(String title, String content, List<String> platforms) async {
    if (_generatedPost == null) return [];

    _isLoading = true;
    notifyListeners();

    try {
      List<String> imagePaths = [];
      if (_generatedPost!['image_paths'] != null) {
        imagePaths = List<String>.from(_generatedPost!['image_paths']);
      }

      final tags = List<String>.from(_generatedPost!['tags'] ?? []);
      final facts = Map<String, dynamic>.from(_generatedPost!['facts'] ?? {});
      final images = List<dynamic>.from(_generatedPost!['images'] ?? []);
      final blocks = List<dynamic>.from(_generatedPost!['blocks'] ?? []);

      final job = await ApiService.publishPost(
        title,
        content,
        imagePaths,
        platforms,
        tags: tags,
        facts: facts,
        images: images,
        blocks: blocks,
      );
      return parseJobIds(job['job_id']);
    } catch (e) {
      print('Error publishing post: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
