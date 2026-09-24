def ocr_from_image(image_path: str, lang: str = "ru+en") -> tuple:
    """OCR - распознавание текста с изображения (через easyocr)"""
    try:
        import easyocr
        
        if not os.path.exists(image_path):
            return False, "❌ Файл не найден", ""
        
        # Создаём читатель (загружает модели при первом запуске)
        reader = easyocr.Reader(['ru', 'en'], gpu=False)
        
        # Распознаём текст
        result = reader.readtext(image_path)
        
        if not result:
            return False, "❌ Текст не распознан. Попробуйте более четкое изображение", ""
        
        # result - это список кортежей: (координаты, текст, уверенность)
        text_lines = [item[1] for item in result]
        text = "\n".join(text_lines)
        
        if not text.strip():
            return False, "❌ Текст не распознан. Попробуйте более четкое изображение", ""
        
        return True, "✅ Текст успешно распознан", text
    
    except ImportError:
        return False, "❌ Библиотека easyocr не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка OCR: {str(e)}", ""
