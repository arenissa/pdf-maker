#!/usr/bin/env python3
"""
Генератор PDF документов из данных и HTML-шаблонов.
Поддерживает CSV и JSON форматы данных.
Использует WeasyPrint для генерации PDF с поддержкой кириллицы.
"""

import os
import sys
import json
import csv
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


class PDFGenerator:
    """Класс для генерации PDF документов из данных и HTML-шаблонов."""
    
    def __init__(self, data_dir: str = "data", templates_dir: str = "templates", output_dir: str = "output"):
        """
        Инициализация генератора PDF.
        
        Args:
            data_dir: Директория с файлами данных
            templates_dir: Директория с HTML шаблонами
            output_dir: Директория для сохранения PDF
        """
        self.data_dir = Path(data_dir)
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        
        self._ensure_directories()
        self._check_dependencies()
    
    def _ensure_directories(self):
        """Создание необходимых директорий, если их нет."""
        self.data_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
    
    def _check_dependencies(self):
        """Проверка наличия необходимых зависимостей."""
        if not HAS_WEASYPRINT:
            print("❌ Ошибка: WeasyPrint не установлен.")
            print("Установите: pip install weasyprint")
            sys.exit(1)
    
    def _get_data_files(self) -> List[Path]:
        """Получение списка всех файлов данных (CSV и JSON)."""
        csv_files = list(self.data_dir.glob("*.csv"))
        json_files = list(self.data_dir.glob("*.json"))
        return sorted(csv_files + json_files)
    
    def _get_template_files(self) -> List[Path]:
        """Получение списка всех HTML шаблонов."""
        return sorted(self.templates_dir.glob("*.html"))
    
    def _load_data(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Загрузка данных из файла.
        
        Args:
            file_path: Путь к файлу данных
            
        Returns:
            Список словарей с данными
        """
        suffix = file_path.suffix.lower()
        
        if suffix == ".csv":
            return self._load_csv(file_path)
        elif suffix == ".json":
            return self._load_json(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {suffix}")
    
    def _load_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """Загрузка CSV файла."""
        if HAS_PANDAS:
            df = pd.read_csv(file_path, encoding='utf-8')
            return df.to_dict('records')
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
    
    def _load_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """Загрузка JSON файла."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError("JSON должен содержать список объектов или один объект")
    
    def _load_template(self, file_path: Path) -> str:
        """Загрузка HTML шаблона."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _display_menu(self, title: str, items: List[str]) -> int:
        """
        Отображение нумерованного меню.
        
        Args:
            title: Заголовок меню
            items: Список элементов
            
        Returns:
            Индекс выбранного элемента (0-based)
        """
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item}")
        
        print(f"{'='*60}")
        
        while True:
            try:
                choice = input(f"\nВыберите вариант (1-{len(items)}): ")
                index = int(choice) - 1
                if 0 <= index < len(items):
                    return index
                else:
                    print("⚠️  Неверный диапазон. Попробуйте снова.")
            except ValueError:
                print("⚠️  Введите число. Попробуйте снова.")
    
    def select_data_file(self) -> Optional[Path]:
        """Выбор файла данных пользователем."""
        files = self._get_data_files()
        
        if not files:
            print("❌ В директории 'data' нет файлов (.csv или .json)")
            return None
        
        file_names = [f"{f.name} ({f.suffix[1:].upper()})" for f in files]
        index = self._display_menu("Доступные файлы данных:", file_names)
        return files[index]
    
    def select_template(self) -> Optional[Path]:
        """Выбор HTML шаблона пользователем."""
        files = self._get_template_files()
        
        if not files:
            print("❌ В директории 'templates' нет HTML файлов")
            return None
        
        file_names = [f.name for f in files]
        index = self._display_menu("Доступные HTML шаблоны:", file_names)
        return files[index]
    
    def select_invoice(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Выбор конкретного инвойса из данных.
        
        Args:
            data: Список записей
            
        Returns:
            Выбранная запись или None
        """
        if not data:
            print("❌ Нет доступных записей")
            return None
        
        # Пытаемся найти поле invoice_id или аналогичное
        invoice_field = None
        common_names = ['invoice_id', 'invoice', 'id', 'номер', 'invoice_number', 'number']
        
        if data and isinstance(data[0], dict):
            available_keys = {k.lower(): k for k in data[0].keys()}
            for name in common_names:
                if name in available_keys:
                    invoice_field = available_keys[name]
                    break
        
        if not invoice_field:
            print("⚠️  Поле invoice_id не найдено. Используем первую запись.")
            return data[0]
        
        # Формируем список инвойсов
        invoice_list = []
        for i, record in enumerate(data):
            invoice_value = record.get(invoice_field, f"Запись {i+1}")
            additional_info = ""
            
            # Добавляем дополнительную информацию, если есть
            for field in ['client', 'customer', 'name', 'имя', 'клиент', 'company']:
                if field in record:
                    additional_info = f" — {record[field]}"
                    break
            
            invoice_list.append(f"{invoice_value}{additional_info}")
        
        index = self._display_menu("Доступные инвойсы:", invoice_list)
        return data[index]
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """
        Подстановка данных в HTML шаблон.
        
        Args:
            template: HTML шаблон
            data: Данные для подстановки
            
        Returns:
            Отрендеренный HTML
        """
        # Используем простой формат {{ключ}} для подстановки
        rendered = template
        
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            rendered = rendered.replace(placeholder, str(value))
        
        return rendered
    
    def generate_pdf(self, html_content: str, output_filename: str) -> Path:
        """
        Генерация PDF из HTML.
        
        Args:
            html_content: HTML контент
            output_filename: Имя выходного файла
            
        Returns:
            Путь к созданному PDF
        """
        output_path = self.output_dir / output_filename
        
        # Добавляем стили для поддержки кириллицы
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @font-face {{
                    font-family: 'DejaVu Sans';
                    src: local('DejaVu Sans'), local('DejaVuSans');
                }}
                body {{
                    font-family: 'DejaVu Sans', 'Roboto', 'Arial', sans-serif;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Если HTML уже содержит <html>, используем как есть
        if '<html' in html_content.lower():
            styled_html = html_content
        
        # Генерация PDF
        HTML(string=styled_html).write_pdf(str(output_path))
        
        return output_path
    
    def _open_pdf(self, pdf_path: Path):
        """
        Открытие PDF в системной программе.
        
        Args:
            pdf_path: Путь к PDF файлу
        """
        system = platform.system()
        
        try:
            if system == "Windows":
                os.startfile(pdf_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(pdf_path)])
            elif system == "Linux":
                subprocess.run(["xdg-open", str(pdf_path)])
            else:
                print(f"⚠️  Не удалось автоматически открыть PDF. Откройте вручную: {pdf_path}")
        except Exception as e:
            print(f"⚠️  Ошибка при открытии PDF: {e}")
            print(f"   Откройте вручную: {pdf_path}")
    
    def run(self):
        """Основной цикл работы программы."""
        print("\n" + "="*60)
        print("  ГЕНЕРАТОР PDF ДОКУМЕНТОВ".center(60))
        print("="*60)
        
        # Выбор файла данных
        data_file = self.select_data_file()
        if not data_file:
            return
        
        # Выбор шаблона
        template_file = self.select_template()
        if not template_file:
            return
        
        # Загрузка данных
        try:
            data = self._load_data(data_file)
        except Exception as e:
            print(f"❌ Ошибка загрузки данных: {e}")
            return
        
        # Загрузка шаблона
        try:
            template = self._load_template(template_file)
        except Exception as e:
            print(f"❌ Ошибка загрузки шаблона: {e}")
            return
        
        # Выбор инвойса
        invoice = self.select_invoice(data)
        if not invoice:
            return
        
        # Генерация PDF
        print("\n⏳ Генерация PDF...")
        
        try:
            # Подстановка данных в шаблон
            rendered_html = self._render_template(template, invoice)
            
            # Формирование имени файла
            invoice_id = "document"
            for field in ['invoice_id', 'invoice', 'id', 'номер', 'invoice_number']:
                if field in invoice:
                    invoice_id = str(invoice[field])
                    break
            
            output_filename = f"invoice_{invoice_id}.pdf"
            
            # Создание PDF
            pdf_path = self.generate_pdf(rendered_html, output_filename)
            
            print(f"✅ PDF успешно создан: {pdf_path}")
            
            # Открытие PDF
            print("📄 Открытие PDF...")
            self._open_pdf(pdf_path)
            
        except Exception as e:
            print(f"❌ Ошибка генерации PDF: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Точка входа."""
    generator = PDFGenerator()
    generator.run()


if __name__ == "__main__":
    main()