# Em materiais/templatetags/materiais_extras.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite acessar o valor de um dicionário usando uma variável como chave no template.
    Uso: {{ meu_dicionario|get_item:minha_chave }}
    """
    return dictionary.get(key)