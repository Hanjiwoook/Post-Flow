import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 네이버 글 하나에 붙일 수 있는 태그 수 (백엔드 prompt_builder.MAX_TAGS와 같다)
const int maxTags = 30;

/// 태그를 네이버에 넣을 모양으로: # 과 띄어쓰기를 빼고, 빈 것·중복을 지운다. 최대 maxTags개.
/// (백엔드 post_writer.clean_tags와 같은 규칙. 앱에서 직접 더한 태그도 같은 모양이 되게 한다)
List<String> cleanTags(Iterable<String> tags) {
  final out = <String>[];
  for (final tag in tags) {
    final t = tag.replaceAll('#', '').replaceAll(RegExp(r'\s+'), '');
    if (t.isEmpty || out.contains(t)) continue;
    out.add(t);
  }
  return out.take(maxTags).toList();
}

/// 편집 화면 맨 아래: AI가 만든 태그를 보고 지우거나 더한다. [태그 복사]는 발행 창에 직접 붙여 넣을 때 쓴다.
class TagEditor extends StatefulWidget {
  final List<String> tags;
  final ValueChanged<List<String>> onChanged;
  const TagEditor({super.key, required this.tags, required this.onChanged});

  @override
  State<TagEditor> createState() => _TagEditorState();
}

class _TagEditorState extends State<TagEditor> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  // 쉼표나 띄어쓰기로 여러 개를 한 번에 넣을 수 있다 ("#하남맛집 #초마" 붙여 넣기 등)
  void _add() {
    final added = _input.text.split(RegExp(r'[,\s]+'));
    widget.onChanged(cleanTags([...widget.tags, ...added]));
    _input.clear();
  }

  @override
  Widget build(BuildContext context) {
    final tags = widget.tags;
    final full = tags.length >= maxTags;
    return Card(
      elevation: 0,
      color: Colors.grey[100],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Text('🏷️ 태그 ${tags.length}개', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(width: 8),
              const Expanded(
                child: Text('네이버 글 아래에 붙어요 (최대 30개)', style: TextStyle(fontSize: 13, color: Colors.black54)),
              ),
              TextButton.icon(
                onPressed: tags.isEmpty
                    ? null
                    : () {
                        Clipboard.setData(ClipboardData(text: tags.map((t) => '#$t').join(' ')));
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('태그를 복사했어요')));
                      },
                icon: const Icon(Icons.copy, size: 18),
                label: const Text('태그 복사'),
              ),
            ]),
            const SizedBox(height: 8),
            if (tags.isEmpty)
              const Text('태그가 없어요. 아래에서 직접 넣을 수 있어요.', style: TextStyle(fontSize: 13, color: Colors.black54)),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final t in tags)
                  InputChip(
                    label: Text('#$t', style: const TextStyle(fontSize: 13)),
                    onDeleted: () => widget.onChanged(tags.where((x) => x != t).toList()),
                    deleteButtonTooltipMessage: '태그 지우기',
                  ),
              ],
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _input,
              enabled: !full,
              onSubmitted: (_) => _add(),
              decoration: InputDecoration(
                hintText: full ? '태그는 30개까지예요' : '태그 더하기 (Enter, 쉼표로 여러 개)',
                isDense: true,
                filled: true,
                fillColor: Colors.white,
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(icon: const Icon(Icons.add), onPressed: full ? null : _add),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
