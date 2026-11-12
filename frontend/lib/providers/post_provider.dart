import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';

class PostProvider with ChangeNotifier {
  List<XFile> _selectedImages = [];
  bool _isLoading = false;
  bool _isRefining = false;
  Map<String, dynamic>? _generatedPost;

  List<XFile> get selectedImages => _selectedImages;
  bool get isLoading => _isLoading;
  bool get isRefining => _isRefining;
  Map<String, dynamic>? get generatedPost => _generatedPost;

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
    }
    blocks[imageBlockIndex]['image_indices'] = [
      ..._toIntList(blocks[imageBlockIndex]['image_indices']),
      imageIndex,
    ];

    _generatedPost!['blocks'] = blocks;
    notifyListeners();
  }

  static List<int> _toIntList(dynamic raw) {
    if (raw is! List) return [];
    return raw.whereType<num>().map((n) => n.toInt()).toList();
  }

  // 이미지 카테고리 변경 기능 추가
  void updateImageCategory(int index, String newCategory) {
    if (_generatedPost == null || _generatedPost!['images'] == null) return;
    
    final images = List<dynamic>.from(_generatedPost!['images']);
    if (index >= 0 && index < images.length) {
      final img = Map<String, dynamic>.from(images[index]);
      img['category'] = newCategory;
      images[index] = img;
      _generatedPost!['images'] = images;
      notifyListeners();
    }
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

  // 여러 팩트 정보를 한 번에 업데이트하고 부분 수정을 요청함
  Future<void> updateFactsMultiple(Map<String, dynamic> newFacts) async {
    if (_generatedPost == null) return;
    
    final facts = Map<String, dynamic>.from(_generatedPost!['facts'] ?? {});
    newFacts.forEach((key, value) {
      facts[key] = value;
    });
    _generatedPost!['facts'] = facts;
    
    _isRefining = true;
    notifyListeners();
    
    try {
      final images = List<dynamic>.from(_generatedPost!['images'] ?? []);
      final blocks = List<dynamic>.from(_generatedPost!['blocks'] ?? []);
      
      final result = await ApiService.patchPost(
        _generatedPost!['title'], 
        blocks, 
        facts, 
        images: images,
      );
      
      _generatedPost!['blocks'] = result['blocks'];
      _generatedPost!['facts'] = result['facts'];
      
    } catch (e) {
      print('Error patching multiple facts: $e');
    } finally {
      _isRefining = false;
      notifyListeners();
    }
  }

  // 채팅 기반 본문 재구성 (지시사항 반영)
  Future<void> refineWithInstruction(String instruction) async {
    if (_generatedPost == null) return;
    
    _isRefining = true;
    notifyListeners();
    
    try {
      final originalBlocks = List<dynamic>.from(_generatedPost!['blocks'] ?? []);
      final images = List<dynamic>.from(_generatedPost!['images'] ?? []);
      final blocks = List<dynamic>.from(originalBlocks);
      final result = await ApiService.refineContent(
        _generatedPost!['title'], 
        _generatedPost!['content'], 
        _generatedPost!['facts'] ?? {}, 
        'professional',
        instruction: instruction,
        images: images,
        blocks: blocks,
      );
      
      // 스마트 머지: AI 응답 블록과 원본 블록을 비교하여 이미지/구조 보존
      final resultBlocks = List<dynamic>.from(result['blocks'] ?? []);
      final mergedBlocks = <dynamic>[];
      
      for (int i = 0; i < originalBlocks.length; i++) {
        final orig = Map<String, dynamic>.from(originalBlocks[i]);
        
        if (orig['type'] == 'image' || orig['type'] == 'divider') {
          // 이미지와 구분선 블록은 원본 그대로 유지 (AI가 건드리면 안 됨)
          mergedBlocks.add(orig);
        } else if (i < resultBlocks.length) {
          // 텍스트/인용구 블록은 AI 결과 사용하되, image_indices는 원본에서 복원
          final refined = Map<String, dynamic>.from(resultBlocks[i]);
          if (orig['image_indices'] != null && (orig['image_indices'] as List).isNotEmpty) {
            refined['image_indices'] = orig['image_indices'];
          }
          mergedBlocks.add(refined);
        } else {
          // AI가 블록을 줄여버린 경우, 원본 유지
          mergedBlocks.add(orig);
        }
      }
      
      _generatedPost!['title'] = result['title'];
      _generatedPost!['content'] = result['content'];
      _generatedPost!['tags'] = result['tags'];
      _generatedPost!['facts'] = result['facts'];
      _generatedPost!['blocks'] = mergedBlocks;
      // images는 원본 유지 (AI가 건드리지 못하게)

      
    } catch (e) {
      print('Error refining with instruction: $e');
    } finally {
      _isRefining = false;
      notifyListeners();
    }
  }

  Map<String, List<Map<String, dynamic>>> getImagesByCategory() {
    if (_generatedPost == null || _generatedPost!['images'] == null) return {};
    
    final Map<String, List<Map<String, dynamic>>> grouped = {};
    final images = _generatedPost!['images'] as List<dynamic>;
    
    for (int i = 0; i < images.length; i++) {
      final img = images[i] as Map<String, dynamic>;
      final cat = img['category'] as String;
      
      grouped.putIfAbsent(cat, () => []).add({
        'index': i,
        'data': img,
      });
    }
    return grouped;
  }

  Future<void> publishPost(String title, String content, List<String> platforms) async {
    if (_generatedPost == null) return;

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

      await ApiService.publishPost(
        title, 
        content, 
        imagePaths, 
        platforms,
        tags: tags,
        facts: facts,
        images: images,
        blocks: blocks,
      );
    } catch (e) {
      print('Error publishing post: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
