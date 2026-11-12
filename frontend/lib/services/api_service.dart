import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

class ApiService {
  // Android Emulator: 10.0.2.2, iOS Simulator/Web: 127.0.0.1
  static const String baseUrl = 'http://127.0.0.1:8000/api/v1';

  // 1. 이미지 분석 및 초안 생성 요청
  static Future<Map<String, dynamic>> analyzeImages(
      List<XFile> images, String style, {String? templateName, Map<String, dynamic>? initialFacts}) async {
    var uri = Uri.parse('$baseUrl/posts/analyze');
    var request = http.MultipartRequest('POST', uri);

    for (var image in images) {
      request.files.add(await http.MultipartFile.fromPath('files', image.path));
    }
    request.fields['style'] = style;
    if (templateName != null) {
      request.fields['template_name'] = templateName;
    }
    if (initialFacts != null) {
      request.fields['initial_facts'] = jsonEncode(initialFacts);
    }

    var streamedResponse = await request.send();
    var response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '분석 실패');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }

  // 2. 최종 포스팅 발행 요청
  static Future<Map<String, dynamic>> publishPost(
      String title, String content, List<String> imagePaths, List<String> platforms,
      {List<String> tags = const [], Map<String, dynamic> facts = const {}, List<dynamic> images = const [], List<dynamic> blocks = const []}) async {
    var uri = Uri.parse('$baseUrl/posts/publish');
    var body = jsonEncode({
      'draft_id': 'temp_id', 
      'final_title': title,
      'final_content': content,
      'blocks': blocks,
      'tags': tags,
      'facts': facts,
      'images': images,
      'image_paths': imagePaths,
      'platforms': platforms
    });

    var response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body,
    );

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '발행 요청 실패');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }

  // 3. 발행 이력 조회
  static Future<List<dynamic>> getHistory() async {
    var uri = Uri.parse('$baseUrl/posts/history');
    var response = await http.get(uri);

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '이력 조회 실패');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }

  // 4. 본문 내용 재구성 요청 (팩트 기반)
  static Future<Map<String, dynamic>> refineContent(
      String title, String content, Map<String, dynamic> facts, String style, {List<dynamic> images = const [], List<dynamic> blocks = const [], String? instruction, String? templateName}) async {
    var uri = Uri.parse('$baseUrl/posts/refine');
    var body = jsonEncode({
      'title': title,
      'content': content,
      'blocks': blocks,
      'facts': facts,
      'images': images,
      'style': style,
      'instruction': instruction,
      'template_name': templateName,
    });

    var response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body,
    );

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '재구성 실패');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }

  // 5. 특정 섹션만 초고속 부분 업데이트 요청
  static Future<Map<String, dynamic>> patchPost(
      String title, List<dynamic> blocks, Map<String, dynamic> facts, {List<dynamic> images = const [], String? style, String? templateName}) async {
    var uri = Uri.parse('$baseUrl/posts/patch');
    var body = jsonEncode({
      'title': title,
      'blocks': blocks,
      'facts': facts,
      'images': images,
      'style': style,
      'template_name': templateName,
    });

    var response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body,
    );

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '부분 업데이트 실패');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }

  // 6. 네이버 지도 가게 정보 검색
  static Future<Map<String, dynamic>> getPlaceInfo(String query) async {
    var uri = Uri.parse('$baseUrl/place-info?query=$query');
    var response = await http.get(uri);

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return decodedData['data'];
      } else {
        throw Exception(decodedData['message'] ?? '정보를 찾을 수 없습니다.');
      }
    } else {
      throw Exception('서버 에러: ${response.statusCode}');
    }
  }
}
