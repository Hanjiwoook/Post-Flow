import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

class TistoryAutomation:
    def __init__(self):
        self.access_token = os.getenv("TISTORY_ACCESS_TOKEN")
        self.blog_name = os.getenv("TISTORY_BLOG_NAME") # 예: "myblog" (https://myblog.tistory.com)
    
    def upload_image(self, image_path: str) -> str:
        """
        티스토리에 이미지를 업로드하고 URL을 반환합니다.
        """
        if not self.access_token or not self.blog_name:
            print("❌ TISTORY_ACCESS_TOKEN 또는 TISTORY_BLOG_NAME이 설정되지 않았습니다.")
            return None

        url = "https://www.tistory.com/apis/post/attach"
        
        try:
            files = {'uploadedfile': open(image_path, 'rb')}
            data = {
                'access_token': self.access_token,
                'blogName': self.blog_name,
                'output': 'json'
            }
            
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                result = response.json()
                # 티스토리 API 응답에서 이미지 URL 추출 (replacer가 URL임)
                return result.get('tistory', {}).get('replacer', '')
            else:
                print(f"❌ 이미지 업로드 실패: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 이미지 업로드 중 에러: {e}")
            return None

    def publish(self, title: str, content: str, image_paths: list[str] = [], tags: list[str] = []) -> str:
        """
        티스토리 블로그에 이미지를 포함하여 글을 발행합니다.
        """
        if not self.access_token or not self.blog_name:
            print("❌ TISTORY_ACCESS_TOKEN 또는 TISTORY_BLOG_NAME이 설정되지 않았습니다.")
            return None

        import re
        final_content = content

        # 1. 이미지 업로드 및 마커 치환
        for i, img_path in enumerate(image_paths):
            marker = f"[IMAGE{i+1}]"
            if marker in final_content:
                replacer = self.upload_image(img_path)
                if replacer:
                    # 티스토리의 replacer는 그 자체로 이미지 태그 역할을 함
                    final_content = final_content.replace(marker, f"<p style='text-align: center;'>{replacer}</p>")
        
        # 2. 기타 서식 마커 치환 (HTML 변환)
        # [QUOTE: ...] -> <blockquote>
        final_content = re.sub(r"\[QUOTE:\s*(.*?)\]", r"<blockquote style='border-left: 5px solid #eee; padding-left: 15px; color: #666;'>\1</blockquote>", final_content)
        # [DIVIDER] -> <hr>
        final_content = final_content.replace("[DIVIDER]", "<hr style='border: 0; border-top: 1px solid #eee; margin: 20px 0;' />")
        # [MAP: ...] -> 텍스트 표시
        final_content = re.sub(r"\[MAP:\s*(.*?)\]", r"<p style='color: #2e66ff; font-weight: bold;'>📍 지도: \1</p>", final_content)

        # 3. 남은 마커 제거 (혹시 이미지가 더 적게 전달된 경우)
        final_content = re.sub(r"\[IMAGE\d+\]", "", final_content)

        # 4. 텍스트를 HTML로 변환 (줄바꿈 처리)
        # 본문이 이미 HTML이 아닐 경우를 대비해 간단한 변환 수행
        html_content = final_content.replace("\n", "<br />")
        
        url = "https://www.tistory.com/apis/post/write"
        tag_str = ",".join(tags) if tags else ""

        data = {
            'access_token': self.access_token,
            'output': 'json',
            'blogName': self.blog_name,
            'title': title,
            'content': html_content,
            'visibility': '3', # 0: 비공개, 1: 보호, 3: 발행
            'category': '0',
            'tag': tag_str
        }

        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                post_url = result.get('tistory', {}).get('url', '')
                print(f"🚀 티스토리 발행 완료: {post_url}")
                return post_url
            else:
                print(f"❌ 티스토리 발행 실패: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 티스토리 발행 중 에러: {e}")
            return None

tistory_automation = TistoryAutomation()
