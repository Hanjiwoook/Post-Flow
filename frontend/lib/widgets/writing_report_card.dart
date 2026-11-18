import 'package:flutter/material.dart';

/// 형식 검사에서 지키지 못한 규칙 하나
class FailedRule {
  final String rule;
  final String detail;
  final bool isError; // error면 꼭 고칠 것, warning이면 참고
  const FailedRule(this.rule, this.detail, this.isError);
}

/// 작성 리포트 카드에 보여 줄 내용. /analyze 결과(generatedPost)에서 계산한다.
/// 화면과 나눠 둔 이유: 계산이 맞는지 flutter test로 확인하기 위해서다.
class WritingReport {
  final int ruleCount; // 검사한 규칙 수
  final List<FailedRule> failed; // 지키지 못한 규칙 (error 먼저)
  final List<String> needsCheck; // 사용자가 꼭 봐야 하는 메모 ('확인 필요')
  final List<String> otherNotes; // 나머지 작성 메모
  final String? costText; // 예: "claude-opus-5-5 · \$0.37 · 입력 28,559 / 출력 12,670 토큰"

  const WritingReport({
    required this.ruleCount,
    required this.failed,
    required this.needsCheck,
    required this.otherNotes,
    required this.costText,
  });

  bool get hasFormatCheck => ruleCount > 0;
}

String _comma(int n) => n.toString().replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');

WritingReport buildWritingReport(Map<String, dynamic> post) {
  // 형식 검사 (services/format_checker.py의 check_post 결과)
  final check = post['format_check'] as Map? ?? {};
  final results = (check['results'] as List? ?? []).whereType<Map>().toList();
  final failed = results
      .where((r) => r['passed'] != true)
      .map((r) => FailedRule('${r['rule'] ?? ''}', '${r['detail'] ?? ''}', r['severity'] == 'error'))
      .toList()
    ..sort((a, b) => (a.isError == b.isError) ? 0 : (a.isError ? -1 : 1));

  // 작성 메모: AI가 '확인 필요'라고 적은 것(예: 만족도와 재방문 의사)은 따로 눈에 띄게 보여 준다
  final notes = (post['writing_notes'] as List? ?? []).map((n) => '$n').where((n) => n.trim().isNotEmpty).toList();
  final needsCheck = notes.where((n) => n.contains('확인 필요')).toList();
  final otherNotes = notes.where((n) => !n.contains('확인 필요')).toList();

  // 비용 (서버가 추정한 값)
  String? costText;
  final usage = post['usage'] as Map?;
  if (usage != null && usage['model'] != null) {
    final cost = usage['cost_usd'];
    final parts = <String>['${usage['model']}'];
    if (cost is num) parts.add('\$${cost.toStringAsFixed(2)}');
    if (usage['input_tokens'] is int && usage['output_tokens'] is int) {
      parts.add('입력 ${_comma(usage['input_tokens'])} / 출력 ${_comma(usage['output_tokens'])} 토큰');
    }
    costText = parts.join(' · ');
  }

  return WritingReport(
    ruleCount: results.length,
    failed: failed,
    needsCheck: needsCheck,
    otherNotes: otherNotes,
    costText: costText,
  );
}

/// 편집 화면 맨 위의 작성 리포트 카드
class WritingReportCard extends StatelessWidget {
  final Map<String, dynamic> post;
  const WritingReportCard({super.key, required this.post});

  @override
  Widget build(BuildContext context) {
    final report = buildWritingReport(post);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: BorderSide(color: Colors.grey[300]!)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("📝 작성 리포트", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),

            // 1. 형식 검사
            if (!report.hasFormatCheck)
              const Text("형식 검사 결과가 없습니다 (예전에 만든 글)", style: TextStyle(color: Colors.grey, fontSize: 13))
            else if (report.failed.isEmpty)
              Text("✅ 형식 검사 ${report.ruleCount}개 규칙 모두 통과", style: const TextStyle(fontSize: 13))
            else ...[
              Text("형식 검사: ${report.ruleCount}개 중 ${report.failed.length}개를 지키지 못했어요",
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              ...report.failed.map((f) => _line(
                    f.isError ? Icons.error : Icons.warning_amber,
                    f.isError ? Colors.red : Colors.orange,
                    "${f.rule}: ${f.detail}",
                  )),
            ],

            // 2. 확인 필요 (항상 보이게)
            if (report.needsCheck.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: Colors.amber[50], borderRadius: BorderRadius.circular(10)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text("👀 확인해 주세요", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    ...report.needsCheck.map((n) => _line(Icons.help_outline, Colors.amber[800]!, n)),
                  ],
                ),
              ),
            ],

            // 3. 나머지 작성 메모 (접어 둠)
            if (report.otherNotes.isNotEmpty)
              Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: Text("AI 작성 메모 ${report.otherNotes.length}개", style: const TextStyle(fontSize: 13)),
                  children: report.otherNotes.map((n) => _line(Icons.notes, Colors.grey, n)).toList(),
                ),
              ),

            // 4. 비용
            if (report.costText != null) ...[
              const SizedBox(height: 8),
              Text(report.costText!, style: const TextStyle(color: Colors.grey, fontSize: 11)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _line(IconData icon, Color color, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Expanded(child: Text(text, style: const TextStyle(fontSize: 13, height: 1.4))),
          ],
        ),
      );
}
