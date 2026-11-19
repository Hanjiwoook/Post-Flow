import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/post_provider.dart';
import 'package:frontend/widgets/publish_result_dialog.dart';

/// 정해 둔 응답을 차례로 돌려주는 가짜 서버. 마지막 응답은 계속 돌려준다.
FetchPublishStatus fakeServer(List<Map<String, dynamic>> answers, List<int> calls) {
  return (int id) async {
    calls.add(id);
    final i = calls.length - 1;
    return answers[i < answers.length ? i : answers.length - 1];
  };
}

Future<void> showResult(WidgetTester tester, FetchPublishStatus fetch, {List<int> ids = const [12]}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: PublishResultDialog(postIds: ids, fetchStatus: fetch, interval: const Duration(seconds: 3)),
    ),
  ));
  await tester.pump(); // 첫 질문의 답 반영
}

void main() {
  test('job_id 글자를 발행 번호 목록으로 바꾼다', () {
    expect(parseJobIds('12'), [12]);
    expect(parseJobIds('12, 13'), [12, 13]);
    expect(parseJobIds(null), isEmpty);
  });

  testWidgets('진행 단계를 보여주다가, 끝나면 임시저장 완료와 고칠 것을 보여주고 더 묻지 않는다', (tester) async {
    final calls = <int>[];
    await showResult(
        tester,
        fakeServer([
          {'status': 'PROCESSING', 'step': '글 넣는 중 (3/31)'},
          {'status': 'SUCCESS', 'problems': ['5번 블록이 왼쪽 정렬입니다'], 'platform': 'NAVER'},
        ], calls));

    expect(find.text('글 넣는 중 (3/31)'), findsOneWidget);
    expect(find.text('발행하는 중'), findsOneWidget);

    await tester.pump(const Duration(seconds: 3));
    expect(find.text('임시저장 완료'), findsOneWidget);
    expect(find.text('5번 블록이 왼쪽 정렬입니다'), findsOneWidget);
    expect(find.text('발행 결과'), findsOneWidget);

    await tester.pump(const Duration(seconds: 9));
    expect(calls.length, 2); // 끝난 뒤에는 서버에 다시 묻지 않는다
  });

  testWidgets('고칠 것이 없으면 그렇다고 알린다', (tester) async {
    await showResult(tester, fakeServer([{'status': 'SUCCESS', 'problems': []}], []));
    expect(find.textContaining('고칠 것이 없었어요'), findsOneWidget);
  });

  testWidgets('로그인이 필요하면 이유와 로그인 저장 명령을 보여준다', (tester) async {
    await showResult(
        tester,
        fakeServer([
          {'status': 'FAIL', 'error_code': 'LOGIN_REQUIRED', 'fail_reason': '저장된 네이버 로그인이 만료됐습니다'},
        ], []));
    expect(find.text('네이버 로그인이 필요해요'), findsOneWidget);
    expect(find.text('저장된 네이버 로그인이 만료됐습니다'), findsOneWidget);
    expect(find.text(saveLoginCommand), findsOneWidget);
  });

  testWidgets('다른 실패는 로그인 명령 없이 이유만 보여준다', (tester) async {
    await showResult(
        tester,
        fakeServer([
          {'status': 'FAIL', 'error_code': 'PUBLISH_ERROR', 'fail_reason': '편집기에서 저장 버튼을 찾지 못했습니다'},
        ], []));
    expect(find.text('발행 실패'), findsOneWidget);
    expect(find.text('편집기에서 저장 버튼을 찾지 못했습니다'), findsOneWidget);
    expect(find.text(saveLoginCommand), findsNothing);
  });

  testWidgets('서버가 잠깐 답하지 않아도 창을 닫지 않고 다시 묻는다', (tester) async {
    var n = 0;
    Future<Map<String, dynamic>> flaky(int id) async {
      n++;
      if (n == 1) throw Exception('연결 끊김');
      return {'status': 'SUCCESS', 'problems': []};
    }

    await showResult(tester, flaky);
    expect(find.textContaining('서버에 연결하지 못했어요'), findsOneWidget);
    await tester.pump(const Duration(seconds: 3));
    expect(find.text('임시저장 완료'), findsOneWidget);
  });
}
