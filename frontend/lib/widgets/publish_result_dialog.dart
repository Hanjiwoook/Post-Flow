import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 발행 상태를 가져오는 함수. 앱에서는 ApiService.getPublishStatus, 테스트에서는 가짜 함수를 넣는다.
typedef FetchPublishStatus = Future<Map<String, dynamic>> Function(int postId);

/// 로그인이 없거나 만료됐을 때 안내할 명령 (backend/app/services/automation/naver_session.py).
/// 저장소 맨 위 폴더(post-flow)에서 붙여 넣는 한 줄 (PowerShell·bash 둘 다 `;`로 이어 실행된다).
const saveLoginCommand = 'cd backend; venv/Scripts/python -X utf8 -m app.services.automation.naver_session';

/// 발행 결과 창 (6-4, 11/19).
/// [발행]을 누른 뒤 열려서, 발행이 끝날 때까지 몇 초마다 서버에 상태를 묻고
/// 진행 단계 → 결과(임시저장 완료 + 폰에서 확인할 것 / 실패 이유)를 보여준다.
class PublishResultDialog extends StatefulWidget {
  final List<int> postIds;
  final FetchPublishStatus fetchStatus;
  final Duration interval;

  const PublishResultDialog({
    super.key,
    required this.postIds,
    required this.fetchStatus,
    this.interval = const Duration(seconds: 3),
  });

  @override
  State<PublishResultDialog> createState() => _PublishResultDialogState();
}

class _PublishResultDialogState extends State<PublishResultDialog> {
  final Map<int, Map<String, dynamic>> _statuses = {};
  final Set<int> _unreachable = {}; // 마지막 질문에 서버가 답하지 않은 발행
  Timer? _timer;

  bool _isDone(int id) {
    final s = _statuses[id]?['status'];
    return s == 'SUCCESS' || s == 'FAIL';
  }

  bool get _allDone => widget.postIds.every(_isDone);

  @override
  void initState() {
    super.initState();
    _poll();
    _timer = Timer.periodic(widget.interval, (_) => _poll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _poll() async {
    for (final id in widget.postIds) {
      if (_isDone(id)) continue;
      try {
        final status = await widget.fetchStatus(id);
        if (!mounted) return;
        setState(() {
          _statuses[id] = status;
          _unreachable.remove(id);
        });
      } catch (_) {
        // 서버가 잠깐 답하지 않아도 발행은 서버에서 계속된다. 다음 차례에 다시 묻는다.
        if (!mounted) return;
        setState(() => _unreachable.add(id));
      }
    }
    if (_allDone) _timer?.cancel();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(_allDone ? '발행 결과' : '발행하는 중'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final id in widget.postIds) _buildOne(id),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(_allDone ? '닫기' : '닫기 (발행은 계속돼요)'),
        ),
      ],
    );
  }

  Widget _buildOne(int id) {
    final s = _statuses[id];
    final platform = s?['platform'] == 'TISTORY' ? '티스토리' : '네이버';
    final header = widget.postIds.length > 1
        ? Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(platform, style: const TextStyle(fontWeight: FontWeight.bold)),
          )
        : const SizedBox.shrink();

    Widget body;
    if (s == null || s['status'] == 'PROCESSING') {
      body = _buildProgress(s?['step'] as String?, _unreachable.contains(id));
    } else if (s['status'] == 'SUCCESS') {
      body = _buildSuccess(List<String>.from(s['problems'] ?? const []));
    } else {
      body = _buildFailure(s['error_code'] as String?, s['fail_reason'] as String?);
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [header, body]),
    );
  }

  Widget _buildProgress(String? step, bool unreachable) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          const SizedBox(width: 12),
          Expanded(child: Text(step ?? '발행 준비 중')),
        ]),
        const SizedBox(height: 8),
        Text(
          unreachable
              ? '서버에 연결하지 못했어요. 잠시 뒤 다시 확인할게요.'
              : '사진을 올리느라 몇 분 걸릴 수 있어요. 열린 Chrome 창은 건드리지 말아 주세요.',
          style: TextStyle(fontSize: 12, color: unreachable ? Colors.orange[800] : Colors.grey[600]),
        ),
      ],
    );
  }

  Widget _buildSuccess(List<String> problems) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(children: [
          Icon(Icons.check_circle, color: Colors.green),
          SizedBox(width: 8),
          Text('임시저장 완료', style: TextStyle(fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 8),
        if (problems.isEmpty)
          const Text('자가 검사에서 고칠 것이 없었어요. 네이버 임시저장 글을 열어 확인하고 발행해 주세요.')
        else ...[
          Text('자가 검사에서 고칠 것 ${problems.length}개를 찾았어요. 임시저장 글에서 확인해 주세요.'),
          const SizedBox(height: 6),
          for (final p in problems)
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('• '),
                Expanded(child: Text(p)),
              ]),
            ),
        ],
      ],
    );
  }

  Widget _buildFailure(String? errorCode, String? reason) {
    final loginRequired = errorCode == 'LOGIN_REQUIRED';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const Icon(Icons.error, color: Colors.red),
          const SizedBox(width: 8),
          Text(loginRequired ? '네이버 로그인이 필요해요' : '발행 실패', style: const TextStyle(fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 8),
        Text(reason ?? '이유를 알 수 없어요. 서버 로그를 확인해 주세요.'),
        if (loginRequired) ...[
          const SizedBox(height: 8),
          const Text("터미널에서 아래 명령으로 로그인을 저장한 뒤('로그인 상태 유지' 체크) 다시 발행해 주세요."),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(8),
            color: Colors.grey[200],
            child: const SelectableText(saveLoginCommand, style: TextStyle(fontFamily: 'monospace', fontSize: 12)),
          ),
          TextButton.icon(
            onPressed: () => Clipboard.setData(const ClipboardData(text: saveLoginCommand)),
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('명령 복사'),
          ),
        ],
      ],
    );
  }
}
