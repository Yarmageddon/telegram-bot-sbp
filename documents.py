"""
Работа с документами и OCR
"""
import os
import uuid
from pathlib import Path

DOCS_DIR = Path("/tmp/documents")
DOCS_DIR.mkdir(exist_ok=True)


def convert_pdf_to_text(pdf_path: str) -> tuple:
    """PDF → текст. Возвращает (ok, message, text)"""
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            return False, "PDF не содержит текста (возможно, это скан — используй OCR)", ""
        return True, "Текст успешно извлечён", text
    except ImportError:
        return False, "Библиотека PyPDF2 не установлена", ""
    except Exception as e:
        return False, f"Ошибка: {e}", ""


def convert_text_to_pdf(text: str, filename: str = None) -> tuple:
    """Текст → PDF. Возвращает (ok, message, path)"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if not filename:
            filename = f"doc_{uuid.uuid4().hex[:8]}.pdf"
        output_path = DOCS_DIR / filename

        # Регистрируем Unicode-шрифт для кириллицы
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            font_name = "DejaVu"
        else:
            font_name = "Helvetica"

        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        text_obj = c.beginText(40, height - 50)
        text_obj.setFont(font_name, 11)
        text_obj.setLeading(16)

        for line in text.split("\n"):
            # Разбиваем длинные строки
            while len(line) > 90:
                text_obj.textLine(line[:90])
                line = line[90:]
            text_obj.textLine(line)

        c.drawText(text_obj)
        c.save()
        return True, "PDF создан", str(output_path)
    except ImportError:
        return False, "Библиотека reportlab не установлена", ""
    except Exception as e:
        return False, f"Ошибка: {e}", ""


def ocr_from_image(image_path: str, lang: str = "rus+eng") -> tuple:
    """OCR с изображения. Возвращает (ok, message, text)"""
    if not os.path.exists(image_path):
        return False, "Файл не найден", ""
    if os.path.getsize(image_path) > 10 * 1024 * 1024:
        return False, "Файл слишком большой (макс. 10 MB)", ""
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        if not text.strip():
            return False, "Текст не распознан. Попробуй более чёткое изображение.", ""
        return True, "Текст распознан", text
    except ImportError:
        return False, "OCR недоступен (pytesseract/Pillow не установлен)", ""
    except Exception as e:
        if "tesseract is not installed" in str(e).lower():
            return False, "Tesseract-OCR не установлен на сервере", ""
        return False, f"Ошибка OCR: {e}", ""
