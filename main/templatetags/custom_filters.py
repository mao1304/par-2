from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divide el valor por el argumento"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None

@register.filter
def mod(value, arg):
    """Obtiene el módulo del valor dividido por el argumento"""
    try:
        return float(value) % float(arg)
    except (ValueError, ZeroDivisionError):
        return None 