import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/memo_logic.dart' show issuesNotAsMemo;
import '../providers/post_provider.dart';

/// 검수 지적이 글의 어디인지 사람이 읽을 수 있게 만든다.
/// 서버(post_reviewer.render_draft)는 블록 번호를 0부터 매기고, 제목은 -1, 글 전체는 -2를 쓴다.
String issueLocation(int blockIndex, List<dynamic> blocks) {
  if (blockIndex == -1) return '제목';
  if (blockIndex == -2) return '글 전체';
  if (blockIndex < 0 || blockIndex >= blocks.length) return '$blockIndex번 블록';
  final b = blocks[blockIndex] as Map;
  final value = '${b['value'] ?? ''}'.replaceAll('\n', ' ').trim();
  final snippet = value.length > 18 ? '${value.substring(0, 18)}…' : value;
  switch (b['type']) {
    case 'image':
      return '사진 묶음';
    case 'map':
      return '지도';
    case 'quote':
      return '인용구 · $snippet';
    default:
      return '글 · $snippet';
  }
}

/// 답을 쓴 질문만 모은다. 답하지 않은 질문은 건너뛴다 (고쳐쓰기 AI가 지어내지 않도록).
List<Map<String, String>> collectAnswers(List<dynamic> questions, Map<int, String> answers) {
  final out = <Map<String, String>>[];
  for (var i = 0; i < questions.length; i++) {
    final answer = (answers[i] ?? '').trim();
    if (answer.isEmpty) continue;
    out.add({'question': '${(questions[i] as Map)['question'] ?? ''}', 'answer': answer});
  }
  return out;
}

/// 파워블로거 검수 결과 화면: 총평, 점수, 지적, 빠진 정보, 질문 → [반영해서 고쳐쓰기]
class ReviewScreen extends StatefulWidget {
  const ReviewScreen({super.key});

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  final Map<int, TextEditingController> _answerControllers = {};

  // 답 칸: 저장해 둔 답(review_answers)으로 채우고, 고칠 때마다 저장한다 (메모 고치기의 사실 근거로 쓴다)
  TextEditingController _controllerFor(int i, List<dynamic> questions, PostProvider provider) {
    return _answerControllers.putIfAbsent(i, () {
      final question = '${(questions[i] as Map)['question'] ?? ''}';
      final saved = List<dynamic>.from(provider.generatedPost?['review_answers'] ?? [])
          .cast<Map>()
          .where((a) => a['question'] == question)
          .map((a) => '${a['answer'] ?? ''}')
          .firstOrNull;
      final c = TextEditingController(text: saved ?? '');
      c.addListener(() => _saveAnswers(questions, provider));
      return c;
    });
  }

  void _saveAnswers(List<dynamic> questions, PostProvider provider) {
    provider.setReviewAnswers(collectAnswers(questions, _answerControllers.map((i, c) => MapEntry(i, c.text))));
  }

  @override
  void dispose() {
    for (final c in _answerControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _reReview(PostProvider provider) async {
    try {
      await provider.requestReview();
      // 새 검수는 질문이 다르므로 답 칸과 저장한 답을 비운다
      for (final c in _answerControllers.values) {
        c.dispose();
      }
      _answerControllers.clear();
      provider.setReviewAnswers([]);
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('검수 실패: $e')));
    }
  }

  Future<void> _revise(PostProvider provider, List<dynamic> questions) async {
    final answers = collectAnswers(questions, _answerControllers.map((i, c) => MapEntry(i, c.text)));
    try {
      await provider.requestRevision(answers);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('고쳐쓰기 실패: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<PostProvider>(context);
    final review = provider.review;
    final blocks = List<dynamic>.from(provider.generatedPost?['blocks'] ?? []);
    final busy = provider.isReviewing || provider.isRevising;

    return Scaffold(
      appBar: AppBar(
        title: const Text('🔍 파워블로거 검수'),
        actions: [
          IconButton(
            tooltip: '다시 검수 받기',
            onPressed: busy ? null : () => _reReview(provider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Stack(
        children: [
          if (review == null)
            const Center(child: Text('검수 결과가 없습니다'))
          else
            _buildBody(review, blocks, provider),
          if (busy)
            Container(
              color: Colors.black26,
              child: Center(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      const CircularProgressIndicator(),
                      const SizedBox(height: 16),
                      Text(provider.isRevising ? '고쳐 쓰는 중이에요 (1분 정도 걸려요)' : '검수 중이에요 (30초 정도 걸려요)'),
                    ]),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBody(Map<String, dynamic> review, List<dynamic> blocks, PostProvider provider) {
    final scores = List<dynamic>.from(review['scores'] ?? []);
    final allIssues = List<dynamic>.from(review['issues'] ?? []);
    // 블록에 달 수 있는 지적은 편집 화면에 메모로 달았다. 여기에는 글 전체 지적처럼 메모로 못 옮긴 것만 남긴다.
    final issues = issuesNotAsMemo(review, blocks);
    final asMemo = allIssues.length - issues.length;
    final missing = List<dynamic>.from(review['missing_info'] ?? []);
    final questions = List<dynamic>.from(review['questions'] ?? []);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 120),
      children: [
        // 1. 총평
        Card(
          elevation: 0,
          color: Colors.indigo[50],
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text('${review['overall'] ?? ''}', style: const TextStyle(fontSize: 14, height: 1.5)),
          ),
        ),
        const SizedBox(height: 16),

        // 2. 점수
        _title('점수'),
        ...scores.map((s) => _scoreRow(s as Map)),
        const SizedBox(height: 16),

        // 3. 지적 사항
        if (asMemo > 0) ...[
          Card(
            elevation: 0,
            color: Colors.orange[50],
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text('지적 $asMemo개는 편집 화면의 해당 글에 주황 메모로 달았어요. '
                  '글을 보면서 확인하고 [AI에게 확인]으로 고친 안을 받을 수 있어요.',
                  style: const TextStyle(fontSize: 13, height: 1.4)),
            ),
          ),
          const SizedBox(height: 16),
        ],
        if (issues.isNotEmpty) ...[
          _title('글 전체 지적 ${issues.length}개'),
          ...issues.map((it) => _issueCard(it as Map, blocks)),
          const SizedBox(height: 16),
        ],

        // 4. 빠진 정보
        if (missing.isNotEmpty) ...[
          _title('빠진 정보'),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: missing.map((m) => Chip(label: Text('$m', style: const TextStyle(fontSize: 12)))).toList(),
          ),
          const SizedBox(height: 16),
        ],

        // 5. 질문
        if (questions.isNotEmpty) ...[
          _title('알려 주시면 글이 좋아져요 (쓴 답은 고쳐쓰기와 메모 고치기의 근거로 써요)'),
          for (var i = 0; i < questions.length; i++) _questionCard(i, questions, provider),
        ],

        const SizedBox(height: 16),
        // 6. 고쳐쓰기
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: provider.hasRevised || provider.isRevising ? null : () => _revise(provider, questions),
            icon: const Icon(Icons.edit_note),
            label: Text(provider.hasRevised ? '이미 한 번 고쳐 썼어요 (고쳐쓰기는 한 번만)' : '✍️ 반영해서 고쳐쓰기'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.indigo,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ),
        if (review['usage'] is Map && review['usage']['cost_usd'] is num)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('검수 비용 ${review['usage']['model']} · \$${(review['usage']['cost_usd'] as num).toStringAsFixed(2)}',
                style: const TextStyle(color: Colors.grey, fontSize: 11)),
          ),
      ],
    );
  }

  Widget _title(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      );

  Widget _scoreRow(Map s) {
    final score = (s['score'] is int) ? s['score'] as int : 0;
    final color = score >= 4 ? Colors.green : (score == 3 ? Colors.orange : Colors.red);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            SizedBox(width: 90, child: Text('${s['criterion'] ?? ''}', style: const TextStyle(fontSize: 13))),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(value: score / 5, minHeight: 8, color: color, backgroundColor: Colors.grey[200]),
              ),
            ),
            const SizedBox(width: 8),
            Text('$score/5', style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.bold)),
          ]),
          if ('${s['comment'] ?? ''}'.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 90, top: 2),
              child: Text('${s['comment']}', style: const TextStyle(fontSize: 12, color: Colors.black54)),
            ),
        ],
      ),
    );
  }

  Widget _issueCard(Map it, List<dynamic> blocks) {
    final where = issueLocation(it['block_index'] is int ? it['block_index'] as int : -2, blocks);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: Colors.grey[300]!)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: Colors.orange[50], borderRadius: BorderRadius.circular(6)),
                child: Text('${it['kind'] ?? ''}', style: TextStyle(fontSize: 11, color: Colors.orange[900])),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(where, style: const TextStyle(fontSize: 12, color: Colors.indigo), overflow: TextOverflow.ellipsis)),
            ]),
            const SizedBox(height: 6),
            Text('${it['problem'] ?? ''}', style: const TextStyle(fontSize: 13, height: 1.4)),
            const SizedBox(height: 4),
            Text('→ ${it['suggestion'] ?? ''}', style: const TextStyle(fontSize: 12, color: Colors.black54, height: 1.4)),
          ],
        ),
      ),
    );
  }

  Widget _questionCard(int i, List<dynamic> questions, PostProvider provider) {
    final q = questions[i] as Map;
    final controller = _controllerFor(i, questions, provider);
    final examples = List<dynamic>.from(q['example_answers'] ?? []);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      color: Colors.amber[50],
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Q${i + 1}. ${q['question'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            if ('${q['reason'] ?? ''}'.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text('${q['reason']}', style: const TextStyle(fontSize: 12, color: Colors.black54)),
              ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: examples
                  .map((a) => ActionChip(
                        label: Text('$a', style: const TextStyle(fontSize: 12)),
                        onPressed: () => setState(() => controller.text = '$a'),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              maxLines: null,
              decoration: const InputDecoration(
                hintText: '직접 쓰거나 위의 예시를 누르세요',
                isDense: true,
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(),
              ),
              style: const TextStyle(fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}
