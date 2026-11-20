import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/memo_logic.dart' show titleIndex;
import '../providers/post_provider.dart';
import '../services/api_service.dart';
import '../widgets/publish_result_dialog.dart';
import '../widgets/memo_widgets.dart';
import '../widgets/writing_report_card.dart';
import 'review_screen.dart';

/// 편집 화면의 섹션 카드 하나 (사진 + 글)
class EditorSection {
  final String title;
  final String text;
  final int? textBlockIndex; // 글 블록 위치 (사진만 있는 섹션이면 null)
  final int? imageBlockIndex; // 이 섹션 사진이 들어있는 image 블록 위치
  final List<int> imageIndices; // 원본 사진 리스트에서의 번호

  const EditorSection({
    required this.title,
    required this.text,
    required this.textBlockIndex,
    required this.imageBlockIndex,
    required this.imageIndices,
  });

  /// 사진 이동 시 목표로 쓸 블록 위치
  int get targetBlockIndex => textBlockIndex ?? imageBlockIndex!;
}

/// 섹션 목록 + 어느 섹션에도 들어가지 않은 사진
class EditorLayout {
  final List<EditorSection> sections;
  final List<int> unplacedImages;
  const EditorLayout(this.sections, this.unplacedImages);
}

/// AI가 글에서 뺀 사진의 이유 (/analyze의 excluded_images). 사진 번호 → 이유.
/// 이유가 없는 사진(예: 편집 중 섹션을 지워서 빠진 사진)은 들어 있지 않다.
Map<int, String> excludedImageReasons(Map post) {
  final reasons = <int, String>{};
  for (final e in (post['excluded_images'] as List? ?? [])) {
    if (e is Map && e['index'] is int) reasons[e['index'] as int] = '${e['reason'] ?? ''}';
  }
  return reasons;
}

/// 블록 순서대로 섹션을 만든다.
/// 네이버 발행(naver_v2.py)과 똑같이 image 블록의 image_indices를 기준으로 사진을 배치하므로,
/// 화면에 보이는 사진 위치 = 실제 발행되는 사진 위치가 된다.
/// AI 프롬프트가 "사진 블록 먼저, 설명 글 다음" 순서를 요구하므로, image 블록은 바로 뒤의 글 블록과 한 섹션으로 묶는다.
EditorLayout buildEditorLayout(List<dynamic> blocks, int imageCount) {
  final sections = <EditorSection>[];
  final placed = <int>{};
  int? pendingImageBlock;
  List<int> pendingImages = [];

  void flushImageOnly() {
    if (pendingImageBlock != null && pendingImages.isNotEmpty) {
      sections.add(EditorSection(
        title: '사진',
        text: '',
        textBlockIndex: null,
        imageBlockIndex: pendingImageBlock,
        imageIndices: pendingImages,
      ));
    }
    pendingImageBlock = null;
    pendingImages = [];
  }

  for (int i = 0; i < blocks.length; i++) {
    final block = blocks[i] as Map;
    final type = block['type'] ?? 'text';

    if (type == 'image') {
      flushImageOnly(); // 사진 블록이 연달아 오면 앞의 것은 사진만 있는 섹션으로
      pendingImageBlock = i;
      final raw = block['image_indices'];
      final indices = <int>[
        if (raw is List) ...raw.whereType<num>().map((n) => n.toInt()),
        if (block['image_index'] is num) (block['image_index'] as num).toInt(), // 하위 호환
      ];
      // 범위를 벗어나거나 이미 다른 섹션에 쓰인 번호는 무시 (AI 응답 검증)
      for (final idx in indices) {
        if (idx >= 0 && idx < imageCount && placed.add(idx)) pendingImages.add(idx);
      }
    } else if (type == 'text' || type == 'quote') {
      final value = block['value']?.toString() ?? '';
      if (value.isEmpty) continue;
      sections.add(EditorSection(
        title: _sectionTitleOf(value),
        text: value,
        textBlockIndex: i,
        imageBlockIndex: pendingImageBlock,
        imageIndices: pendingImages,
      ));
      pendingImageBlock = null;
      pendingImages = [];
    }
    // divider, map 등은 화면 카드로 만들지 않음
  }
  flushImageOnly();

  final unplaced = [for (int i = 0; i < imageCount; i++) if (!placed.contains(i)) i];
  return EditorLayout(sections, unplaced);
}

/// "[외관] 매장 외부는..." -> "외관"
String _sectionTitleOf(String value) {
  final match = RegExp(r'^\s*\[([^\]]+)\]').firstMatch(value);
  return match?.group(1)?.trim() ?? '본문';
}

class PostEditorScreen extends StatefulWidget {
  const PostEditorScreen({super.key});

  @override
  State<PostEditorScreen> createState() => _PostEditorScreenState();
}

class _PostEditorScreenState extends State<PostEditorScreen> {
  late TextEditingController _titleController;
  final List<String> _selectedPlatforms = ['naver']; 

  @override
  void initState() {
    super.initState();
    final provider = Provider.of<PostProvider>(context, listen: false);
    _titleController = TextEditingController(text: provider.generatedPost?['title'] ?? '');
  }

  @override
  void dispose() {
    _titleController.dispose();
    super.dispose();
  }

  Widget _buildFactRow(String label, String value) {
    if (value.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.black87)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 13, color: Colors.indigo)),
          ),
        ],
      ),
    );
  }

  Future<bool?> _showMoveMenu(BuildContext context, int imageIndex, List<EditorSection> sections, PostProvider provider) {
    return showModalBottomSheet<bool>(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) {
        return Container(
          padding: const EdgeInsets.symmetric(vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text("📸 사진 이동하기", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 10),
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: sections.map((section) {
                    return ListTile(
                      leading: const Icon(Icons.move_to_inbox, size: 20),
                      title: Text(section.title),
                      onTap: () {
                        provider.moveImageToSection(imageIndex, section.targetBlockIndex);
                        Navigator.pop(context, true);
                      },
                    );
                  }).toList(),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  /// 사진 번호 -> 파일 경로. 방금 고른 사진이 있으면 그것을, 이력에서 불러왔으면 서버 저장 경로를 쓴다.
  String? _imagePath(PostProvider provider, int index) {
    if (index < provider.selectedImages.length) return provider.selectedImages[index].path;
    final images = provider.generatedPost?['images'];
    if (images is List && index < images.length) return images[index]['path']?.toString();
    return null;
  }

  void _showImageDetail(BuildContext context, String path, int realIndex, List<EditorSection> sections, PostProvider provider) {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Stack(
                alignment: Alignment.topRight,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        maxHeight: MediaQuery.of(context).size.height * 0.7, // 최대 높이 제한
                      ),
                      child: InteractiveViewer(
                        minScale: 1.0,
                        maxScale: 4.0,
                        child: Image.file(File(path), fit: BoxFit.contain),
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: IconButton(
                      icon: const Icon(Icons.close, color: Colors.white, size: 28, shadows: [Shadow(blurRadius: 8, color: Colors.black)]),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () async {
                final bool? moved = await _showMoveMenu(context, realIndex, sections, provider); // 이동 메뉴 팝업 띄우기
                if (moved == true && context.mounted) {
                  Navigator.pop(context); // 이동 완료된 경우에만 이미지 팝업 닫기
                }
              },
              icon: const Icon(Icons.move_to_inbox),
              label: const Text("다른 섹션으로 사진 이동", style: TextStyle(fontWeight: FontWeight.bold)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.white, 
                foregroundColor: Colors.indigo, 
                elevation: 4,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12)
              ),
            )
          ],
        ),
      ),
    );
  }
  Widget _buildInsightChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: color.withOpacity(0.2), borderRadius: BorderRadius.circular(8), border: Border.all(color: color.withOpacity(0.5))),
      child: Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
    );
  }

  // 통합 섹션 카드 빌더
  // [unplaced] true면 "배치 안 된 사진" 카드 (글·삭제 버튼 없음)
  Widget _buildSectionItem(String sectionTitle, String sectionText, int? textBlockIndex, int? imageBlockIndex, List<int> sectionImages, List<EditorSection> allSections, PostProvider provider, {bool unplaced = false}) {
    if (sectionText.isEmpty && sectionImages.isEmpty) return const SizedBox.shrink();

    // 고쳐쓰기(6-3)에서 바뀐 글은 초록 테두리로 표시한다
    final edited = List<dynamic>.from(provider.generatedPost?['edited_blocks'] ?? []);
    final wasEdited = textBlockIndex != null && edited.contains(textBlockIndex);
    // 메모는 글(text) 블록에만 단다. 인용구(가게 이름·정보)는 고치지 않는다
    final blocks = List<dynamic>.from(provider.generatedPost?['blocks'] ?? []);
    final memoable = !unplaced && textBlockIndex != null && textBlockIndex < blocks.length &&
        ((blocks[textBlockIndex] as Map)['type'] ?? 'text') == 'text';

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: wasEdited ? const BorderSide(color: Colors.green, width: 2) : BorderSide.none,
      ),
      elevation: 0,
      color: Colors.grey[50],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(color: Colors.indigo[50], borderRadius: const BorderRadius.vertical(top: Radius.circular(12))),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Text(sectionTitle, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo, fontSize: 13)),
                    if (wasEdited)
                      const Padding(
                        padding: EdgeInsets.only(left: 8),
                        child: Text("✍️ 고침", style: TextStyle(fontSize: 11, color: Colors.green, fontWeight: FontWeight.bold)),
                      ),
                    if (sectionImages.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(left: 8),
                        child: Text("${sectionImages.length}장의 사진", style: const TextStyle(fontSize: 11, color: Colors.indigoAccent)),
                      ),
                  ],
                ),
                if (memoable) IconButton(
                  tooltip: '메모 남기기 (글을 드래그한 뒤 우클릭해도 돼요)',
                  icon: const Icon(Icons.sticky_note_2_outlined, size: 18, color: Colors.blue),
                  visualDensity: VisualDensity.compact,
                  onPressed: () => _addMemo(provider, textBlockIndex),
                ),
                // 섹션 삭제 버튼 추가
                if (!unplaced) IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18, color: Colors.redAccent),
                  visualDensity: VisualDensity.compact,
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text("섹션 삭제"),
                        content: Text("'$sectionTitle' 섹션을 정말 삭제하시겠습니까?\n글과 이미지가 모두 제거됩니다."),
                        actions: [
                          TextButton(onPressed: () => Navigator.pop(context), child: const Text("취소")),
                          TextButton(
                            onPressed: () {
                              // 뒤쪽 블록부터 지워야 앞쪽 블록 위치가 밀리지 않는다 (사진 블록은 항상 글 블록 앞)
                              if (textBlockIndex != null) provider.removeBlock(textBlockIndex);
                              if (imageBlockIndex != null) provider.removeBlock(imageBlockIndex);
                              Navigator.pop(context);
                            },
                            child: const Text("삭제", style: TextStyle(color: Colors.red)),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
          // 뺀 사진: 사진마다 뺀 이유와 [다시 넣기] (6-2, 11/18)
          if (unplaced)
            ..._buildUnplacedRows(sectionImages, allSections, provider)
          else if (sectionImages.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: SizedBox(
                height: 100,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: sectionImages.length,
                  itemBuilder: (context, index) {
                    final realIndex = sectionImages[index];
                    final path = _imagePath(provider, realIndex);
                    if (path == null) return const SizedBox.shrink();

                    return GestureDetector(
                      onTap: () => _showImageDetail(context, path, realIndex, allSections, provider),
                      child: Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.file(File(path), width: 100, height: 100, fit: BoxFit.cover)
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
          if (unplaced)
            // 11/17부터 봇은 글에 없는 사진을 올리지 않는다 (예전 안내: '글 맨 끝에 올라갑니다'는 틀린 말이 됐다)
            const Padding(
              padding: EdgeInsets.all(12),
              child: Text("글에 들어가지 않은 사진이에요. 그대로 두면 네이버에 올라가지 않아요. 넣고 싶은 사진은 [다시 넣기]로 섹션을 고르세요.",
                  style: TextStyle(fontSize: 12, color: Colors.black54)),
            )
          else if (textBlockIndex != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: TextFormField(
                key: Key('$textBlockIndex-$sectionText'),
                initialValue: sectionText,
                maxLines: null,
                decoration: const InputDecoration(border: InputBorder.none, isDense: true),
                style: const TextStyle(fontSize: 15, height: 1.5),
                onChanged: (val) { provider.generatedPost!['blocks'][textBlockIndex]['value'] = val; },
                contextMenuBuilder: memoable
                    ? (context, state) => memoContextMenu(context, state, (quote) => _addMemo(provider, textBlockIndex, quote: quote))
                    : null,
              ),
            ),
          if (memoable) _buildMemoList(provider, textBlockIndex),
        ],
      ),
    );
  }

  // 뺀 사진 한 장씩: 썸네일(누르면 크게) + 뺀 이유 + [다시 넣기]
  List<Widget> _buildUnplacedRows(List<int> imageIndices, List<EditorSection> allSections, PostProvider provider) {
    final reasons = excludedImageReasons(provider.generatedPost ?? {});
    return imageIndices.map((realIndex) {
      final path = _imagePath(provider, realIndex);
      if (path == null) return const SizedBox.shrink();
      final reason = reasons[realIndex];
      return Padding(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              onTap: () => _showImageDetail(context, path, realIndex, allSections, provider),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.file(File(path), width: 80, height: 80, fit: BoxFit.cover),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("사진 ${realIndex + 1}", style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(
                    reason == null || reason.isEmpty ? "뺀 이유가 없어요 (편집 중에 섹션에서 빠진 사진일 수 있어요)" : reason,
                    style: const TextStyle(fontSize: 13, height: 1.4),
                  ),
                  TextButton.icon(
                    style: TextButton.styleFrom(padding: EdgeInsets.zero, visualDensity: VisualDensity.compact),
                    onPressed: () => _showMoveMenu(context, realIndex, allSections, provider),
                    icon: const Icon(Icons.add_photo_alternate_outlined, size: 18),
                    label: const Text("다시 넣기"),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  // ---------------- 메모 ----------------

  Future<void> _addMemo(PostProvider provider, int blockIndex, {String quote = ''}) async {
    final comment = await showMemoDialog(context, quote: quote);
    if (comment != null && comment.isNotEmpty) provider.addMemo(blockIndex, comment, quote: quote);
  }

  Future<void> _editMemo(PostProvider provider, Map memo) async {
    final comment = await showMemoDialog(context, initial: '${memo['comment'] ?? ''}', quote: '${memo['quote'] ?? ''}');
    if (comment != null && comment.isNotEmpty) provider.editMemo('${memo['id']}', comment);
  }

  // 블록에 단 메모 목록 (제목은 -1)
  Widget _buildMemoList(PostProvider provider, int blockIndex) {
    final memos = provider.memos.where((m) => m['block_index'] == blockIndex).toList();
    if (memos.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: memos
            .map((m) => MemoTile(
                  key: ValueKey('${m['id']}'),
                  memo: m,
                  onChecked: (v) => provider.toggleMemo('${m['id']}', v),
                  onEdit: () => _editMemo(provider, m),
                  onDelete: () => provider.deleteMemo('${m['id']}'),
                ))
            .toList(),
      ),
    );
  }

  // 검수(6-3): 결과가 없으면 먼저 검수를 받고, 검수 화면을 연다. 고쳐 쓰고 돌아오면 제목 칸도 바꾼다.
  Future<void> _openReview(PostProvider provider) async {
    provider.updateTitle(_titleController.text); // 편집 화면에서 고친 제목도 검수 받는다
    if (provider.review == null) {
      try {
        await provider.requestReview();
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('검수 실패: $e')));
        return;
      }
    }
    if (!mounted) return;
    final revised = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => const ReviewScreen()));
    if (revised == true && mounted) {
      setState(() => _titleController.text = provider.generatedPost?['title'] ?? '');
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('고쳐 쓴 글을 반영했어요. 바뀐 곳은 초록 테두리로 표시했어요.')));
    }
  }

  // 발행(6-4): 요청을 보낸 뒤 결과 창을 열어, 진행 단계와 결과(고칠 것·실패 이유)를 보여준다.
  Future<void> _showPublishConfirmation(PostProvider provider) async {
    final List<int> postIds;
    try {
      postIds = await provider.publishPost(_titleController.text, "", _selectedPlatforms);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('발행 요청 실패: $e')));
      return;
    }
    if (!mounted || postIds.isEmpty) return;
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => PublishResultDialog(postIds: postIds, fetchStatus: ApiService.getPublishStatus),
    );
  }

  void _showEditInfoModal(BuildContext context, PostProvider provider) {
    final facts = provider.generatedPost?['facts'] ?? {};
    final Map<String, TextEditingController> controllers = {
      'ordered_menu': TextEditingController(text: facts['ordered_menu'] ?? ''),
      'parking': TextEditingController(text: facts['parking'] ?? ''),
      'business_hours': TextEditingController(text: facts['business_hours'] ?? ''),
      'address': TextEditingController(text: facts['address'] ?? ''),
      'phone': TextEditingController(text: facts['phone'] ?? ''),
      'waiting': TextEditingController(text: facts['waiting'] ?? ''),
    };

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(25))),
      builder: (context) {
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom, left: 20, right: 20, top: 20),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text("📍 매장 정보 수정", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                const SizedBox(height: 20),
                _buildModalField("🍔 주문 메뉴", controllers['ordered_menu']!),
                _buildModalField("🚗 주차 정보", controllers['parking']!),
                _buildModalField("🕒 영업 시간", controllers['business_hours']!),
                _buildModalField("🏠 주소", controllers['address']!),
                _buildModalField("📞 전화번호", controllers['phone']!),
                _buildModalField("⏳ 웨이팅/기타", controllers['waiting']!),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.indigo, foregroundColor: Colors.white),
                    onPressed: () async {
                      final Map<String, dynamic> newFacts = {};
                      controllers.forEach((k, v) => newFacts[k] = v.text);
                      Navigator.pop(context);
                      await provider.updateFactsMultiple(newFacts);
                      _titleController.text = provider.generatedPost?['title'] ?? '';
                    },
                    child: const Text("반영 및 재작성"),
                  ),
                ),
                const SizedBox(height: 30),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildModalField(String label, TextEditingController controller) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextField(controller: controller, decoration: InputDecoration(labelText: label, border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)))),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<PostProvider>(context);
    final post = provider.generatedPost;
    if (post == null) return const Scaffold(body: Center(child: CircularProgressIndicator()));

    final List<dynamic> blocks = post['blocks'] ?? [];
    final List<dynamic> images = post['images'] ?? [];
    final layout = buildEditorLayout(blocks, images.length);

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: const Text('AI 자동화 에디터'), actions: [
        TextButton.icon(
          onPressed: provider.isReviewing ? null : () => _openReview(provider),
          icon: const Icon(Icons.fact_check_outlined),
          label: Text(provider.review == null ? '검수 받기' : '검수 결과'),
        ),
        IconButton(onPressed: () => _showPublishConfirmation(provider), icon: const Icon(Icons.send)),
      ]),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 작성 리포트: 형식 검사, '확인 필요' 메모, 비용 (6-1, 11/18)
              // 예전 'AI 분석 인사이트' 카드는 입력한 리뷰 요약을 다시 보여 줄 뿐이었다.
              WritingReportCard(post: post),
              const SizedBox(height: 20),
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _titleController,
                    decoration: const InputDecoration(hintText: '제목', border: InputBorder.none),
                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    contextMenuBuilder: (context, state) =>
                        memoContextMenu(context, state, (quote) => _addMemo(provider, titleIndex, quote: quote)),
                  ),
                ),
                IconButton(
                  tooltip: '제목에 메모 남기기',
                  icon: const Icon(Icons.sticky_note_2_outlined, size: 20, color: Colors.blue),
                  onPressed: () => _addMemo(provider, titleIndex),
                ),
              ]),
              _buildMemoList(provider, titleIndex),
              const Divider(height: 30),

              // 섹션 리스트: 블록 순서 그대로 (= 네이버에 발행되는 순서)
              ...layout.sections.map((s) => _buildSectionItem(
                    s.title, s.text, s.textBlockIndex, s.imageBlockIndex, s.imageIndices, layout.sections, provider,
                  )),

              // 어떤 섹션에도 들어가지 않은 사진 (조용히 사라지지 않도록 따로 보여줌)
              _buildSectionItem(
                "🚫 글에서 뺀 사진", "", null, null, layout.unplacedImages, layout.sections, provider,
                unplaced: true,
              ),
              const SizedBox(height: 100),
            ],
          ),
          // 하단 'AI에게 수정 요청' 입력창은 지웠다 (11/18). /refine이 Gemini라 크레딧 소진으로 동작하지 않았고,
          // 실패해도 화면에 알리지 않았다. 고칠 곳은 글을 직접 고치거나 [검수 받기] → 고쳐쓰기로 한다.
          if (provider.isRefining) Container(color: Colors.black26, child: const Center(child: CircularProgressIndicator())),
          if (provider.isReviewing)
            Container(
              color: Colors.black26,
              child: const Center(
                child: Card(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 16),
                      Text('파워블로거가 검수하는 중이에요 (30초 정도 걸려요)'),
                    ]),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
