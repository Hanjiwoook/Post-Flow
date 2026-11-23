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

  // 2-1. 발행 상태 조회 (6-4): 발행 결과 창이 몇 초마다 묻는다.
  // 돌려주는 것: status(PROCESSING/SUCCESS/FAIL), step, error_code, fail_reason, problems
  static Future<Map<String, dynamic>> getPublishStatus(int postId) async {
    var uri = Uri.parse('$baseUrl/posts/$postId/status');
    var response = await http.get(uri);

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(utf8.decode(response.bodyBytes));
      if (decodedData['success'] == true) {
        return Map<String, dynamic>.from(decodedData['data']);
      } else {
        throw Exception(decodedData['message'] ?? '발행 상태 조회 실패');
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

  // JSON POST 공통: success가 아니면 서버가 보낸 이유로 Exception을 던진다
  static Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> body, String failMessage) async {
    final response = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    if (response.statusCode != 200) throw Exception('서버 에러: ${response.statusCode}');
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded['success'] != true) throw Exception(decoded['message'] ?? failMessage);
    return Map<String, dynamic>.from(decoded['data']);
  }

  // 7. 파워블로거 검수: 점수, 지적, 빠진 정보, 사용자에게 할 질문 (글은 고치지 않음)
  static Future<Map<String, dynamic>> reviewPost(String title, List<dynamic> blocks, Map<String, dynamic> facts,
      {List<dynamic> images = const [], List<dynamic> writingNotes = const []}) {
    return _postJson('/posts/review', {
      'title': title,
      'blocks': blocks,
      'facts': facts,
      'images': images,
      'writing_notes': writingNotes,
    }, '검수 실패');
  }

  // 8. 검수 반영 고쳐쓰기: 글 블록만 고친다 (사진·지도·인용구는 그대로)
  static Future<Map<String, dynamic>> revisePost(String title, List<dynamic> blocks, Map<String, dynamic> facts,
      Map<String, dynamic> review, List<Map<String, String>> answers,
      {List<dynamic> images = const [], List<dynamic> writingNotes = const []}) {
    return _postJson('/posts/revise', {
      'title': title,
      'blocks': blocks,
      'facts': facts,
      'images': images,
      'writing_notes': writingNotes,
      'review': review,
      'answers': answers,
    }, '고쳐쓰기 실패');
  }

  // 9. 메모로 부분 고치기: 메모마다 고친 안과 의견을 받는다 (글은 바꾸지 않음, 승인은 앱에서)
  static Future<Map<String, dynamic>> memoEdit(String title, List<dynamic> blocks, Map<String, dynamic> facts,
      List<Map<String, dynamic>> memos,
      {List<dynamic> images = const [], List<dynamic> writingNotes = const [], List<dynamic> answers = const []}) {
    return _postJson('/posts/memo-edit', {
      'title': title,
      'blocks': blocks,
      'facts': facts,
      'images': images,
      'writing_notes': writingNotes,
      'memos': memos,
      'answers': answers,
    }, '고친 안 받기 실패');
  }
}
