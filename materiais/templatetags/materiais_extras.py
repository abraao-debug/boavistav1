from django import template
from django.http import QueryDict

register = template.Library()

@register.filter
def remove_param(query_string, keys_to_remove):
    """
    Remove uma ou mais chaves de uma query string de URL.
    Exemplo de uso: {{ request.GET.urlencode|remove_param:'sort,dir' }}
    """
    keys_to_remove = keys_to_remove.split(',')
    query_dict = QueryDict(query_string).copy()
    for key in keys_to_remove:
        if key in query_dict:
            del query_dict[key]
    return query_dict.urlencode()

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)