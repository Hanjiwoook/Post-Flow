import 'package:flutter/material.dart';
import '../providers/memo_logic.dart';

/// 메모 색: 내 메모는 파랑, 검수 지적은 주황, 검수 질문 답은 보라
Color memoColor(Map memo) {
  switch (memo['source']) {
    case 'review':
      return Colors.orange;
    case 'answer':
      return Colors.purple;
    default:
      return Colors.blue;
  }
}

String memoLabel(Map memo) {
  if (memo['source'] == 'answer') return '질문 답';
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
Future<String?> showMemoDialog(BuildContext context,
    {String initial = '', String quote = '', String? title, String? hint}) {
  return showDialog<String>(
    context: context,
    builder: (_) => _MemoDialog(initial: initial, quote: quote, title: title, hint: hint),
  );
}

// 입력 칸 controller는 창이 화면에서 완전히 사라질 때 정리한다
// (닫히는 애니메이션 중에도 칸을 그리므로, 결과를 받자마자 dispose하면 에러가 난다)
class _MemoDialog extends StatefulWidget {
  final String initial;
  final String quote;
  final String? title;
  final String? hint;
  const _MemoDialog({required this.initial, required this.quote, this.title, this.hint});

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
      title: Text(widget.title ?? (widget.initial.isEmpty ? '메모 남기기' : '메모 고치기')),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.quote.trim().isNotEmpty) ...[
              Text('“${widget.quote.trim()}”', style: const TextStyle(fontSize: 16, color: Colors.black54)),
              const SizedBox(height: 8),
            ],
            TextField(
              controller: _controller,
              autofocus: true,
              maxLines: null,
              decoration: InputDecoration(
                  hintText: widget.hint ?? '예: 이렇게 바꿔 줘, 이건 빼도 돼', border: const OutlineInputBorder()),
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
class MemoTile extends StatefulWidget {
  final Map memo;
  final ValueChanged<bool>? onChecked;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final Widget? child;

  const MemoTile({super.key, required this.memo, this.onChecked, this.onEdit, this.onDelete, this.child});

  @override
  State<MemoTile> createState() => _MemoTileState();
}

class _MemoTileState extends State<MemoTile> {
  bool _showSuggestion = false; // 검수 메모의 '고칠 방향'은 눌러야 펼친다 (메모가 길어지지 않게)

  @override
  Widget build(BuildContext context) {
    final memo = widget.memo;
    final onChecked = widget.onChecked;
    final onEdit = widget.onEdit;
    final onDelete = widget.onDelete;
    final child = widget.child;
    final suggestion = '${memo['suggestion'] ?? ''}'.trim();
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
                width: 40,
                height: 40,
                child: done
                    ? Icon(memo['status'] == 'approved' ? Icons.check_circle : Icons.cancel, size: 22, color: color)
                    : Checkbox(
                        value: memo['checked'] == true,
                        onChanged: onChecked == null ? null : (v) => onChecked(v ?? false),
                        visualDensity: VisualDensity.compact,
                      ),
              ),
              Text(memoLabel(memo), style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.bold)),
              if (status.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Text(status, style: const TextStyle(fontSize: 13, color: Colors.black54)),
                ),
              const Spacer(),
              if (!done && onEdit != null)
                IconButton(
                  tooltip: '메모 고치기',
                  icon: const Icon(Icons.edit_outlined, size: 20),
                  visualDensity: VisualDensity.compact,
                  onPressed: onEdit,
                ),
              if (onDelete != null)
                IconButton(
                  tooltip: '메모 지우기',
                  icon: const Icon(Icons.close, size: 20),
                  visualDensity: VisualDensity.compact,
                  onPressed: onDelete,
                ),
            ]),
            Padding(
              padding: const EdgeInsets.only(left: 8, right: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 드래그한 부분은 글 안에도 칠해져 있으므로 두 줄까지만
                  if (quote.isNotEmpty)
                    Text('“$quote”',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 14, color: Colors.black54, fontStyle: FontStyle.italic)),
                  Text('${memo['comment'] ?? ''}', style: const TextStyle(fontSize: 16, height: 1.4)),
                  if (suggestion.isNotEmpty) ...[
                    if (_showSuggestion)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text('→ $suggestion', style: const TextStyle(fontSize: 15, height: 1.4, color: Colors.black87)),
                      ),
                    TextButton(
                      onPressed: () => setState(() => _showSuggestion = !_showSuggestion),
                      style: TextButton.styleFrom(padding: EdgeInsets.zero, visualDensity: VisualDensity.compact),
                      child: Text(_showSuggestion ? '고칠 방향 접기' : '고칠 방향 보기', style: const TextStyle(fontSize: 14)),
                    ),
                  ],
                  if (child != null) child,
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

/// 받은 안: 바뀌는 블록마다 원래 → 고친 글(줄 단위 비교), AI 의견, 코드 검증 메모, [승인]·[거절]·[답장해서 다시 요청].
/// [stale]이 있으면 글이 그 사이 바뀐 것이라 승인을 막는다.
class ProposalView extends StatelessWidget {
  final Map memo;
  final List<int> stale;
  final VoidCallback onApprove;
  final VoidCallback onReject;
  final VoidCallback onReply;

  const ProposalView({
    super.key,
    required this.memo,
    required this.stale,
    required this.onApprove,
    required this.onReject,
    required this.onReply,
  });

  @override
  Widget build(BuildContext context) {
    final p = memo['proposal'] as Map;
    final memoIndex = memo['block_index'] as int;
    final edits = List<dynamic>.from(p['edits'] ?? []);
    final opinion = '${p['opinion'] ?? ''}'.trim();
    final notes = List<dynamic>.from(p['notes'] ?? []);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (edits.isEmpty)
            const Text('고친 안 없음', style: TextStyle(fontSize: 14, color: Colors.black54)),
          for (final e in edits) _editBox(e as Map, memoIndex),
          if (opinion.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('💬 $opinion', style: const TextStyle(fontSize: 16, height: 1.4)),
            ),
          for (final n in notes)
            Text('(코드 검증) $n', style: const TextStyle(fontSize: 13, color: Colors.black45)),
          if (stale.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('글이 그 사이 바뀌어서 이 안은 넣을 수 없어요. 답장해서 다시 요청해 주세요.',
                  style: TextStyle(fontSize: 14, color: Colors.red[700])),
            ),
          const SizedBox(height: 6),
          Wrap(spacing: 8, runSpacing: 4, children: [
            FilledButton.tonal(
              onPressed: stale.isEmpty ? onApprove : null,
              child: Text(edits.isEmpty ? '확인' : '승인'),
            ),
            OutlinedButton(onPressed: onReject, child: const Text('거절')),
            TextButton.icon(onPressed: onReply, icon: const Icon(Icons.reply, size: 20), label: const Text('답장해서 다시 요청')),
          ]),
        ],
      ),
    );
  }

  Widget _editBox(Map e, int memoIndex) {
    final index = e['block_index'] as int;
    final diff = lineDiff('${e['before'] ?? ''}', '${e['after'] ?? ''}');
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.grey[300]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(editPlaceLabel(index, memoIndex),
              style: const TextStyle(fontSize: 13, color: Colors.indigo, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          for (final d in diff) _diffLine(d.key, d.value),
        ],
      ),
    );
  }

  Widget _diffLine(String op, String line) {
    final text = line.isEmpty ? ' ' : line;
    switch (op) {
      case '-':
        return Container(
          width: double.infinity,
          color: Colors.red[50],
          child: Text('− $text',
              style: TextStyle(fontSize: 16, height: 1.5, color: Colors.red[800], decoration: TextDecoration.lineThrough)),
        );
      case '+':
        return Container(
          width: double.infinity,
          color: Colors.green[50],
          child: Text('+ $text', style: TextStyle(fontSize: 16, height: 1.5, color: Colors.green[900])),
        );
      default:
        return Text('   $text', style: const TextStyle(fontSize: 16, height: 1.5, color: Colors.black54));
    }
  }
}

/// 드래그한 부분(메모의 quote)을 글 안에 메모 색 배경으로 칠하는 입력 칸 controller.
/// highlights는 화면을 그릴 때마다 정해 주고, 같은 글자가 여러 번 나오면 첫 번째만 칠한다.
class HighlightTextController extends TextEditingController {
  HighlightTextController({super.text});

  List<MapEntry<String, Color>> highlights = const [];

  @override
  TextSpan buildTextSpan({required BuildContext context, TextStyle? style, required bool withComposing}) {
    // 한글 조합 중에는 밑줄 표시를 그대로 쓰도록 기본 동작을 따른다
    if (highlights.isEmpty || (withComposing && value.isComposingRangeValid)) {
      return super.buildTextSpan(context: context, style: style, withComposing: withComposing);
    }
    final ranges = highlightRanges(text, highlights);
    if (ranges.isEmpty) return TextSpan(style: style, text: text);
    final children = <TextSpan>[];
    var pos = 0;
    for (final r in ranges) {
      if (r.start > pos) children.add(TextSpan(text: text.substring(pos, r.start)));
      children.add(TextSpan(text: text.substring(r.start, r.end), style: TextStyle(backgroundColor: r.color.withOpacity(0.22))));
      pos = r.end;
    }
    if (pos < text.length) children.add(TextSpan(text: text.substring(pos)));
    return TextSpan(style: style, children: children);
  }
}

class HighlightRange {
  final int start;
  final int end;
  final Color color;
  const HighlightRange(this.start, this.end, this.color);
}

/// 칠할 구간: 글에서 찾은 quote의 첫 위치, 앞 구간과 겹치는 것은 뺀다
List<HighlightRange> highlightRanges(String text, List<MapEntry<String, Color>> highlights) {
  final found = <HighlightRange>[];
  for (final h in highlights) {
    final q = h.key;
    if (q.isEmpty) continue;
    final at = text.indexOf(q);
    if (at >= 0) found.add(HighlightRange(at, at + q.length, h.value));
  }
  found.sort((a, b) => a.start.compareTo(b.start));
  final out = <HighlightRange>[];
  for (final r in found) {
    if (out.isEmpty || r.start >= out.last.end) out.add(r);
  }
  return out;
}

/// 블록 글 입력 칸. 승인 등으로 글이 밖에서 바뀌면 칸도 따라 바뀌고, 드래그한 부분을 칠한다.
class MemoTextField extends StatefulWidget {
  final String value;
  final List<MapEntry<String, Color>> highlights;
  final ValueChanged<String> onChanged;
  final EditableTextContextMenuBuilder? contextMenuBuilder;

  const MemoTextField({
    super.key,
    required this.value,
    required this.highlights,
    required this.onChanged,
    this.contextMenuBuilder,
  });

  @override
  State<MemoTextField> createState() => _MemoTextFieldState();
}

class _MemoTextFieldState extends State<MemoTextField> {
  late final HighlightTextController _controller = HighlightTextController(text: widget.value)
    ..highlights = widget.highlights;

  @override
  void didUpdateWidget(MemoTextField old) {
    super.didUpdateWidget(old);
    _controller.highlights = widget.highlights; // 곧 다시 그리므로 알림은 필요 없다
    if (widget.value != _controller.text) _controller.text = widget.value;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: _controller,
      maxLines: null,
      decoration: const InputDecoration(border: InputBorder.none, isDense: true),
      style: const TextStyle(fontSize: 17, height: 1.6),
      onChanged: widget.onChanged,
      contextMenuBuilder: widget.contextMenuBuilder,
    );
  }
}

/// 노트북처럼 넓은 화면이면 글 | 메모를 나란히, 좁으면 메모를 글 아래에 둔다.
/// 블로그 글은 한 줄이 짧아서(폰 기준 15~20자) 글 칸을 넓히면 글은 왼쪽 끝, 메모는 오른쪽 끝으로 멀어진다.
/// 그래서 글 칸은 글 길이에 맞는 폭으로 두고, 메모를 바로 옆에 붙여 남은 폭을 쓰게 한다.
const double memoTextWidth = 560;
const double memoSideMinWidth = 900;

/// 편집 화면 전체 최대 폭 (큰 화면에서는 가운데에 둔다)
const double editorMaxWidth = 1240;

Widget textWithMemoSide({required Widget text, required Widget memos}) {
  return LayoutBuilder(builder: (context, c) {
    if (c.maxWidth < memoSideMinWidth) {
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [text, memos]);
    }
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(width: memoTextWidth, child: text),
      Expanded(
        child: Container(
          decoration: BoxDecoration(border: Border(left: BorderSide(color: Colors.grey[200]!))),
          child: memos,
        ),
      ),
    ]);
  });
}

/// 편집 화면 안내: 메모로 고치는 방법 ([AI에게 확인]이 무엇을 하는지)
class MemoGuideBanner extends StatelessWidget {
  final int pending;
  const MemoGuideBanner({super.key, required this.pending});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: Colors.blue[50], borderRadius: BorderRadius.circular(10)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.lightbulb_outline, color: Colors.blue),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            '고치고 싶은 곳이 있으면 글을 드래그한 뒤 우클릭 → [메모 남기기]로 원하는 내용을 적어 주세요 '
            '(예: "이렇게 바꿔 줘", "이건 빼도 돼"). 검수 지적은 주황 메모로 미리 달려 있어요.\n'
            '메모를 다 적었으면 위의 [AI에게 확인]을 눌러 주세요. 메모마다 고친 안을 보여 드리고, '
            '마음에 드는 안만 [승인]하면 글에 들어가요.'
            '${pending > 0 ? '\n지금 AI에게 보낼 메모: $pending개' : ''}',
            style: const TextStyle(fontSize: 15, height: 1.5),
          ),
        ),
      ]),
    );
  }
}
