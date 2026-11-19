import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/widgets/writing_report_card.dart';

// 11/18 실제 /analyze 결과(유카이도)를 줄인 것
Map<String, dynamic> realPost() => {
      'format_check': {
        'passed': true,
        'results': [
          {'rule': '인사로 시작', 'severity': 'error', 'passed': true, 'detail': "첫 글이 '안녕하세요'로 시작"},
          {'rule': '너무 짧은 글', 'severity': 'warning', 'passed': true, 'detail': '본문 1,622자'},
        ],
      },
      'writing_notes': [
        '가게 정보 인용구는 제공된 문구 그대로 넣음',
        '만족도와 재방문 의사 확인 필요 - 메모에 재방문·추천 의사가 없어 재방문 문장과 추천 줄을 뺌',
        '날씨 정보 없음 - 날씨 언급 안 함',
      ],
      'usage': {'model': 'claude-opus-5-5', 'input_tokens': 28559, 'output_tokens': 12670, 'cost_usd': 0.367636},
    };

void main() {
  group('buildWritingReport', () {
    test('모두 통과하면 실패 규칙이 없고, 확인 필요 메모만 따로 뽑는다', () {
      final r = buildWritingReport(realPost());
      expect(r.ruleCount, 2);
      expect(r.failed, isEmpty);
      expect(r.needsCheck.length, 1);
      expect(r.needsCheck.first, startsWith('만족도와 재방문 의사 확인 필요'));
      expect(r.otherNotes.length, 2);
      expect(r.costText, 'claude-opus-5-5 · \$0.37 · 입력 28,559 / 출력 12,670 토큰');
    });

    test('못 지킨 규칙은 error를 warning보다 먼저 보여 준다', () {
      final post = realPost();
      post['format_check'] = {
        'passed': false,
        'results': [
          {'rule': '폰에서 꺾이는 줄', 'severity': 'warning', 'passed': false, 'detail': '20자 넘는 줄 40%'},
          {'rule': '줄 끝 마침표 없음', 'severity': 'error', 'passed': false, 'detail': '마침표로 끝나는 줄 20%'},
          {'rule': '인사로 시작', 'severity': 'error', 'passed': true, 'detail': ''},
        ],
      };
      final r = buildWritingReport(post);
      expect(r.failed.map((f) => f.rule), ['줄 끝 마침표 없음', '폰에서 꺾이는 줄']);
      expect(r.failed.first.isError, isTrue);
    });

    test('예전 글(검사·메모·비용 없음)도 에러 없이 빈 리포트가 된다', () {
      final r = buildWritingReport({'blocks': []});
      expect(r.hasFormatCheck, isFalse);
      expect(r.needsCheck, isEmpty);
      expect(r.costText, isNull);
    });
  });

  testWidgets('카드에 통과 문구, 확인 필요, 비용이 보인다', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: WritingReportCard(post: realPost())))));
    expect(find.text('✅ 형식 검사 2개 규칙 모두 통과'), findsOneWidget);
    expect(find.text('👀 확인해 주세요'), findsOneWidget);
    expect(find.textContaining('만족도와 재방문 의사 확인 필요'), findsOneWidget);
    expect(find.text('AI 작성 메모 2개'), findsOneWidget);
    expect(find.textContaining('\$0.37'), findsOneWidget);
  });
}
