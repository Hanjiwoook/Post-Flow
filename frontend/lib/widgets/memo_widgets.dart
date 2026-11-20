import 'package:flutter/material.dart';

/// 메모 색: 내 메모는 파랑, 검수 지적은 주황
Color memoColor(Map memo) => memo['source'] == 'review' ? Colors.orange : Colors.blue;

String memoLabel(Map memo) {
  if (memo['source'] != 'review') return '내 메모';
  final kind = '${memo['kind'] ?? ''}'.trim();
  return kind.isEmpty ? '검수 지적' : '검수 지적 · $kind';
}

String memoStatusLabel(Map memo) {
  switch (memo['status']) {
    case 'proposed':
      return '안 받음';
    case 'approved':
      return '반영함';
    case 'rejected':
      return '거절함';
    default:
      return '';
  }
}

/// 메모를 쓰거나 고치는 창. 취소하면 null.
Future<String?> showMemoDialog(BuildContext context, {String initial = '', String quote = ''}) {
  return showDialog<String>(
    context: context,
    builder: (_) => _MemoDialog(initial: initial, quote: quote),
  );
}

// 입력 칸 controller는 창이 화면에서 완전히 사라질 때 정리한다
// (닫히는 애니메이션 중에도 칸을 그리므로, 결과를 받자마자 dispose하면 에러가 난다)
class _MemoDialog extends StatefulWidget {
  final String initial;
  final String quote;
  const _MemoDialog({required this.initial, required this.quote});

  @override
  State<_MemoDialog> createState() => _MemoDialogState();
}

class _MemoDialogState extends State<_MemoDialog> {
  late final TextEditingController _controller = TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.initial.isEmpty ? '메모 남기기' : '메모 고치기'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.quote.trim().isNotEmpty) ...[
              Text('“${widget.quote.trim()}”', style: const TextStyle(fontSize: 13, color: Colors.black54)),
              const SizedBox(height: 8),
            ],
            TextField(
              controller: _controller,
              autofocus: true,
              maxLines: null,
              decoration: const InputDecoration(hintText: '예: 이렇게 바꿔 줘, 이건 빼도 돼', border: OutlineInputBorder()),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('취소')),
        TextButton(
          onPressed: () => Navigator.pop(context, _controller.text.trim()),
          child: const Text('저장'),
        ),
      ],
    );
  }
}

/// 메모 한 개: 색 띠, 체크(AI에게 보낼지), 드래그한 부분, 메모 내용, 고치기·지우기.
/// [child]는 받은 안 등 아래에 덧붙일 내용 (6단계).
class MemoTile extends StatelessWidget {
  final Map memo;
  final ValueChanged<bool>? onChecked;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final Widget? child;

  const MemoTile({super.key, required this.memo, this.onChecked, this.onEdit, this.onDelete, this.child});

  @override
  Widget build(BuildContext context) {
    final color = memoColor(memo);
    final done = memo['status'] == 'approved' || memo['status'] == 'rejected';
    final quote = '${memo['quote'] ?? ''}'.trim();
    final status = memoStatusLabel(memo);
    return Opacity(
      opacity: done ? 0.55 : 1,
      child: Container(
        margin: const EdgeInsets.only(top: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.06),
          borderRadius: BorderRadius.circular(8),
          border: Border(left: BorderSide(color: color, width: 4)),
        ),
        padding: const EdgeInsets.fromLTRB(4, 2, 4, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              SizedBox(
                width: 32,
                height: 32,
                child: done
                    ? Icon(memo['status'] == 'approved' ? Icons.check_circle : Icons.cancel, size: 18, color: color)
                    : Checkbox(
                        value: memo['checked'] == true,
                        onChanged: onChecked == null ? null : (v) => onChecked!(v ?? false),
                        visualDensity: VisualDensity.compact,
                      ),
              ),
              Text(memoLabel(memo), style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.bold)),
              if (status.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Text(status, style: const TextStyle(fontSize: 11, color: Colors.black54)),
                ),
              const Spacer(),
              if (!done && onEdit != null)
                IconButton(
                  tooltip: '메모 고치기',
                  icon: const Icon(Icons.edit_outlined, size: 16),
                  visualDensity: VisualDensity.compact,
                  onPressed: onEdit,
                ),
              if (onDelete != null)
                IconButton(
                  tooltip: '메모 지우기',
                  icon: const Icon(Icons.close, size: 16),
                  visualDensity: VisualDensity.compact,
                  onPressed: onDelete,
                ),
            ]),
            Padding(
              padding: const EdgeInsets.only(left: 8, right: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (quote.isNotEmpty)
                    Text('“$quote”', style: const TextStyle(fontSize: 12, color: Colors.black54, fontStyle: FontStyle.italic)),
                  Text('${memo['comment'] ?? ''}', style: const TextStyle(fontSize: 13, height: 1.4)),
                  if (child != null) child!,
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 글 칸의 우클릭(길게 누르기) 메뉴에 [메모 남기기]를 더한다. 드래그한 글자를 onMemo로 넘긴다.
Widget memoContextMenu(BuildContext context, EditableTextState state, void Function(String quote) onMemo) {
  final value = state.textEditingValue;
  final selection = value.selection;
  final quote = selection.isValid && !selection.isCollapsed ? selection.textInside(value.text) : '';
  return AdaptiveTextSelectionToolbar.buttonItems(
    anchors: state.contextMenuAnchors,
    buttonItems: [
      ContextMenuButtonItem(
        label: '메모 남기기',
        onPressed: () {
          state.hideToolbar();
          onMemo(quote);
        },
      ),
      ...state.contextMenuButtonItems,
    ],
  );
}
