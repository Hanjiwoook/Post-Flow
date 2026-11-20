import 'dart:convert';
import 'dart:io';

/// 작업 중인 글 1개(본문·메모·받은 안·검수 결과 포함)를 노트북 파일에 저장한다.
/// 앱을 꺼도 홈 화면의 [이어서 작업하기]로 다시 열 수 있게 하려는 것이다.
/// 저장 위치: %APPDATA%\post_flow\current_draft.json (서버가 꺼져 있어도 저장된다)
class DraftStore {
  final File file;
  DraftStore(String path) : file = File(path);

  /// Windows 기본 위치. APPDATA가 없으면 null (저장하지 않음).
  static DraftStore? windowsDefault() {
    final appData = Platform.environment['APPDATA'];
    if (appData == null || appData.isEmpty) return null;
    return DraftStore('$appData${Platform.pathSeparator}post_flow${Platform.pathSeparator}current_draft.json');
  }

  /// 저장한 글. 없거나 깨졌으면 null.
  Map<String, dynamic>? load() {
    try {
      if (!file.existsSync()) return null;
      final data = jsonDecode(file.readAsStringSync());
      return data is Map<String, dynamic> && data['post'] is Map ? data : null;
    } catch (_) {
      return null; // 저장 중 꺼져서 깨진 파일 등은 없는 것으로 본다
    }
  }

  /// 임시 파일에 먼저 쓰고 바꿔 끼운다 (쓰는 도중 꺼져도 앞의 저장본이 깨지지 않게)
  void save(Map<String, dynamic> post, List<String> localImagePaths) {
    file.parent.createSync(recursive: true);
    final tmp = File('${file.path}.tmp');
    tmp.writeAsStringSync(jsonEncode({
      'saved_at': DateTime.now().toIso8601String(),
      'local_image_paths': localImagePaths,
      'post': post,
    }));
    if (file.existsSync()) file.deleteSync();
    tmp.renameSync(file.path);
  }

  void clear() {
    if (file.existsSync()) file.deleteSync();
  }
}
