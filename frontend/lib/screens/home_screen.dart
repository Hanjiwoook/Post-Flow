import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../providers/post_provider.dart';
import '../services/api_service.dart';
import 'post_editor_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _selectedTemplate = '맛집리뷰 템플릿';
  
  final _placeNameController = TextEditingController();
  final _addressController = TextEditingController();
  final _phoneController = TextEditingController();
  final _businessHoursController = TextEditingController();
  final _parkingController = TextEditingController();
  final _waitingController = TextEditingController();
  final _menuController = TextEditingController();

  // 사진별 힌트 입력을 위한 컨트롤러 리스트
  List<TextEditingController> _imageHintControllers = [];

  String _ownerIntro = "";
  String _recentEvent = "";
  List<String> _amenities = [];
  List<String> _placeVibe = [];
  String _fullContext = "";

  @override
  void dispose() {
    _placeNameController.dispose();
    _addressController.dispose();
    _phoneController.dispose();
    _businessHoursController.dispose();
    _parkingController.dispose();
    _waitingController.dispose();
    _menuController.dispose();
    for (var controller in _imageHintControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  void _syncImageControllers(int count) {
    if (_imageHintControllers.length < count) {
      for (int i = _imageHintControllers.length; i < count; i++) {
        _imageHintControllers.add(TextEditingController());
      }
    } else if (_imageHintControllers.length > count) {
      for (int i = count; i < _imageHintControllers.length; i++) {
        _imageHintControllers[i].dispose();
      }
      _imageHintControllers = _imageHintControllers.sublist(0, count);
    }
  }

  Widget _buildTemplateChip(String label) {
    final isSelected = _selectedTemplate == label;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        if (selected) setState(() => _selectedTemplate = label);
      },
      selectedColor: Colors.indigo,
      labelStyle: TextStyle(color: isSelected ? Colors.white : Colors.black),
    );
  }

  Widget _buildInput(String hint, TextEditingController controller, IconData icon) {
    return TextField(
      controller: controller,
      decoration: InputDecoration(
        hintText: hint,
        prefixIcon: Icon(icon, size: 18),
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      style: const TextStyle(fontSize: 14),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<PostProvider>(context);
    final ImagePicker picker = ImagePicker();
    _syncImageControllers(provider.selectedImages.length);

    Future<void> pickImages() async {
      final List<XFile> images = await picker.pickMultiImage();
      if (images.isNotEmpty) {
        provider.setImages(images);
      }
    }

    Future<void> startAnalysis() async {
      try {
        final imageHints = _imageHintControllers.map((c) => c.text).toList();
        
        final initialFacts = {
          'place_name': _placeNameController.text,
          'address': _addressController.text,
          'phone': _phoneController.text,
          'business_hours': _businessHoursController.text,
          'parking': _parkingController.text,
          'waiting': _waitingController.text,
          'ordered_menu': _menuController.text,
          'image_hints': imageHints, // 사진별 힌트 추가
          'owner_intro': _ownerIntro,
          'recent_event': _recentEvent,
          'amenities': _amenities.join(", "),
          'place_vibe': _placeVibe.join(", "),
          'full_context': _fullContext,
        };

        await provider.analyzeImages(_selectedTemplate, initialFacts: initialFacts);
        
        if (mounted && provider.generatedPost != null) {
            Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PostEditorScreen()));
        }
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('분석 중 오류가 발생했습니다: $e')));
      }
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Post Flow 🚀')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text("블로그 포스팅, 이제 사진만 고르세요.\nAI가 알아서 써줍니다.", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
            const SizedBox(height: 30),

            if (provider.selectedImages.isEmpty)
              GestureDetector(
                onTap: pickImages,
                child: Container(
                  height: 200,
                  decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.grey[400]!)),
                  child: const Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.add_photo_alternate_outlined, size: 64, color: Colors.grey), SizedBox(height: 10), Text("터치하여 사진을 추가하세요", style: TextStyle(color: Colors.grey))]),
                ),
              )
            else
              Column(
                children: [
                  const Text("📸 사진별 설명을 입력하면 AI가 더 정확하게 써줘요!", style: TextStyle(fontSize: 12, color: Colors.indigo, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 220, // 높이 조절 (입력창 포함)
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      itemCount: provider.selectedImages.length,
                      itemBuilder: (context, index) {
                        return Padding(
                          padding: const EdgeInsets.only(right: 12.0),
                          child: Column(
                            children: [
                              Stack(
                                children: [
                                  ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.file(File(provider.selectedImages[index].path), width: 140, height: 140, fit: BoxFit.cover)),
                                  Positioned(right: 0, top: 0, child: IconButton(icon: const Icon(Icons.close, color: Colors.white, size: 18), style: IconButton.styleFrom(backgroundColor: Colors.black54), onPressed: () => provider.removeImage(index))),
                                ],
                              ),
                              const SizedBox(height: 8),
                              SizedBox(
                                width: 140,
                                child: TextField(
                                  controller: _imageHintControllers[index],
                                  decoration: InputDecoration(
                                    hintText: '사진 설명 (힌트)',
                                    hintStyle: const TextStyle(fontSize: 11),
                                    filled: true, fillColor: Colors.indigo[50],
                                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
                                    isDense: true, contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                                  ),
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: Colors.amber[50], borderRadius: BorderRadius.circular(15), border: Border.all(color: Colors.amber[200]!)),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(children: [Icon(Icons.edit_note, color: Colors.orange, size: 20), SizedBox(width: 8), Text("나의 방문 기록", style: TextStyle(fontWeight: FontWeight.bold, color: Colors.orange, fontSize: 15))]),
                        const SizedBox(height: 12),
                        _buildInput("오늘 어떤 메뉴를 드셨나요? (쉼표 구분)", _menuController, Icons.restaurant_menu),
                        const SizedBox(height: 10),
                        _buildInput("웨이팅은 어땠나요? (예: 없음, 20분)", _waitingController, Icons.hourglass_empty),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextButton.icon(onPressed: pickImages, icon: const Icon(Icons.add), label: const Text("사진 더 추가하기 / 다시 선택하기")),
                ],
              ),
            
            const SizedBox(height: 30),
            const Text("📋 포스팅 템플릿", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            Row(children: [_buildTemplateChip('맛집리뷰 템플릿')]),
            const SizedBox(height: 30),

            const Row(children: [Icon(Icons.auto_awesome, size: 18, color: Colors.indigo), SizedBox(width: 8), Text("AI가 찾아준 가게 정보", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.indigo))]),
            const SizedBox(height: 10),
            Card(
              elevation: 0, color: Colors.indigo[50]!.withOpacity(0.5),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.indigo[100]!)),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(child: _buildInput("가게명 (필수)", _placeNameController, Icons.storefront)),
                        const SizedBox(width: 8),
                        ElevatedButton.icon(
                          onPressed: () async {
                            if (_placeNameController.text.isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('가게명을 먼저 입력해주세요.')));
                              return;
                            }
                            showDialog(context: context, barrierDismissible: false, builder: (context) => const Center(child: CircularProgressIndicator()));
                            try {
                              final info = await ApiService.getPlaceInfo(_placeNameController.text);
                              Navigator.pop(context);
                              setState(() {
                                if (info['address'] != null) _addressController.text = info['address'];
                                if (info['phone'] != null) _phoneController.text = info['phone'];
                                if (info['business_hours'] != null) _businessHoursController.text = info['business_hours'];
                                if (info['parking'] != null) _parkingController.text = info['parking'];
                                if (info['place_name'] != null) _placeNameController.text = info['place_name'];
                                _ownerIntro = info['owner_intro'] ?? "";
                                _recentEvent = info['recent_event'] ?? "";
                                _amenities = List<String>.from(info['amenities'] ?? []);
                                _placeVibe = List<String>.from(info['place_vibe'] ?? []);
                                _fullContext = info['full_context'] ?? "";
                              });
                            } catch (e) {
                              Navigator.pop(context);
                              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('정보 가져오기 실패: $e')));
                            }
                          },
                          icon: const Icon(Icons.search, size: 18),
                          label: const Text("정보 가져오기"),
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.indigo, foregroundColor: Colors.white),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _buildInput("주소", _addressController, Icons.location_on_outlined),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(child: _buildInput("전화번호", _phoneController, Icons.phone_outlined)),
                        const SizedBox(width: 12),
                        Expanded(child: _buildInput("주차 정보", _parkingController, Icons.local_parking)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _buildInput("영업시간", _businessHoursController, Icons.access_time),
                  ],
                ),
              ),
            ),
            
            if (_ownerIntro.isNotEmpty || _recentEvent != "없음" && _recentEvent.isNotEmpty) ...[
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.indigo[900], borderRadius: BorderRadius.circular(12)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(children: [Icon(Icons.lightbulb, color: Colors.amber, size: 20), SizedBox(width: 8), Text("AI 인사이트 브리핑", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold))]),
                    const SizedBox(height: 12),
                    if (_ownerIntro.isNotEmpty) Text(_ownerIntro, style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.5)),
                    if (_recentEvent != "없음" && _recentEvent.isNotEmpty) Text(_recentEvent, style: const TextStyle(color: Colors.white, fontSize: 13)),
                  ],
                ),
              ),
            ],
            
            const SizedBox(height: 30),
            if (provider.isLoading)
              const Column(children: [CircularProgressIndicator(), SizedBox(height: 16), Text("AI가 사진을 분석하고 글을 쓰고 있어요.\n잠시만 기다려주세요 ☕", textAlign: TextAlign.center)])
            else
              FilledButton.icon(
                onPressed: provider.selectedImages.isNotEmpty ? startAnalysis : null,
                icon: const Icon(Icons.auto_awesome),
                label: const Text("AI 블로그 글 생성하기", style: TextStyle(fontSize: 18)),
                style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
              ),

            const SizedBox(height: 40),
            const Divider(),
            const SizedBox(height: 20),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [const Text("📜 최근 발행 이력", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), TextButton(onPressed: () => setState(() {}), child: const Text("새로고침"))]),
            const SizedBox(height: 10),
            
            FutureBuilder<List<dynamic>>(
              future: ApiService.getHistory(),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
                if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) return Container(padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: Colors.grey[100], borderRadius: BorderRadius.circular(12)), child: const Text("최근 작업 이력이 없습니다.", textAlign: TextAlign.center));
                final history = snapshot.data!;
                return ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: history.length > 5 ? 5 : history.length,
                  separatorBuilder: (context, index) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final item = history[index];
                    return ListTile(
                      tileColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.grey[300]!)),
                      leading: const Icon(Icons.article_outlined, color: Colors.indigo),
                      title: Text(item['title'] ?? '제목 없음', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text("${item['platform']} · ${item['created_at'].toString().split('T')[0]}"),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        provider.loadFromHistory(item);
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PostEditorScreen()));
                      },
                    );
                  },
                );
              },
            ),
            const SizedBox(height: 50),
          ],
        ),
      ),
    );
  }
}
