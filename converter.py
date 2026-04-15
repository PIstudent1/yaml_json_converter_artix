import yaml
import json
import random
from pprint import pprint
import os
import re


discount_type = None

class DiscountTransformer: 
    """Класс для трансформации Discount объектов"""

    def __init__(self):
        #Список полей, которые необходимо исключить
        self.exclude_fields = [
            'counters', 'coupons', 'discountMarks', 'gifts',
            'minPriceIgnored', 'showCashTextToConsultant', 'reports'
        ]
        self.discount_type = 'discount'
        #self.field_order = []
    def set_discount_type(self, discount_type):
        self.discount_type = discount_type
        return self

    def generate_default_id(self):
        """Генерирует случайный шестизначный ID"""
        return str(random.randint(100000, 999999))

    def transform_discount_rate(self, discount_rate):
        """Преобразует discountRate в rateType и calcExpr"""
        if not isinstance(discount_rate, dict):
            return None, None

        rate_type = discount_rate.get('type', '').upper()
        calc_expr = normalize_quotes(discount_rate.get('value'))

        return rate_type, calc_expr
    
    def transform_kit_discount_rate(self, discount_rate):
        '''Переобразует данные для наборной скидки'''
        kitItems = {}
        items = discount_rate.get('items')
        if items and isinstance(items, list) and len(items) > 0:
            for item in items:
                kit_item = item.get('kitItem')
                disc_rate = item.get('discountRate')
                if kit_item:
                    kitItems['count'] = kit_item.get('quantity')
                    conditions = kit_item.get('conditions')
                    if conditions and isinstance(conditions, list):
                        kitItems['conditionTemplates'] = []
                        for condition in conditions:
                            kitItems['conditionTemplates'].append({
                                'expression': normalize_quotes(condition.get('condition')),
                                'type': condition.get('type')
                            })                           
                if disc_rate:
                    kitItems['rateType'] = disc_rate.get('type', '').upper()
                    kitItems['value'] = normalize_quotes(disc_rate.get('value'))
        return kitItems
    
    def extract_objects(self, objects):
        kitItems = {}
        if objects and isinstance(objects, list) and len(objects) > 0:
            for obj in objects:
                items = obj.get('items')
                if items and isinstance(items, list) and len(items) > 0:
                    for item in items:
                        if item is None or not isinstance(item, dict):
                            continue 
                        kitItems['count'] = item.get('quantity')
                        kitItems['name'] = item.get('name')
                        objectType = item.get('type')
                        conditions = item.get('conditions')
                        if conditions and isinstance(conditions, list):
                            kitItems['conditionTemplates'] = []
                            for condition in conditions:
                                kitItems['conditionTemplates'].append({
                                    'expression': normalize_quotes(condition.get('condition')),
                                    'type': condition.get('type')
                                })

        return kitItems, objectType

    def extract_object_type(self, data):
        """Извлекает objectType из поля objects"""
        if 'objects' in data and isinstance(data['objects'], list):
            for obj in data['objects']:
                if isinstance(obj, dict) and 'type' in obj:
                    return obj['type']
        return None

    '''def reorder_fields(self, data):
        #Сортирует поля по порядку указанному в field_order.
        if not isinstance(data, dict):
            return data

        ordered_result = {}

        for field in self.field_order:
            if field in data:
                ordered_result[field] = data[field]

        for field, value in data.items():
            if field not in ordered_result:
                ordered_result[field] = value

        return ordered_result'''

    def transform(self, data):
        '''Приводит python объект полученный из yaml к правильному виду для дальнейшего перевода в json'''
        if not isinstance(data, dict):
            return data

        result = {}
        kitItems =  []
        if self.discount_type == 'kit':
            self.exclude_fields = [
                'counters', 'coupons', 'discountMarks', 'gifts',
                'minPriceIgnored', 'showCashTextToConsultant', 'reports',
                'clientDisplayText', 'clientText', 'cashText', 'campaign'
            ]

        # id
        result['id'] = self.generate_default_id()

        # name
        if 'name' in data:
            result['name'] = data['name']

        # active
        if 'active' in data:
            result['active'] = data['active']

        # conditions
        if 'conditions' in data:
            result['conditions'] = data['conditions']

        # discountRate
        if 'discountRate' in data:
            if self.discount_type == 'discount':
                rate_type, calc_expr = self.transform_discount_rate(data['discountRate'])
                if rate_type:
                    result['rateType'] = rate_type
                if calc_expr:
                    result['calcExpr'] = calc_expr
            else: 
                kitItems.append(self.transform_kit_discount_rate(data['discountRate']))
        
        if self.discount_type == 'discount': 
        # objectType
            object_type = self.extract_object_type(data)
            if object_type:
                result['objectType'] = object_type
        else:
            if 'objects' in data:
                kitItem, object_type = self.extract_objects(data['objects'])
                kitItems.append(kitItem)
                result['objectType'] = object_type

        # resultType
        if self.discount_type == 'discount': 
            result['resultType'] = "IMPACT"
        else:
            result['resultType'] = "KIT_OBJECT"

        result['kitItems'] = kitItems
        # остальные поля
        for key, value in data.items():
            if key not in self.exclude_fields:
                if key not in ['id', 'name', 'active', 'conditions', 'discountRate', 'objects']:
                    if value is not None:
                        result[key] = value

        return result

transformer = DiscountTransformer()

def normalize_quotes(value):
    """Заменяет двойные кавычки на одинарные"""
    if isinstance(value, str):
        return value.replace('"', "'")
    return value

def construct(loader, tag_suffix, node):
    obj_type = None

    '''Определяем тип объекта в зависимости от python-объекта в yaml'''
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
        #if 'Discount' in tag_suffix and 'Condition' not in tag_suffix:
        if tag_suffix == 'artixds.domain.Discount':
            return transformer.transform(data)

    elif isinstance(node, yaml.SequenceNode):
        data = loader.construct_sequence(node)

    else:
        data = loader.construct_scalar(node)

    if obj_type and isinstance(data, dict):
        data['type'] = obj_type

    return data


def filter_conditions(discount):
    """Фильтрует и упрощает условия"""

    if 'conditions' in discount and isinstance(discount['conditions'], list):

        # фильтрация
        discount['conditions'] = [
            c for c in discount['conditions']
            if c.get('condition') not in [
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

        discount['conditions'] = simplified

    return discount

def json_convert(template, file):
    '''Конвертация файла в json'''
    with open(file + '.json', 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    #print("\nJSON:")
    #with open('sw_templates.json', encoding='utf-8') as f:
    #    print(f.read())

def remove_aliases(file):
    '''Удаляем вхождение ссылок и якорей типа &id001, *id001 в yaml'''
    file = re.sub(r'\s+&\w+', '', file)
    file = re.sub(r'\*\w+', 'null', file)
    return file

def main():
    #Cоздается конструктор для чтения python-объектов из yaml файла. Пример объекта - - !!python/object:artixds.domain.Discount
    yaml.add_multi_constructor('tag:yaml.org,2002:python/object:', construct)
    
    yaml_file = input("\nУкажите путь до yaml файла со скидкой (yaml должен содержать скидку, а не акцию!):")

    #Формирование python-щбъекта на основе загруженного yaml
    with open(yaml_file, 'r', encoding='utf-8') as f:
        f = remove_aliases(f.read())
        templates = yaml.load(f, Loader=yaml.FullLoader)

    #Обработка python-объекта
    if isinstance(templates, list):
        templates = [filter_conditions(d) for d in templates]
    elif isinstance(templates, dict):
        templates = filter_conditions(templates)

    templates = {
        "resultTemplates": templates
    }

    #print("\nPYTHON OBJECT:")
    #pprint(templates)

    json_convert(templates, file = os.path.splitext(yaml_file)[0])


if __name__ == "__main__":
    main()