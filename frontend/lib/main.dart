import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/post_provider.dart';
import 'services/draft_store.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => PostProvider(store: DraftStore.windowsDefault())),
      ],
      child: const PostFlowApp(),
    ),
  );
}

class PostFlowApp extends StatelessWidget {
  const PostFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Post Flow',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
        fontFamily: 'Pretendard', // 나중에 폰트 적용 시 유용
      ),
      home: const HomeScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}