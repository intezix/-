"""
Скрипт для обрезки и загрузки изображения.

Использование:
    python resize_and_upload.py фото.jpg
"""

import sys
import os
import requests

try:
    from PIL import Image
except ImportError:
    print("❌ Нужна библиотека Pillow. Установи:")
    print("   pip install Pillow")
    sys.exit(1)


def resize_image(file_path: str, target_width: int = 1200, target_height: int = 700) -> str:
    """
    Обрезает и масштабирует изображение.
    
    Returns:
        Путь к новому файлу
    """
    img = Image.open(file_path)
    
    # Текущие размеры
    orig_width, orig_height = img.size
    print(f"📐 Оригинал: {orig_width} × {orig_height}")
    
    # Соотношение сторон целевое
    target_ratio = target_width / target_height
    orig_ratio = orig_width / orig_height
    
    # Обрезаем по центру под нужное соотношение
    if orig_ratio > target_ratio:
        # Фото шире - обрезаем по бокам
        new_width = int(orig_height * target_ratio)
        left = (orig_width - new_width) // 2
        img = img.crop((left, 0, left + new_width, orig_height))
    else:
        # Фото выше - обрезаем сверху/снизу
        new_height = int(orig_width / target_ratio)
        top = (orig_height - new_height) // 2
        img = img.crop((0, top, orig_width, top + new_height))
    
    # Масштабируем до целевого размера
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Конвертируем RGBA в RGB (убираем прозрачность)
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Сохраняем
    name, ext = os.path.splitext(file_path)
    new_path = f"{name}_resized.jpg"
    img.save(new_path, "JPEG", quality=90)
    
    print(f"✂️ Обрезано: {target_width} × {target_height}")
    print(f"💾 Сохранено: {new_path}")
    
    return new_path


def upload_image(file_path: str) -> str:
    """Загружает на catbox.moe"""
    url = "https://catbox.moe/user/api.php"
    filename = os.path.basename(file_path)
    
    with open(file_path, "rb") as f:
        response = requests.post(
            url,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (filename, f)},
            timeout=120
        )
    
    if response.status_code == 200 and response.text.startswith("https://"):
        return response.text.strip()
    
    raise Exception(f"Ошибка: {response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python resize_and_upload.py фото.jpg")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    print(f"📤 Обрабатываю: {file_path}\n")
    
    try:
        # Обрезаем
        resized_path = resize_image(file_path)
        
        # Загружаем
        print(f"\n☁️ Загружаю на catbox.moe...")
        image_url = upload_image(resized_path)
        
        print(f"\n✅ Готово!")
        print(f"📎 URL: {image_url}\n")
        
        # Удаляем временный файл
        os.remove(resized_path)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
