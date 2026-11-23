import 'dart:convert';
import 'dart:io';

/// 작업 중인 글(본문·메모·받은 안·검수 결과 포함)을 노트북에 글마다 파일 하나로 저장한다.
/// 앱을 꺼도 홈 화면의 작업 중인 글 목록에서 [이어서 작업하기]로 다시 열 수 있게 하려는 것이다.
/// 저장 위치: %APPDATA%\post_flow\drafts\<글 번호>.json (서버가 꺼져 있어도 저장된다)
///
/// 11/23: 처음에는 current_draft.json 하나에만 저장해서 새 글을 쓰면 앞 글이 덮였다.
/// 지금은 글마다 따로 저장하고, 예전 파일이 있으면 처음 한 번 drafts 폴더로 옮긴다.
class DraftStore {
  final Directory dir;
  final File? legacyFile; // 예전 저장 파일 (current_draft.json). 있으면 drafts로 옮긴다.

  DraftStore(String dirPath, {String? legacyPath})
      : dir = Directory(dirPath),
        legacyFile = legacyPath == null ? null : File(legacyPath);

  /// Windows 기본 위치. APPDATA가 없으면 null (저장하지 않음).
  static DraftStore? windowsDefault() {
    final appData = Platform.environment['APPDATA'];
    if (appData == null || appData.isEmpty) return null;
    final sep = Platform.pathSeparator;
    return DraftStore('$appData${sep}post_flow${sep}drafts', legacyPath: '$appData${sep}post_flow${sep}current_draft.json');
  }

  /// 새로 쓴 글의 번호
  static String newId() => 'd${DateTime.now().microsecondsSinceEpoch}';

  /// 발행 이력에서 연 글의 번호 (같은 글을 다시 열면 같은 작업본으로 이어진다)
  static String historyId(Object id) => 'h$id';

  // 파일 이름에 쓸 수 없는 글자는 _로 바꾼다
  File _file(String id) => File('${dir.path}${Platform.pathSeparator}${id.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_')}.json');

  Map<String, dynamic>? _read(File f) {
    try {
      if (!f.existsSync()) return null;
      final data = jsonDecode(f.readAsStringSync());
      return data is Map<String, dynamic> && data['post'] is Map ? data : null;
    } catch (_) {
      return null; // 저장 중 꺼져서 깨진 파일 등은 없는 것으로 본다
    }
  }

  /// 예전 current_draft.json → drafts/d<저장 시각>.json (한 번만). 깨진 파일은 그대로 둔다.
  void _migrateLegacy() {
    final legacy = legacyFile;
    if (legacy == null || !legacy.existsSync()) return;
    final data = _read(legacy);
    if (data == null) return;
    final savedAt = DateTime.tryParse('${data['saved_at'] ?? ''}') ?? DateTime.now();
    final id = 'd${savedAt.microsecondsSinceEpoch}';
    if (!_file(id).existsSync()) {
      _write(id, {...data, 'id': id});
    }
    legacy.deleteSync();
  }

  /// 저장해 둔 글 전부, 최근에 저장한 것부터. 깨진 파일은 뺀다.
  List<Map<String, dynamic>> list() {
    _migrateLegacy();
    if (!dir.existsSync()) return [];
    final out = <Map<String, dynamic>>[];
    for (final f in dir.listSync().whereType<File>().where((f) => f.path.endsWith('.json'))) {
      final data = _read(f);
      if (data != null && data['id'] is String) out.add(data);
    }
    out.sort((a, b) => '${b['saved_at'] ?? ''}'.compareTo('${a['saved_at'] ?? ''}'));
    return out;
  }

  /// 저장한 글. 없거나 깨졌으면 null.
  Map<String, dynamic>? load(String id) {
    _migrateLegacy();
    return _read(_file(id));
  }

  void save(String id, Map<String, dynamic> post, List<String> localImagePaths) {
    _write(id, {
      'id': id,
      'saved_at': DateTime.now().toIso8601String(),
      'local_image_paths': localImagePaths,
      'post': post,
    });
  }

  /// 임시 파일에 먼저 쓰고 바꿔 끼운다 (쓰는 도중 꺼져도 앞의 저장본이 깨지지 않게)
  void _write(String id, Map<String, dynamic> data) {
    dir.createSync(recursive: true);
    final file = _file(id);
    final tmp = File('${file.path}.tmp');
    tmp.writeAsStringSync(jsonEncode(data));
    if (file.existsSync()) file.deleteSync();
    tmp.renameSync(file.path);
  }

  void delete(String id) {
    final f = _file(id);
    if (f.existsSync()) f.deleteSync();
  }
}
