import yaml
import json
import random
from pprint import pprint
import os
import re
import sys
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

discount_type = None

class DiscountTransformerError(Exception):
    """Базовое исключение для ошибок трансформации скидок"""
    pass

class DiscountTransformer:
    """Класс для трансформации Discount объектов"""

    def __init__(self):
        # Список полей, которые необходимо исключить
        self.exclude_fields = [
            'counters', 'coupons', 'discountMarks', 'gifts',
            'minPriceIgnored', 'showCashTextToConsultant', 'reports'
        ]
        self.discount_type = 'discount'
        
    def set_discount_type(self, discount_type):
        """Устанавливает тип скидки"""
        if discount_type not in ['discount', 'kit']:
            raise ValueError(f"Некорректный тип скидки: {discount_type}. Допустимые значения: 'discount', 'kit'")
        self.discount_type = discount_type
        return self

    def generate_default_id(self):
        """Генерирует случайный шестизначный ID"""
        try:
            return str(random.randint(100000, 999999))
        except Exception as e:
            logger.error(f"Ошибка генерации ID: {e}")
            # Возвращаем резервный ID на основе времени
            import time
            return str(int(time.time()) % 1000000)

    def transform_discount_rate(self, discount_rate):
        """Преобразует discountRate в rateType и calcExpr"""
        if not isinstance(discount_rate, dict):
            logger.warning(f"discountRate не является словарем: {type(discount_rate)}")
            return None, None

        try:
            rate_type = discount_rate.get('type', '').upper()
            calc_expr = normalize_quotes(discount_rate.get('value'))
            return rate_type, calc_expr
        except Exception as e:
            logger.error(f"Ошибка преобразования discountRate: {e}")
            return None, None
    
    def transform_kit_discount_rate(self, discount_rate):
        """Преобразует данные для наборной скидки"""
        if not isinstance(discount_rate, dict):
            logger.warning(f"discount_rate не является словарем: {type(discount_rate)}")
            return {}
            
        kitItems = {}
        try:
            items = discount_rate.get('items')
            if items and isinstance(items, list) and len(items) > 0:
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        logger.warning(f"Элемент {idx} в items не является словарем, пропускаем")
                        continue
                        
                    kit_item = item.get('kitItem')
                    disc_rate = item.get('discountRate')
                    
                    if kit_item and isinstance(kit_item, dict):
                        kitItems['count'] = kit_item.get('quantity')
                        conditions = kit_item.get('conditions')
                        if conditions and isinstance(conditions, list):
                            kitItems['conditionTemplates'] = []
                            for cond_idx, condition in enumerate(conditions):
                                if isinstance(condition, dict):
                                    kitItems['conditionTemplates'].append({
                                        'expression': normalize_quotes(condition.get('condition')),
                                        'type': condition.get('type')
                                    })
                                else:
                                    logger.warning(f"Условие {cond_idx} не является словарем, пропускаем")
                                    
                    if disc_rate and isinstance(disc_rate, dict):
                        kitItems['rateType'] = disc_rate.get('type', '').upper()
                        kitItems['value'] = normalize_quotes(disc_rate.get('value'))
        except Exception as e:
            logger.error(f"Ошибка преобразования kit discount rate: {e}")
            
        return kitItems
    
    def extract_objects(self, objects):
        """Извлекает объекты из структуры"""
        kitItems = {}
        objectType = None
        
        if not objects or not isinstance(objects, list):
            logger.warning(f"objects не является списком или пуст: {type(objects)}")
            return kitItems, objectType
            
        try:
            for obj_idx, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    logger.warning(f"Объект {obj_idx} не является словарем, пропускаем")
                    continue
                    
                items = obj.get('items')
                if items and isinstance(items, list) and len(items) > 0:
                    for item_idx, item in enumerate(items):
                        if item is None or not isinstance(item, dict):
                            logger.warning(f"Элемент {item_idx} в объекте {obj_idx} некорректен, пропускаем")
                            continue
                            
                        kitItems['count'] = item.get('quantity')
                        kitItems['name'] = item.get('name')
                        objectType = item.get('type')
                        
                        conditions = item.get('conditions')
                        if conditions and isinstance(conditions, list):
                            kitItems['conditionTemplates'] = []
                            for cond_idx, condition in enumerate(conditions):
                                if isinstance(condition, dict):
                                    kitItems['conditionTemplates'].append({
                                        'expression': normalize_quotes(condition.get('condition')),
                                        'type': condition.get('type')
                                    })
                                else:
                                    logger.warning(f"Условие {cond_idx} не является словарем, пропускаем")
                                    
        except Exception as e:
            logger.error(f"Ошибка извлечения объектов: {e}")
            
        return kitItems, objectType

    def extract_object_type(self, data):
        """Извлекает objectType из поля objects"""
        if not isinstance(data, dict):
            return None
            
        try:
            if 'objects' in data and isinstance(data['objects'], list):
                for obj in data['objects']:
                    if isinstance(obj, dict) and 'type' in obj:
                        return obj['type']
        except Exception as e:
            logger.error(f"Ошибка извлечения objectType: {e}")
            
        return None

    def transform_discount(self, result, data):
        """Трансформирует обычную скидку"""
        if not isinstance(result, dict) or not isinstance(data, dict):
            raise DiscountTransformerError("result и data должны быть словарями")
            
        try:
            if 'discountRate' in data:
                rate_type, calc_expr = self.transform_discount_rate(data['discountRate'])
                if rate_type:
                    result['rateType'] = rate_type
                if calc_expr:
                    result['calcExpr'] = calc_expr

            object_type = self.extract_object_type(data)
            if object_type:
                result['objectType'] = object_type

            result['resultType'] = "IMPACT"
        except Exception as e:
            logger.error(f"Ошибка трансформации скидки: {e}")
            raise DiscountTransformerError(f"Не удалось трансформировать скидку: {e}")

        return result

    def transform_kit_discount(self, result, data):
        """Трансформирует наборную скидку"""
        if not isinstance(result, dict) or not isinstance(data, dict):
            raise DiscountTransformerError("result и data должны быть словарями")
            
        try:
            self.exclude_fields = [
                'counters', 'coupons', 'discountMarks', 'gifts',
                'minPriceIgnored', 'showCashTextToConsultant', 'reports',
                'clientDisplayText', 'clientText', 'cashText', 'campaign'
            ]
            
            kitItems = []
            
            if 'discountRate' in data:
                kit_items = self.transform_kit_discount_rate(data['discountRate'])
                if kit_items:
                    kitItems.append(kit_items)

            if 'objects' in data:
                kitItem, object_type = self.extract_objects(data['objects'])
                if kitItem:
                    kitItems.append(kitItem)
                if object_type:
                    result['objectType'] = object_type
            
            result['resultType'] = "KIT_OBJECT"
            result['kitItems'] = kitItems
            
        except Exception as e:
            logger.error(f"Ошибка трансформации наборной скидки: {e}")
            raise DiscountTransformerError(f"Не удалось трансформировать наборную скидку: {e}")

        return result

    def transform(self, data):
        """Приводит python объект полученный из yaml к правильному виду для дальнейшего перевода в json"""
        if not isinstance(data, dict):
            logger.warning(f"Ожидался словарь, получен {type(data)}")
            return data
            
        result = {}
        
        try:
            # id
            result['id'] = self.generate_default_id()

            # name
            if 'name' in data and data['name'] is not None:
                result['name'] = data['name']
            else:
                logger.warning("Отсутствует поле 'name' в данных скидки")

            # active
            if 'active' in data:
                result['active'] = data['active']

            # conditions
            if 'conditions' in data and data['conditions'] is not None:
                result['conditions'] = data['conditions']

            if self.discount_type == 'discount':
                self.transform_discount(result, data)
            else:
                self.transform_kit_discount(result, data)

            # остальные поля
            for key, value in data.items():
                if key not in self.exclude_fields:
                    if key not in ['id', 'name', 'active', 'conditions', 'discountRate', 'objects']:
                        if value is not None:
                            result[key] = value
                            
        except Exception as e:
            logger.error(f"Ошибка в методе transform: {e}")
            raise DiscountTransformerError(f"Трансформация данных не удалась: {e}")

        return result

def normalize_quotes(value):
    """Заменяет двойные кавычки на одинарные"""
    if isinstance(value, str):
        try:
            return value.replace('"', "'")
        except Exception as e:
            logger.error(f"Ошибка нормализации кавычек: {e}")
            return value
    return value

def construct(loader, tag_suffix, node):
    """Конструктор для yaml объектов"""
    obj_type = None
    
    try:
        # Определяем тип объекта в зависимости от python-объекта в yaml
        if 'DiscountCardCondition' in tag_suffix:
            obj_type = 'CARD'
        elif 'DiscountCouponCondition' in tag_suffix:
            obj_type = 'COUPON'
        elif 'DiscountCondition' in tag_suffix:
            obj_type = 'COMMON'
        elif 'CheckObject' in tag_suffix:
            obj_type = 'CHECK'
        elif 'PositionObject' in tag_suffix:
            obj_type = 'POSITION'
        elif 'KitObjectItem' in tag_suffix:
            obj_type = 'KIT_OBJECT'
        elif 'KitDiscountRate' in tag_suffix:
            transformer.set_discount_type('kit')

        if isinstance(node, yaml.MappingNode):
            data = loader.construct_mapping(node, deep=True)
            if tag_suffix == 'artixds.domain.Discount':
                return transformer.transform(data)

        elif isinstance(node, yaml.SequenceNode):
            data = loader.construct_sequence(node)

        else:
            data = loader.construct_scalar(node)

        if obj_type and isinstance(data, dict):
            data['type'] = obj_type

        return data
        
    except Exception as e:
        logger.error(f"Ошибка в конструкторе yaml для тега {tag_suffix}: {e}")
        return None

def filter_conditions(discount):
    """Фильтрует и упрощает условия"""
    if not isinstance(discount, dict):
        logger.warning(f"filter_conditions: ожидался словарь, получен {type(discount)}")
        return discount
        
    try:
        if 'conditions' in discount and isinstance(discount['conditions'], list):
            # фильтрация
            discount['conditions'] = [
                c for c in discount['conditions']
                if isinstance(c, dict) and c.get('condition') not in [
                    "not cf.isPartOfDisKit()",
                    "object['opcode'] != 63",
                    "object['tmc']['price'] > object['tmc']['minprice']"
                ]
            ]

            # упрощение
            simplified = []
            for condition in discount['conditions']:
                if isinstance(condition, dict):
                    simplified.append({
                        'type': condition.get('type'),
                        'expression': normalize_quotes(condition.get('condition'))
                    })
                else:
                    logger.warning(f"Пропущено некорректное условие: {condition}")

            discount['conditions'] = simplified
    except Exception as e:
        logger.error(f"Ошибка фильтрации условий: {e}")
        
    return discount

def json_convert(template, file):
    """Конвертация файла в json"""
    if not template:
        logger.error("Нет данных для сохранения в JSON")
        return False
        
    try:
        # Создаем директорию, если она не существует
        output_dir = os.path.dirname(file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(file + '.json', 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
            
        logger.info(f"JSON файл успешно создан: {file}.json")
        return True
        
    except IOError as e:
        logger.error(f"Ошибка записи JSON файла: {e}")
        return False
    except TypeError as e:
        logger.error(f"Ошибка сериализации в JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при сохранении JSON: {e}")
        return False

def remove_aliases(file_content):
    """Удаляем вхождение ссылок и якорей типа &id001, *id001 в yaml"""
    if not isinstance(file_content, str):
        logger.warning("remove_aliases: ожидалась строка")
        return file_content
        
    try:
        file_content = re.sub(r'\s+&\w+', '', file_content)
        file_content = re.sub(r'\*\w+', 'null', file_content)
    except Exception as e:
        logger.error(f"Ошибка удаления алиасов: {e}")
        
    return file_content

def validate_yaml_file(file_path):
    """Валидация YAML файла перед загрузкой"""
    # Проверка существования файла
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    # Проверка расширения файла
    if not file_path.lower().endswith(('.yaml', '.yml')):
        raise ValueError(f"Файл должен иметь расширение .yaml или .yml: {file_path}")
    
    # Проверка размера файла
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError(f"Файл пуст: {file_path}")
    if file_size > 10 * 1024 * 1024:  # 10 MB
        logger.warning(f"Файл очень большой ({file_size / 1024 / 1024:.2f} MB)")
    
    # Проверка читаемости файла
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Нет прав на чтение файла: {file_path}")
    
    return True

def main():
    """Главная функция программы"""
    try:
        # Создается конструктор для чтения python-объектов из yaml файла
        yaml.add_multi_constructor('tag:yaml.org,2002:python/object:', construct)
        
        # Запрос пути к файлу с проверкой
        max_attempts = 3
        for attempt in range(max_attempts):
            yaml_file = input("\nУкажите путь до yaml файла со скидкой (yaml должен содержать скидку, а не акцию!):").strip()
            
            if not yaml_file:
                print("Путь к файлу не может быть пустым. Попробуйте снова.")
                continue
                
            try:
                validate_yaml_file(yaml_file)
                break
            except FileNotFoundError as e:
                print(f"Ошибка: {e}")
                if attempt == max_attempts - 1:
                    print("Превышено количество попыток. Программа завершена.")
                    return
                continue
            except (ValueError, PermissionError) as e:
                print(f"Ошибка: {e}")
                if attempt == max_attempts - 1:
                    print("Превышено количество попыток. Программа завершена.")
                    return
                continue
        else:
            print("Не удалось указать корректный файл. Программа завершена.")
            return
        
        # Формирование python-объекта на основе загруженного yaml
        logger.info(f"Начинаю обработку файла: {yaml_file}")
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
                if not file_content:
                    raise ValueError("Файл пуст")
                    
                file_content = remove_aliases(file_content)
                templates = yaml.load(file_content, Loader=yaml.FullLoader)
                
                if templates is None:
                    raise ValueError("YAML файл не содержит данных")
                    
        except yaml.YAMLError as e:
            logger.error(f"Ошибка парсинга YAML: {e}")
            print(f"Ошибка в синтаксисе YAML файла: {e}")
            return
        except IOError as e:
            logger.error(f"Ошибка чтения файла: {e}")
            print(f"Не удалось прочитать файл: {e}")
            return
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке файла: {e}")
            print(f"Ошибка при загрузке файла: {e}")
            return

        # Обработка python-объекта
        logger.info("Начинаю обработку данных")
        
        try:
            if isinstance(templates, list):
                if not templates:
                    logger.warning("Список скидок пуст")
                templates = [filter_conditions(d) for d in templates if d is not None]
            elif isinstance(templates, dict):
                templates = filter_conditions(templates)
            else:
                logger.error(f"Неожиданный тип данных: {type(templates)}")
                print("Ошибка: загруженные данные имеют неверный формат")
                return

            templates = {
                "resultTemplates": templates
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки данных: {e}")
            print(f"Не удалось обработать данные: {e}")
            return

        # Конвертация в JSON
        output_file = os.path.splitext(yaml_file)[0]
        if json_convert(templates, output_file):
            print(f"\n✅ Конвертация успешно завершена! JSON файл сохранен как: {output_file}.json")
            logger.info("Программа успешно завершена")
        else:
            print("\n❌ Ошибка при сохранении JSON файла")
            
    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем")
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в программе: {e}", exc_info=True)
        print(f"\n❌ Произошла критическая ошибка: {e}")
        print("Пожалуйста, проверьте лог для получения дополнительной информации")

if __name__ == "__main__":
    main()