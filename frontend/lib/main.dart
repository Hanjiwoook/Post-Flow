import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

void main() {
  runApp(const PostFlowApp());
}

class PostFlowApp extends StatelessWidget {
  const PostFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Post Flow',
      theme: ThemeData(
        primarySwatch: Colors.indigo,
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // 상태 변수들
  final ImagePicker _picker = ImagePicker();
  List<XFile> _selectedImages = []; // 선택된 이미지들
  bool _isLoading = false; // 로딩 중인지 여부
  Map<String, dynamic>? _blogPost; // 서버에서 받은 결과

  // 1. 이미지 선택 함수
  Future<void> _pickImages() async {
    final List<XFile> images = await _picker.pickMultiImage();
    if (images.isNotEmpty) {
      setState(() {
        _selectedImages = images;
        _blogPost = null; // 새 이미지를 고르면 기존 결과 초기화
      });
    }
  }

  // 2. 서버로 전송 및 분석 요청 함수
  Future<void> _analyzeImages() async {
    if (_selectedImages.isEmpty) return;

    setState(() {
      _isLoading = true;
    });

    try {
      // 서버 주소 (윈도우/웹: 127.0.0.1, 안드로이드 에뮬레이터: 10.0.2.2)
      var uri = Uri.parse('http://127.0.0.1:8000/api/v1/analyze');

      var request = http.MultipartRequest('POST', uri);

      // 이미지 파일들을 요청에 담기
      for (var image in _selectedImages) {
        request.files
            .add(await http.MultipartFile.fromPath('files', image.path));
      }

      // 스타일 지정
      request.fields['style'] = 'emotional';

      // 전송!
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        // 성공하면 결과를 JSON으로 풀어서 화면에 보여줌
        final data = jsonDecode(utf8.decode(response.bodyBytes)); // 한글 깨짐 방지
        setState(() {
          _blogPost = data['result'];
        });
      } else {
        throw Exception('서버 에러: ${response.statusCode}');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('에러 발생: $e')),
      );
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Post Flow 🚀')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // [1] 이미지 선택 버튼
            ElevatedButton.icon(
              onPressed: _pickImages,
              icon: const Icon(Icons.photo_library),
              label: Text('${_selectedImages.length}장의 사진 선택하기'),
              style:
                  ElevatedButton.styleFrom(padding: const EdgeInsets.all(16)),
            ),

            const SizedBox(height: 10),

            // [2] 선택된 이미지 미리보기
            if (_selectedImages.isNotEmpty)
              SizedBox(
                height: 100,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: _selectedImages.length,
                  itemBuilder: (context, index) {
                    return Padding(
                      padding: const EdgeInsets.only(right: 8.0),
                      child: Image.file(
                        File(_selectedImages[index].path),
                        width: 100,
                        height: 100,
                        fit: BoxFit.cover,
                      ),
                    );
                  },
                ),
              ),

            const SizedBox(height: 20),

            // [3] 분석 버튼 (로딩 중이면 뺑글이 표시)
            if (_isLoading)
              const Center(child: CircularProgressIndicator())
            else if (_selectedImages.isNotEmpty)
              FilledButton(
                onPressed: _analyzeImages,
                child: const Text('✨ AI 블로그 글 생성하기'),
              ),

            const SizedBox(height: 30),

            // [4] 결과 보여주는 곳
            if (_blogPost != null) ...[
              const Divider(),
              Text(
                _blogPost!['title'] ?? '',
                style:
                    const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8.0,
                children: (_blogPost!['tags'] as List)
                    .map((tag) => Chip(
                          label: Text(tag),
                          backgroundColor: Colors.indigo.shade50,
                        ))
                    .toList(),
              ),
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _blogPost!['content'] ?? '',
                  style: const TextStyle(fontSize: 16, height: 1.6),
                ),
              ),
            ]
          ],
        ),
      ),
    );
  }
}
