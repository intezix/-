from typing import Optional, Dict, List
import requests
import io
from telegraph import Telegraph as TelegraphAPI
from telegraph.exceptions import TelegraphException
from config import TELEGRAPH_TOKEN, TELEGRAPH_AUTHOR, TELEGRAPH_AUTHOR_URL
from services.recipe_service import Recipe

class TelegraphService:
    _instance: Optional['TelegraphService'] = None
    _telegraph: Optional[TelegraphAPI] = None
    _cache: Dict[str, str] = {}
    _image_cache: Dict[str, str] = {}

    def __new__(cls) -> 'TelegraphService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_telegraph()
        return cls._instance

    def _init_telegraph(self) -> None:
        if TELEGRAPH_TOKEN:
            self._telegraph = TelegraphAPI(TELEGRAPH_TOKEN)
        else:
            self._telegraph = TelegraphAPI()
            try:
                self._telegraph.create_account(short_name='RecipeBot', author_name=TELEGRAPH_AUTHOR)
            except TelegraphException:
                pass

    def validate_image_url(self, image_url: str, recipe_id: str=None) -> tuple[bool, str]:
        log_prefix = f'[VALIDATE] {recipe_id}: ' if recipe_id else '[VALIDATE] '
        if not image_url:
            print(f'{log_prefix}URL пустой')
            return (False, 'URL пустой')
        if not image_url.startswith('https://'):
            print(f'{log_prefix}URL не начинается с https://: {image_url[:50]}')
            return (False, f'URL должен начинаться с https://, получен: {image_url[:50]}')
        try:
            session = requests.Session()
            session.proxies = {}
            print(f'{log_prefix}Проверяю {image_url[:80]}...')
            response = session.get(image_url, timeout=8, stream=True, headers={'Range': 'bytes=0-16383'})
            status_code = response.status_code
            print(f'{log_prefix}HTTP статус: {status_code}')
            if status_code == 206:
                chunk = next(response.iter_content(chunk_size=16384), b'')
            elif status_code == 200:
                chunk = next(response.iter_content(chunk_size=16384), b'')
            else:
                print(f'{log_prefix}❌ HTTP {status_code}')
                return (False, f'HTTP {status_code}')
            if not chunk:
                print(f'{log_prefix}❌ Пустой ответ от сервера')
                return (False, 'Пустой ответ от сервера')
            content_type = response.headers.get('content-type', '').lower()
            print(f'{log_prefix}Content-Type: {content_type}')
            if not content_type.startswith('image/'):
                if chunk.startswith(b'\xff\xd8\xff'):
                    print(f'{log_prefix}✅ Распознана сигнатура JPEG')
                    pass
                elif chunk.startswith(b'\x89PNG\r\n\x1a\n'):
                    print(f'{log_prefix}✅ Распознана сигнатура PNG')
                    pass
                elif chunk.startswith(b'GIF87a') or chunk.startswith(b'GIF89a'):
                    print(f'{log_prefix}✅ Распознана сигнатура GIF')
                    pass
                elif chunk.startswith(b'RIFF') and b'WEBP' in chunk[:12]:
                    print(f'{log_prefix}✅ Распознана сигнатура WebP')
                    pass
                else:
                    print(f'{log_prefix}❌ Content-Type не image/* и не распознана сигнатура')
                    return (False, f'Content-Type не image/* и не распознана сигнатура, получен: {content_type}')
            else:
                print(f'{log_prefix}✅ Content-Type валиден: {content_type}')
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                print(f'{log_prefix}Размер файла: {size_mb:.2f} MB')
                if size_mb > 20:
                    print(f'{log_prefix}❌ Файл слишком большой: {size_mb:.1f} MB')
                    return (False, f'Файл слишком большой: {size_mb:.1f} MB')
            print(f'{log_prefix}✅ URL валиден')
            return (True, '')
        except requests.exceptions.Timeout:
            print(f'{log_prefix}❌ Timeout при проверке URL')
            return (False, 'Timeout при проверке URL')
        except requests.exceptions.RequestException as e:
            print(f'{log_prefix}❌ Ошибка запроса: {str(e)[:100]}')
            return (False, f'Ошибка запроса: {str(e)[:100]}')
        except Exception as e:
            print(f'{log_prefix}❌ Неожиданная ошибка: {str(e)[:100]}')
            return (False, f'Неожиданная ошибка: {str(e)[:100]}')

    def create_recipe_page(self, recipe: Recipe, skip_validation: bool=True) -> Optional[str]:
        import re
        import time as _time
        if self._telegraph is None:
            self._init_telegraph()
            if self._telegraph is None:
                print(f'[TELEGRAPH] {recipe.id}: не инициализирован')
                return None
        content = recipe.format_for_telegraph()
        image_url = (recipe.image_url or '').strip()
        print(f'[TELEGRAPH] recipe_id= {recipe.id}')
        print(f"[TELEGRAPH] image_url= {(image_url[:120] if image_url else '(нет)')}")
        print(f'[TELEGRAPH] html_prefix= {content[:120]!r}')
        for attempt in (1, 2):
            try:
                response = self._telegraph.create_page(title=recipe.name, html_content=content, author_name=TELEGRAPH_AUTHOR, author_url=TELEGRAPH_AUTHOR_URL if TELEGRAPH_AUTHOR_URL else None)
                path = response.get('path', '')
                url = f'https://telegra.ph/{path}' if path else ''
                ok = bool(path)
                print(f'[TELEGRAPH] status= ok={ok} path= {path!r} url= {url!r}')
                return url if ok else None
            except TelegraphException as e:
                err = str(e)
                if attempt == 1 and 'Flood control' in err:
                    m = re.search('[Rr]etry in (\\d+) seconds?', err, re.I)
                    wait = int(m.group(1)) + 1 if m else 5
                    print(f'[TELEGRAPH] Flood control, жду {wait} сек, повтор...')
                    _time.sleep(wait)
                    continue
                print(f'[TELEGRAPH] status= ok=False TelegraphException= {e}')
                return None
            except Exception as e:
                print(f'[TELEGRAPH] status= ok=False error= {e}')
                return None
        return None

    def get_cached_url(self, recipe_id: str) -> Optional[str]:
        return None

    def upload_image_to_telegraph(self, image_url: str) -> Optional[str]:
        if not image_url or not image_url.startswith('https://'):
            print(f"[TELEGRAPH UPLOAD] BAD_URL: {(image_url[:80] if image_url else 'пустой')}")
            return None
        try:
            import os
            old_http_proxy = os.environ.get('HTTP_PROXY')
            old_https_proxy = os.environ.get('HTTPS_PROXY')
            old_http_proxy_lower = os.environ.get('http_proxy')
            old_https_proxy_lower = os.environ.get('https_proxy')
            try:
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)
                os.environ.pop('http_proxy', None)
                os.environ.pop('https_proxy', None)
                session = requests.Session()
                session.proxies = {'http': None, 'https': None}
                print(f'[TELEGRAPH UPLOAD] Скачиваю {image_url[:80]}...')
                max_retries = 2
                retry_delay = 1
                response = None
                for attempt in range(1, max_retries + 1):
                    try:
                        print(f'[TELEGRAPH UPLOAD] Попытка {attempt}/{max_retries}...')
                        response = session.get(image_url, timeout=(5, 25), stream=True, verify=True)
                        response.raise_for_status()
                        print(f'[TELEGRAPH UPLOAD] ✅ Успешно загружено с попытки {attempt}')
                        break
                    except (requests.exceptions.Timeout, requests.exceptions.SSLError, OSError, requests.exceptions.ProxyError) as e:
                        error_name = type(e).__name__
                        if attempt < max_retries:
                            import time
                            time.sleep(retry_delay)
                        else:
                            print(f'[TELEGRAPH UPLOAD] ❌ Все {max_retries} попытки не удались: {error_name}')
                            raise
            finally:
                if old_http_proxy is not None:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy is not None:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                if old_http_proxy_lower is not None:
                    os.environ['http_proxy'] = old_http_proxy_lower
                if old_https_proxy_lower is not None:
                    os.environ['https_proxy'] = old_https_proxy_lower
            if response is None:
                return None
            print(f'[TELEGRAPH UPLOAD] Читаю файл по частям...')
            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'jpeg' in content_type or 'jpg' in content_type:
                file_ext = 'jpg'
            elif 'png' in content_type:
                file_ext = 'png'
            elif 'gif' in content_type:
                file_ext = 'gif'
            elif 'webp' in content_type:
                file_ext = 'webp'
            else:
                file_ext = 'jpg'
            file_content = b''
            chunk_size = 8192
            max_size = 20 * 1024 * 1024
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file_content += chunk
                    if len(file_content) > max_size:
                        print(f'[TELEGRAPH UPLOAD] Файл слишком большой, прерываю чтение')
                        return None
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > 20:
                print(f'[TELEGRAPH UPLOAD] Файл слишком большой: {file_size_mb:.1f} MB')
                return None
            print(f'[TELEGRAPH UPLOAD] Размер: {file_size_mb:.2f} MB, тип: {content_type}')
            old_http_proxy_upload = os.environ.get('HTTP_PROXY')
            old_https_proxy_upload = os.environ.get('HTTPS_PROXY')
            old_http_proxy_lower_upload = os.environ.get('http_proxy')
            old_https_proxy_lower_upload = os.environ.get('https_proxy')
            try:
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)
                os.environ.pop('http_proxy', None)
                os.environ.pop('https_proxy', None)
                upload_session = requests.Session()
                upload_session.proxies = {'http': None, 'https': None}
                upload_max = 2
                for u_attempt in range(1, upload_max + 1):
                    file_obj = io.BytesIO(file_content)
                    file_obj.name = f'image.{file_ext}'
                    print(f'[TELEGRAPH UPLOAD] Загружаю на telegra.ph/upload (попытка {u_attempt}/{upload_max})...')
                    upload_response = upload_session.post('https://telegra.ph/upload', files={'file': (f'image.{file_ext}', file_obj, content_type)}, timeout=20)
                    if upload_response.status_code == 200:
                        result = upload_response.json()
                        if isinstance(result, list) and len(result) > 0:
                            telegraph_path = result[0].get('src', '')
                            if telegraph_path:
                                if telegraph_path.startswith('/'):
                                    telegraph_url = f'https://telegra.ph{telegraph_path}'
                                else:
                                    telegraph_url = f'https://telegra.ph/{telegraph_path}'
                                print(f'[TELEGRAPH UPLOAD] ✅ Успешно: {telegraph_url}')
                                return telegraph_url
                        print(f'[TELEGRAPH UPLOAD] ❌ Неверный формат ответа: {upload_response.text[:200]}')
                    else:
                        if upload_response.status_code == 400:
                            print('UPLOAD ERROR', upload_response.status_code, upload_response.text[:300] if upload_response.text else '', 'file_size_bytes=', len(file_content))
                            print(f'[TELEGRAPH UPLOAD] image_url= {image_url[:120]}')
                            print(f'[TELEGRAPH UPLOAD] content_type= {content_type} format= {file_ext}')
                        else:
                            print(f'[TELEGRAPH UPLOAD] ❌ HTTP {upload_response.status_code}: {upload_response.text[:200]}')
                        if u_attempt < upload_max:
                            import time
                            time.sleep(1)
                            continue
                    break
            finally:
                if old_http_proxy_upload is not None:
                    os.environ['HTTP_PROXY'] = old_http_proxy_upload
                if old_https_proxy_upload is not None:
                    os.environ['HTTPS_PROXY'] = old_https_proxy_upload
                if old_http_proxy_lower_upload is not None:
                    os.environ['http_proxy'] = old_http_proxy_lower_upload
                if old_https_proxy_lower_upload is not None:
                    os.environ['https_proxy'] = old_https_proxy_lower_upload
            return None
        except (requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
            error_type = 'Timeout' if isinstance(e, requests.exceptions.Timeout) else 'SSL Error'
            print(f'[TELEGRAPH UPLOAD] ❌ {error_type} при загрузке {image_url[:80]}: {str(e)[:100]}')
            return None
        except requests.exceptions.RequestException as e:
            print(f'[TELEGRAPH UPLOAD] ❌ Ошибка запроса для {image_url[:80]}: {str(e)[:100]}')
            return None
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f'[TELEGRAPH UPLOAD] ❌ Неожиданная ошибка для {image_url[:80]}: {str(e)[:100]}')
            import traceback
            print(f'[TELEGRAPH UPLOAD] Traceback: {traceback.format_exc()}')
            return None

    def upload_local_image_to_telegraph(self, file_path: str) -> Optional[str]:
        from pathlib import Path
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            print(f'[TELEGRAPH UPLOAD] ❌ Файл не найден: {file_path}')
            return None
        try:
            ext = file_path_obj.suffix.lower()
            if ext in ['.jpg', '.jpeg']:
                file_ext = 'jpg'
                content_type = 'image/jpeg'
            elif ext == '.png':
                file_ext = 'png'
                content_type = 'image/png'
            elif ext == '.gif':
                file_ext = 'gif'
                content_type = 'image/gif'
            elif ext == '.webp':
                file_ext = 'webp'
                content_type = 'image/webp'
            else:
                file_ext = 'jpg'
                content_type = 'image/jpeg'
            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            if file_size_mb > 20:
                print(f'[TELEGRAPH UPLOAD] ❌ Файл слишком большой: {file_size_mb:.1f} MB')
                return None
            print(f'[TELEGRAPH UPLOAD] Читаю локальный файл: {file_path_obj.name} ({file_size_mb:.2f} MB)')
            with open(file_path_obj, 'rb') as f:
                file_content = f.read()
            import os
            old_http_proxy = os.environ.get('HTTP_PROXY')
            old_https_proxy = os.environ.get('HTTPS_PROXY')
            old_http_proxy_lower = os.environ.get('http_proxy')
            old_https_proxy_lower = os.environ.get('https_proxy')
            try:
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)
                os.environ.pop('http_proxy', None)
                os.environ.pop('https_proxy', None)
                upload_session = requests.Session()
                upload_session.proxies = {'http': None, 'https': None}
                file_obj = io.BytesIO(file_content)
                print(f'[TELEGRAPH UPLOAD] Загружаю на telegra.ph/upload...')
                upload_response = upload_session.post('https://telegra.ph/upload', files={'file': (f'image.{file_ext}', file_obj, content_type)}, timeout=20)
                if upload_response.status_code == 200:
                    result = upload_response.json()
                    if isinstance(result, list) and len(result) > 0:
                        telegraph_path = result[0].get('src', '')
                        if telegraph_path:
                            url = f'https://telegra.ph{telegraph_path}' if telegraph_path.startswith('/') else f'https://telegra.ph/{telegraph_path}'
                            print(f'[TELEGRAPH UPLOAD] ✅ Успешно: {url}')
                            return url
                    print(f'[TELEGRAPH UPLOAD] ❌ Неверный формат ответа: {result}')
                else:
                    if upload_response.status_code == 400:
                        print('UPLOAD ERROR', upload_response.status_code, upload_response.text[:300] if upload_response.text else '', 'file_size_bytes=', len(file_content))
                        print(f'[TELEGRAPH UPLOAD] file_path= {file_path}')
                        print(f'[TELEGRAPH UPLOAD] content_type= {content_type} format= {file_ext}')
                    else:
                        err = upload_response.text[:500] if upload_response.text else 'Нет текста'
                        print(f'[TELEGRAPH UPLOAD] ❌ HTTP {upload_response.status_code}: {err}')
                    if upload_response.status_code == 400:
                        file_obj = io.BytesIO(file_content)
                        print(f'[TELEGRAPH UPLOAD] 🔄 Пробую альтернативный формат загрузки...')
                        try:
                            r2 = upload_session.post('https://telegra.ph/upload', files={'file': (f'image.{file_ext}', file_obj)}, timeout=20)
                            if r2.status_code == 200:
                                data = r2.json()
                                if isinstance(data, list) and data and data[0].get('src'):
                                    p = data[0]['src']
                                    u = f'https://telegra.ph{p}' if p.startswith('/') else f'https://telegra.ph/{p}'
                                    print(f'[TELEGRAPH UPLOAD] ✅ Успешно (альтернативный формат): {u}')
                                    return u
                        except Exception as e2:
                            print(f'[TELEGRAPH UPLOAD] ❌ Альтернативный формат не сработал: {e2}')
                return None
            finally:
                if old_http_proxy is not None:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy is not None:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                if old_http_proxy_lower is not None:
                    os.environ['http_proxy'] = old_http_proxy_lower
                if old_https_proxy_lower is not None:
                    os.environ['https_proxy'] = old_https_proxy_lower
        except Exception as e:
            print(f'[TELEGRAPH UPLOAD] ❌ Ошибка при загрузке локального файла {file_path}: {str(e)[:200]}')
            return None

    def upload_image_from_url(self, image_url: str) -> Optional[str]:
        if image_url in self._image_cache:
            return self._image_cache[image_url]
        try:
            session = requests.Session()
            session.proxies = {}
            response = session.get(image_url, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'jpeg' in content_type or 'jpg' in content_type:
                file_ext = 'jpg'
            elif 'png' in content_type:
                file_ext = 'png'
            elif 'gif' in content_type:
                file_ext = 'gif'
            else:
                file_ext = 'jpg'
            file_obj = io.BytesIO(response.content)
            file_obj.name = f'image.{file_ext}'
            upload_session = requests.Session()
            upload_session.proxies = {}
            upload_response = upload_session.post('https://telegra.ph/upload', files={'file': (f'image.{file_ext}', file_obj, content_type)}, timeout=10)
            if upload_response.status_code == 200:
                result = upload_response.json()
                if isinstance(result, list) and len(result) > 0:
                    telegraph_path = result[0].get('src', '')
                    if telegraph_path:
                        self._image_cache[image_url] = telegraph_path
                        return telegraph_path
            print(f'Telegraph: failed to upload image from {image_url}')
            return None
        except Exception as e:
            print(f'Telegraph: error uploading image from {image_url}: {e}')
            return None

    def clear_cache(self) -> None:
        self._cache.clear()
        self._image_cache.clear()

    def force_recreate_all_pages(self) -> None:
        self.clear_cache()
        print('✅ Кеш очищен - все страницы будут пересозданы при следующем открытии')

    def rebuild_pages(self, recipes: List[Recipe]) -> Dict[str, str]:
        results = {}
        total = len(recipes)
        print(f'[TELEGRAPH REBUILD] Начинаю пересоздание {total} страниц...')
        for i, recipe in enumerate(recipes, 1):
            print(f'[TELEGRAPH REBUILD] [{i}/{total}] Обрабатываю {recipe.id} ({recipe.name})...')
            url = self.create_recipe_page(recipe, skip_validation=True)
            if url:
                results[recipe.id] = url
                print(f'[TELEGRAPH REBUILD] [{i}/{total}] ✅ {recipe.id}: {url}')
            else:
                print(f'[TELEGRAPH REBUILD] [{i}/{total}] ❌ {recipe.id}: не удалось создать страницу')
        print(f'[TELEGRAPH REBUILD] Готово! Успешно пересоздано {len(results)}/{total} страниц')
        return results