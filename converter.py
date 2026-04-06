import yaml
import json
from pprint import pprint



class DiscountTransformer:
    """Класс для трансформации Discount объектов"""
    
    def __init__(self):
        # Определяем правила трансформации
        self.rules = {
            'field_mapping': {
                'name': 'title', 
                'active': 'enabled',
                'discountRate': 'calculation_rate',
                'conditions': 'rules',
                'campaign': 'campaign_name'
            },
            'field_order': [
                'discount_id', 'title', 'enabled', 
                'calculation_rate', 'rules', 'campaign_name'
            ],
            'exclude_fields': [
                'cashText', 'clientDisplayText', 'clientText',
                'counters', 'coupons', 'discountMarks', 
                'gifts', 'objects', 'reports'
            ],
            'default_values': {
                'enabled': True,
                'calculation_rate': {'type': 'sum', 'value': '0'}
            }
        }
    
    def transform(self, data):
        
        if not isinstance(data, dict):
            return data
        
        result = {}
        
        # Применяем маппинг полей
        for old_key, new_key in self.rules['field_mapping'].items():
            if old_key in data and data[old_key] is not None:
                result[new_key] = data[old_key]
        
        # Добавляем поля, которые не были в маппинге (кроме исключенных)
        for key, value in data.items():
            if key not in self.rules['field_mapping']:
                if key not in self.rules['exclude_fields']:
                    if value is not None:
                        result[key] = value
        
        # Применяем значения по умолчанию для отсутствующих полей
        for key, default_value in self.rules['default_values'].items():
            if key not in result:
                result[key] = default_value
        
        # Сортируем поля согласно field_order
        ordered_result = {}
        for field in self.rules['field_order']:
            if field in result:
                ordered_result[field] = result[field]
        
        # Добавляем остальные поля в конец
        for field, value in result.items():
            if field not in ordered_result:
                ordered_result[field] = value
        
        return ordered_result

# Создаем экземпляр трансформера
transformer = DiscountTransformer()


def construct(loader, tag_suffix, node):
    
    obj_type = None
    if 'DiscountCardCondition' in tag_suffix:
        obj_type = 'CARD'
    elif 'DiscountCouponCondition' in tag_suffix:
        obj_type = 'COUPON'
    elif 'DiscountCondition' in tag_suffix:
        obj_type = 'REGULAR'
    elif 'CheckObject' in tag_suffix:
        obj_type = 'CHECK'
    elif 'PositionObject' in tag_suffix:
        obj_type = 'POSITION' 
    #elif 'Discount' in tag_suffix:
    #    obj_type = 'DISCOUNT'

    if isinstance(node, yaml.MappingNode):
        data = loader.construct_mapping(node)
    elif isinstance(node, yaml.SequenceNode):
        data = loader.construct_sequence(node)
    else:
        data = loader.construct_scalar(node)

    if obj_type and isinstance(data, dict):
        data['type'] = obj_type
    
    return data    

def filter_conditions(discount):
    """Фильтрует технические условия скидки"""
    if 'conditions' in discount and isinstance(discount['conditions'], list):
        discount['conditions'] = [
            condition for condition in discount['conditions']
            if condition.get('condition') != "not cf.isPartOfDisKit()" 
            and condition.get('condition') != "object['opcode'] != 63"
            and condition.get('condition') != "object['tmc']['price'] > object['tmc']['minprice']"
        ]
    '''Упращение параметров условий до типа и выражения условия. Может потом убрать, так как полезно только для отладки.'''
    if 'conditions' in discount and isinstance(discount['conditions'], list):
        simplified = []
        for condition in discount['conditions']:
            if isinstance(condition, dict):
                # Оставляем только нужные поля
                simplified_condition = {
                    'type': condition.get('type'),
                    'condition': condition.get('condition')
                }
                simplified.append(simplified_condition)
        discount['conditions'] = simplified
    return discount





def test_json_convert(template):
    with open('sw_templates.json', 'w') as f:
        json.dump(template, f)

    print("\nJSON")

    with open('sw_templates.json') as f:
        print(f.read())


def main():
    '''Регистрируем конструктор для всех тегов python/object:*'''
    yaml.add_multi_constructor('tag:yaml.org,2002:python/object:', construct)
    
    with open("template.yaml", 'r', encoding='utf-8') as f:
        templates = yaml.load(f, Loader=yaml.FullLoader)

    if isinstance(templates, list):
        templates = [filter_conditions(discount) for discount in templates]
    elif isinstance(templates, dict):
        templates = filter_conditions(templates)
    
    print("\nPYTHON OBJECT")

    pprint(templates)

if __name__ == "__main__":
    main()