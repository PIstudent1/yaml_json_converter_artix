import yaml
import json
import random
from pprint import pprint


def normalize_quotes(value):
    """Заменяет двойные кавычки на одинарные"""
    if isinstance(value, str):
        return value.replace('"', "'")
    return value


class DiscountTransformer:
    """Класс для трансформации Discount объектов"""

    def __init__(self):
        self.exclude_fields = [
            'counters', 'coupons', 'discountMarks', 'gifts',
            'minPriceIgnored', 'showCashTextToConsultant', 'reports'
        ]
        self.field_order = []

    def generate_default_id(self):
        """Генерирует случайный шестизначный ID"""
        return str(random.randint(100000, 999999))  # строка!

    def transform_discount_rate(self, discount_rate):
        """Преобразует discountRate в rateType и calcExpr"""
        if not isinstance(discount_rate, dict):
            return None, None

        rate_type = discount_rate.get('type', '').upper()
        calc_expr = normalize_quotes(discount_rate.get('value'))

        return rate_type, calc_expr

    def extract_object_type(self, data):
        """Извлекает objectType из поля objects"""
        if 'objects' in data and isinstance(data['objects'], list):
            for obj in data['objects']:
                if isinstance(obj, dict) and 'type' in obj:
                    return obj['type']
        return None

    def reorder_fields(self, data):
        if not isinstance(data, dict):
            return data

        ordered_result = {}

        for field in self.field_order:
            if field in data:
                ordered_result[field] = data[field]

        for field, value in data.items():
            if field not in ordered_result:
                ordered_result[field] = value

        return ordered_result

    def transform(self, data):
        if not isinstance(data, dict):
            return data

        result = {}

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
            rate_type, calc_expr = self.transform_discount_rate(data['discountRate'])
            if rate_type:
                result['rateType'] = rate_type
            if calc_expr:
                result['calcExpr'] = calc_expr

        # objectType
        object_type = self.extract_object_type(data)
        if object_type:
            result['objectType'] = object_type

        # resultType
        result['resultType'] = "IMPACT"

        # остальные поля
        for key, value in data.items():
            if key not in self.exclude_fields:
                if key not in ['id', 'name', 'active', 'conditions', 'discountRate', 'objects']:
                    if value is not None:
                        result[key] = value

        return self.reorder_fields(result)

transformer = DiscountTransformer()

def construct(loader, tag_suffix, node):
    obj_type = None

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

    if isinstance(node, yaml.MappingNode):
        data = loader.construct_mapping(node, deep=True)

        if 'Discount' in tag_suffix and 'Condition' not in tag_suffix:
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


def json_convert(template):
    with open('sw_templates.json', 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    #print("\nJSON:")
    #with open('sw_templates.json', encoding='utf-8') as f:
    #    print(f.read())


def main():
    yaml.add_multi_constructor('tag:yaml.org,2002:python/object:', construct)

    with open("template.yaml", 'r', encoding='utf-8') as f:
        templates = yaml.load(f, Loader=yaml.FullLoader)

    # обработка
    if isinstance(templates, list):
        templates = [filter_conditions(d) for d in templates]
    elif isinstance(templates, dict):
        templates = filter_conditions(templates)

    templates = {
        "resultTemplates": templates
    }

    #print("\nPYTHON OBJECT:")
    #pprint(templates)

    json_convert(templates)


if __name__ == "__main__":
    main()