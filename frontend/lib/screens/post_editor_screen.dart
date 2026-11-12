import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/post_provider.dart';

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
  late TextEditingController _instructionController;
  final List<String> _selectedPlatforms = ['naver']; 

  @override
  void initState() {
    super.initState();
    final provider = Provider.of<PostProvider>(context, listen: false);
    _titleController = TextEditingController(text: provider.generatedPost?['title'] ?? '');
    _instructionController = TextEditingController();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _instructionController.dispose();
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

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
                    if (sectionImages.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(left: 8),
                        child: Text("${sectionImages.length}장의 사진", style: const TextStyle(fontSize: 11, color: Colors.indigoAccent)),
                      ),
                  ],
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
          if (sectionImages.isNotEmpty)
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
            const Padding(
              padding: EdgeInsets.all(12),
              child: Text("본문 어디에도 배치되지 않은 사진입니다. 사진을 눌러 섹션으로 옮길 수 있고, 그대로 두면 네이버 발행 시 글 맨 끝에 올라갑니다.",
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
              ),
            ),
        ],
      ),
    );
  }

  void _showPublishConfirmation(PostProvider provider) {
    provider.publishPost(_titleController.text, "", _selectedPlatforms);
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('블로그 발행을 시작합니다...')));
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
    final facts = post['facts'] ?? {};
    final List<dynamic> images = post['images'] ?? [];
    final layout = buildEditorLayout(blocks, images.length);

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: const Text('AI 자동화 에디터'), actions: [IconButton(onPressed: () => _showPublishConfirmation(provider), icon: const Icon(Icons.send))]),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 정보 카드
              Card(
                elevation: 0, color: Colors.indigo[900],
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text("AI 분석 인사이트", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Text(facts['visitor_insight'] ?? "분석된 리뷰 정보가 없습니다.", style: const TextStyle(color: Colors.white70, fontSize: 13)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              TextField(controller: _titleController, decoration: const InputDecoration(hintText: '제목', border: InputBorder.none), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
              const Divider(height: 30),

              // 섹션 리스트: 블록 순서 그대로 (= 네이버에 발행되는 순서)
              ...layout.sections.map((s) => _buildSectionItem(
                    s.title, s.text, s.textBlockIndex, s.imageBlockIndex, s.imageIndices, layout.sections, provider,
                  )),

              // 어떤 섹션에도 들어가지 않은 사진 (조용히 사라지지 않도록 따로 보여줌)
              _buildSectionItem(
                "⚠️ 배치 안 된 사진", "", null, null, layout.unplacedImages, layout.sections, provider,
                unplaced: true,
              ),
              const SizedBox(height: 100),
            ],
          ),
          // 하단 입력창
          Positioned(
            bottom: 0, left: 0, right: 0,
            child: Container(
              padding: const EdgeInsets.all(12), color: Colors.white,
              child: Row(
                children: [
                  Expanded(child: TextField(controller: _instructionController, decoration: InputDecoration(hintText: 'AI에게 수정 요청', filled: true, fillColor: Colors.grey[100], border: OutlineInputBorder(borderRadius: BorderRadius.circular(20), borderSide: BorderSide.none)))),
                  const SizedBox(width: 8),
                  FloatingActionButton.small(onPressed: () async {
                    await provider.refineWithInstruction(_instructionController.text);
                    _titleController.text = provider.generatedPost?['title'] ?? '';
                  }, child: const Icon(Icons.auto_awesome))
                ],
              ),
            ),
          ),
          if (provider.isRefining) Container(color: Colors.black26, child: const Center(child: CircularProgressIndicator())),
        ],
      ),
    );
  }
}
