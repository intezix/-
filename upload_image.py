"""
Скрипт для загрузки изображений.

Использование:
    python upload_image.py путь/к/изображению.jpg

Результат:
    Публичный URL изображения
"""

import sys
import os
import requests


def upload_to_catbox(file_path: str) -> str:
    """
    Загружает изображение на catbox.moe (бесплатный хостинг).
    
    Args:
        file_path: Путь к файлу изображения
        
    Returns:
        Публичный URL изображения
    """
    url = "https://catbox.moe/user/api.php"
    filename = os.path.basename(file_path)
    
    with open(file_path, "rb") as f:
        response = requests.post(
            url,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (filename, f)}
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200 and response.text.startswith("https://"):
        return response.text.strip()
    
    raise Exception(f"Ошибка: {response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python upload_image.py путь/к/изображению.jpg")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        sys.exit(1)
    
    print(f"📤 Загружаю: {file_path}")
    print(f"📦 Размер: {os.path.getsize(file_path) / 1024:.1f} KB")
    
    try:
        image_url = upload_to_catbox(file_path)
        print(f"\n✅ Изображение загружено!")
        print(f"📎 URL: {image_url}")
        print(f"\nСкопируй URL и скинь мне — добавлю в рецепт.\n")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
