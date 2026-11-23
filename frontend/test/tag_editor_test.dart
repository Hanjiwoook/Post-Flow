import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/widgets/tag_editor.dart';

void main() {
  test('cleanTags: # 과 띄어쓰기를 빼고, 빈 것·중복을 지우고, 30개까지', () {
    expect(cleanTags(['#하남 맛집', '하남맛집', ' ', '초마', '#초마']), ['하남맛집', '초마']);
    expect(cleanTags([for (var i = 0; i < 40; i++) '태그$i']).length, maxTags);
  });

  testWidgets('태그를 보여 주고, 지우고, 여러 개를 한 번에 더한다', (tester) async {
    var tags = ['하남맛집', '초마'];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: StatefulBuilder(
          builder: (context, setState) => TagEditor(tags: tags, onChanged: (t) => setState(() => tags = t)),
        ),
      ),
    ));
    expect(find.text('🏷️ 태그 2개'), findsOneWidget);
    expect(find.text('#하남맛집'), findsOneWidget);

    await tester.tap(find.byTooltip('태그 지우기').first);
    await tester.pump();
    expect(tags, ['초마']);

    await tester.enterText(find.byType(TextField), '#초마짬뽕, 하남 중식  초마');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();
    expect(tags, ['초마', '초마짬뽕', '하남', '중식']);
  });

  test('편집 화면에서 고친 태그가 글에 남는다 (발행 요청에 같이 간다)', () {
    final provider = PostProvider()..loadFromHistory({'title': '제목', 'blocks': [], 'tags': ['하남맛집']});
    expect(provider.tags, ['하남맛집']);
    provider.setTags(['하남맛집', '초마']);
    expect(provider.generatedPost!['tags'], ['하남맛집', '초마']);
  });
}
