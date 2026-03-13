import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/post_provider.dart';

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

  void _showMoveMenu(BuildContext context, int imageIndex, PostProvider provider) {
    final Map<String, String> categoryNames = {
      'EXTERIOR': '🏠 외관/건물',
      'INTERIOR': '🛋️ 매장 내부',
      'MENU': '📋 메뉴판/메뉴',
      'FOOD_MAIN': '😋 음식/디저트',
      'MAP': '📍 매장 위치/정보',
      'OTHER': ' 기타 (인사/마무리)',
    };

    showModalBottomSheet(
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
              ...categoryNames.entries.map((entry) {
                return ListTile(
                  leading: const Icon(Icons.move_to_inbox, size: 20),
                  title: Text(entry.value),
                  onTap: () {
                    provider.updateImageCategory(imageIndex, entry.key);
                    Navigator.pop(context);
                  },
                );
              }),
            ],
          ),
        );
      },
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
  Widget _buildSectionItem(String sectionTitle, String categoryKey, List<dynamic> blocks, Map<String, List<Map<String, dynamic>>> groupedImages, PostProvider provider, {String? customBlockValue, int? customBlockIndex}) {
    final sectionImages = groupedImages[categoryKey] ?? [];
    String sectionText = customBlockValue ?? "";
    int blockIndex = customBlockIndex ?? -1;
    
    if (customBlockValue == null) {
      for (int i = 0; i < blocks.length; i++) {
        final String val = blocks[i]['value']?.toString() ?? "";
        if (val.contains(sectionTitle)) {
          sectionText = val;
          blockIndex = i;
          break;
        }
      }
    }

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
                IconButton(
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
                              if (blockIndex != -1) {
                                provider.removeBlock(blockIndex);
                              }
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
                    final imgData = sectionImages[index];
                    final realIndex = imgData['index'];
                    final path = provider.selectedImages.isNotEmpty 
                        ? provider.selectedImages[realIndex].path 
                        : imgData['data']['path'];
                    
                    return GestureDetector(
                      onTap: () => _showMoveMenu(context, realIndex, provider),
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
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextFormField(
              key: Key(sectionText),
              initialValue: sectionText,
              maxLines: null,
              decoration: const InputDecoration(border: InputBorder.none, isDense: true),
              style: const TextStyle(fontSize: 15, height: 1.5),
              onChanged: (val) { if (blockIndex != -1) provider.generatedPost!['blocks'][blockIndex]['value'] = val; },
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

    final groupedImages = provider.getImagesByCategory();
    final List<dynamic> blocks = post['blocks'] ?? [];
    final facts = post['facts'] ?? {};
    
    // 음식(FOOD_ITEM) 블록들만 별도로 추출
    final List<Map<String, dynamic>> foodBlocks = [];
    for (int i = 0; i < blocks.length; i++) {
      final String val = blocks[i]['value']?.toString() ?? "";
      if (val.contains("[음식:")) {
        foodBlocks.add({'index': i, 'value': val});
      }
    }

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

              // 섹션 리스트
              _buildSectionItem("인사말", "OTHER", blocks, groupedImages, provider),
              _buildSectionItem("매장 위치 & 정보", "MAP", blocks, groupedImages, provider),
              _buildSectionItem("외관", "EXTERIOR", blocks, groupedImages, provider),
              _buildSectionItem("내부", "INTERIOR", blocks, groupedImages, provider),
              
              // 메뉴판 섹션 (독립)
              _buildSectionItem("메뉴판", "MENU", blocks, groupedImages, provider),
              
              // 음식 섹션 (동적 생성)
              ...foodBlocks.map((fb) {
                final String menuName = fb['value'].split(']')[0].replaceAll('[음식:', '');
                return _buildSectionItem(
                  "음식: $menuName", 
                  "FOOD_ITEM:$menuName", // 카테고리 키도 메뉴명에 맞게 매칭
                  blocks, groupedImages, provider,
                  customBlockValue: fb['value'],
                  customBlockIndex: fb['index']
                );
              }),

              _buildSectionItem("총평 & 마무리", "OTHER", blocks, groupedImages, provider),
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
