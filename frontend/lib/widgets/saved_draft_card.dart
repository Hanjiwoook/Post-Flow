import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../providers/post_provider.dart' show DraftSaveState;

/// 홈 화면: 저장해 둔 작업 중인 글 하나 → [이어서 작업하기] / [지우기]
class SavedDraftCard extends StatelessWidget {
  final Map<String, dynamic> draft; // DraftStore.list()의 한 항목
  final VoidCallback onResume;
  final VoidCallback onDiscard;

  const SavedDraftCard({super.key, required this.draft, required this.onResume, required this.onDiscard});

  static String savedAtLabel(String? iso) {
    final t = DateTime.tryParse(iso ?? '');
    if (t == null) return '';
    String two(int n) => n.toString().padLeft(2, '0');
    return '${t.month}/${t.day} ${two(t.hour)}:${two(t.minute)} 저장';
  }

  @override
  Widget build(BuildContext context) {
    final post = Map<String, dynamic>.from(draft['post'] as Map);
    final memos = List<dynamic>.from(post['memos'] ?? []);
    final left = memos.where((m) => m is Map && (m['status'] == 'draft' || m['status'] == 'proposed')).length;
    final title = '${post['title'] ?? ''}'.trim();
    return Card(
      elevation: 0,
      color: Colors.indigo[50],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title.isEmpty ? '제목 없음' : title, style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 4),
            Text(
              [
                savedAtLabel(draft['saved_at'] as String?),
                if (memos.isNotEmpty) '메모 ${memos.length}개 (남은 것 $left개)',
                if (post['review'] != null) '검수 받음',
              ].where((s) => s.isNotEmpty).join(' · '),
              style: const TextStyle(fontSize: 14, color: Colors.black54),
            ),
            const SizedBox(height: 10),
            Row(children: [
              FilledButton.icon(
                onPressed: onResume,
                icon: const Icon(Icons.play_arrow),
                label: const Text('이어서 작업하기'),
              ),
              const SizedBox(width: 8),
              TextButton(onPressed: onDiscard, child: const Text('지우기')),
            ]),
          ],
        ),
      ),
    );
  }
}

/// 편집 화면 위: 작업 중인 글이 자동 저장됐는지 보여 준다 ("✓ 자동 저장됨 14:32" / "⚠ 저장 실패").
/// 아직 저장한 적이 없으면 아무것도 보이지 않는다.
class DraftSaveLabel extends StatelessWidget {
  final ValueListenable<DraftSaveState?> state;
  const DraftSaveLabel({super.key, required this.state});

  static String timeLabel(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<DraftSaveState?>(
      valueListenable: state,
      builder: (context, s, _) {
        if (s == null) return const SizedBox.shrink();
        final text = s.ok ? '✓ 자동 저장됨 ${timeLabel(s.at)}' : '⚠ 저장 실패 ${timeLabel(s.at)}';
        return Tooltip(
          message: s.ok
              ? '고칠 때마다 노트북에 자동으로 저장돼요. 앱을 꺼도 홈의 [이어서 작업하기]로 다시 열 수 있어요.'
              : '노트북에 저장하지 못했어요: ${s.error}',
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Center(
              child: Text(text, style: TextStyle(fontSize: 13, color: s.ok ? Colors.green[700] : Colors.red[700])),
            ),
          ),
        );
      },
    );
  }
}
