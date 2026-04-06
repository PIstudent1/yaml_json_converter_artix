import yaml
import json
from pprint import pprint

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
        data['_type'] = obj_type
    
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
    '''Упрощение параметров условий до типа и выражения условия. Может потом убрать, так как полезно только для отладки.'''
    if 'conditions' in discount and isinstance(discount['conditions'], list):
        simplified = []
        for condition in discount['conditions']:
            if isinstance(condition, dict):
                # Оставляем только нужные поля
                simplified_condition = {
                    '_type': condition.get('_type'),
                    'condition': condition.get('condition')
                }
                simplified.append(simplified_condition)
        discount['conditions'] = simplified
    return discount


def main():
    # Регистрируем конструктор для всех тегов python/object:*
    yaml.add_multi_constructor('tag:yaml.org,2002:python/object:', construct)
    
    with open("template.yaml", 'r', encoding='utf-8') as f:
        templates = yaml.load(f, Loader=yaml.FullLoader)

    if isinstance(templates, list):
        templates = [filter_conditions(discount) for discount in templates]
    elif isinstance(templates, dict):
        templates = filter_conditions(templates)


    pprint(templates)

if __name__ == "__main__":
    main()