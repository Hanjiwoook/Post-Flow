import 'package:flutter/material.dart';

/// 홈 화면: 저장해 둔 작업 중인 글 → [이어서 작업하기] / [지우기]
class SavedDraftCard extends StatelessWidget {
  final Map<String, dynamic> draft; // DraftStore.load() 결과
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
            const Text('✏️ 작업 중인 글', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
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
