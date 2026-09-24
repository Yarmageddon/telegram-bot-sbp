"""
Конвертация документов и OCR
"""
import os
import uuid
from pathlib import Path

# Папка для документов
DOCS_DIR = Path("/tmp/documents")
DOCS_DIR.mkdir(exist_ok=True)


def convert_pdf_to_text(pdf_path: str) -> tuple:
    """Конвертация PDF в текст"""
    try:
        import PyPDF2
        
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        if not text.strip():
            return False, "PDF не содержит текста (возможно, это скан)", ""
        
        return True, "✅ Текст успешно извлечен", text
    
    except ImportError:
        return False, "❌ Библиотека PyPDF2 не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}", ""


def convert_text_to_pdf(text: str, filename: str = None) -> tuple:
    """Конвертация текста в PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        
        if not filename:
            filename = f"document_{uuid.uuid4().hex[:8]}.pdf"
        
        output_path = DOCS_DIR / filename
        
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        
        text_object = c.beginText(40, height - 40)
        text_object.setFont("Helvetica", 11)
        
        for line in text.split('\n'):
            text_object.textLine(line)
        
        c.drawText(text_object)
        c.save()
        
        return True, "✅ PDF создан", str(output_path)
    
    except ImportError:
        return False, "❌ Библиотека reportlab не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}", ""


def ocr_from_image(image_path: str, lang: str = "rus+eng") -> tuple:
    """OCR - распознавание текста с изображения"""
    try:
        from PIL import Image
        
        if not os.path.exists(image_path):
            return False, "❌ Файл не найден", ""
        
        # Проверяем размер файла
        file_size = os.path.getsize(image_path)
        if file_size > 10 * 1024 * 1024:  # 10 MB
            return False, "❌ Файл слишком большой (макс. 10 MB)", ""
        
        # Пытаемся использовать pytesseract
        try:
            import pytesseract
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=lang)
            
            if not text.strip():
                return False, "❌ Текст не распознан. Попробуйте более четкое изображение", ""
            
            return True, "✅ Текст успешно распознан", text
        except ImportError:
            # Если pytesseract не установлен, возвращаем ошибку с инструкцией
            return False, "❌ OCR временно недоступен. Библиотека pytesseract не установлена.\n\n💡 Для работы OCR необходима установка tesseract-ocr на сервер.", ""
        except Exception as e:
            # Если pytesseract установлен, но tesseract-ocr не установлен
            if "tesseract is not installed" in str(e).lower():
                return False, "❌ OCR временно недоступен. Tesseract-ocr не установлен на сервере.\n\n💡 Обратитесь к администратору для установки tesseract-ocr.", ""
            return False, f"❌ Ошибка OCR: {str(e)}", ""
    
    except ImportError:
        return False, "❌ Библиотека Pillow не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}", ""


def save_uploaded_file(file_bytes: bytes, extension: str) -> str:
    """Сохранить загруженный файл"""
    filename = f"{uuid.uuid4().hex[:12]}.{extension}"
    file_path = DOCS_DIR / filename
    
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    return str(file_path)


def get_file_extension(file_name: str) -> str:
    """Получить расширение файла"""
    return file_name.split('.')[-1].lower() if '.' in file_name else ""
