"""Live web research and fact-verification tool using DuckDuckGo HTML search."""
import urllib.request
import urllib.parse
import re
import html
from typing import List, Dict, Any

class WebSearchTool:
    """Haqiqiy internetdan yangi ma'lumotlar, faktlar va narxlarni qidiruvchi modul."""

    @classmethod
    def search(cls, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        """DuckDuckGo orqali qidiruv o'tkazadi va havolalari bilan natijalarni qaytaradi."""
        results = []
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            # Qidiruv natijalarini parsing qilish
            pattern = re.compile(
                r'<a[^>]+class="result__url"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            matches = pattern.findall(content)

            for match in matches[:max_results]:
                raw_url, title, snippet = match
                clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                
                # DuckDuckGo redirect url tozalash
                if "uddg=" in raw_url:
                    actual_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                else:
                    actual_url = raw_url

                results.append({
                    "title": html.unescape(clean_title),
                    "snippet": html.unescape(clean_snippet),
                    "url": actual_url
                })
        except Exception as e:
            # Fallback agar tarmoq xatosi bo'lsa
            pass

        return results
