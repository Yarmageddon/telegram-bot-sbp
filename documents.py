"""
Конвертация документов и OCR
"""
import os
import uuid
from pathlib import Path
from datetime import datetime

# Создаем папку для документов
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
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        if not filename:
            filename = f"document_{uuid.uuid4().hex[:8]}.pdf"
        
        output_path = DOCS_DIR / filename
        
        # Регистрируем шрифт с поддержкой кириллицы
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            font_name = "DejaVu"
        else:
            font_name = "Helvetica"
        
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        
        # Добавляем текст
        text_object = c.beginText(40, height - 40)
        text_object.setFont(font_name, 11)
        
        for line in text.split('\n'):
            text_object.textLine(line)
        
        c.drawText(text_object)
        c.save()
        
        return True, "✅ PDF создан", str(output_path)
    
    except ImportError:
        return False, "❌ Библиотека reportlab не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}", ""


def ocr_from_image(image_path: str, lang: str = "ru+en") -> tuple:
    """OCR - распознавание текста с изображения (через rapidocr)"""
    try:
        from rapidocr_onnxruntime import RapidOCR
        
        if not os.path.exists(image_path):
            return False, "❌ Файл не найден", ""
        
        # Создаём движок OCR
        engine = RapidOCR()
        
        # Распознаём текст
        result, elapse = engine(image_path)
        
        if not result:
            return False, "❌ Текст не распознан. Попробуйте более четкое изображение", ""
        
        # result - это список списков: [[координаты, текст, уверенность], ...]
        text_lines = [item[1] for item in result]
        text = "\n".join(text_lines)
        
        if not text.strip():
            return False, "❌ Текст не распознан. Попробуйте более четкое изображение", ""
        
        return True, "✅ Текст успешно распознан", text
    
    except ImportError:
        return False, "❌ Библиотека rapidocr-onnxruntime не установлена", ""
    except Exception as e:
        return False, f"❌ Ошибка OCR: {str(e)}", ""


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


def convert_between_formats(input_path: str, target_format: str) -> tuple:
    """Конвертация между форматами"""
    input_ext = get_file_extension(input_path)
    
    if input_ext == "pdf" and target_format == "txt":
        return convert_pdf_to_text(input_path)
    
    elif input_ext == "txt" and target_format == "pdf":
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return convert_text_to_pdf(text)
    
    else:
        return False, f"❌ Конвертация {input_ext} → {target_format} не поддерживается", ""
