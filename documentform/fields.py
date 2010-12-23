from django import forms
from django.utils.encoding import smart_unicode
from django.utils.text import capfirst

from pymongo.errors import InvalidId
from pymongo.objectid import ObjectId

__all__ = ('ReferenceField', 'DocumentFormField')

# copy from django-mongoforms
class ReferenceField(forms.ChoiceField):
    """
    Reference field for mongo forms. Inspired by `django.forms.models.ModelChoiceField`.
    """
    def __init__(self, queryset, *args, **kwargs):
        forms.Field.__init__(self, *args, **kwargs)
        self.queryset = queryset

    def _get_queryset(self):
        return self._queryset

    def _set_queryset(self, queryset):
        self._queryset = queryset
        self.widget.choices = self.choices

    queryset = property(_get_queryset, _set_queryset)

    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices

        self._choices = [(obj.id, smart_unicode(obj)) for obj in self.queryset]
        return self._choices

    choices = property(_get_choices, forms.ChoiceField._set_choices)

    def clean(self, value):
        try:
            oid = ObjectId(value)
            oid = super(ReferenceField, self).clean(oid)
            obj = self.queryset.get(id=oid)
        except (TypeError, InvalidId, self.queryset._document.DoesNotExist):
            raise forms.ValidationError(self.error_messages['invalid_choice'] % {'value':value})
        return obj

pretty = lambda name: name and ' '.join([capfirst(i) for i in name.split('_')]) 

class DocumentFormField(object):
    def __call__(self, field, **kwargs):
        return self.formfield(field, **kwargs)

    def formfield(self, field, **kwargs):
        docfield_class = ('from_%s' % field.__class__.__name__).lower()

        if hasattr(self, docfield_class):
            #TODO smart_unicode label
            defaults = {'required' : field.required,
                    'label' : pretty(field.db_field),
                    'initial' : field.default}
            defaults.update(kwargs)
            return getattr(self, docfield_class)(field, **defaults)
        else:
            return NotImplementedError('%s for django form field is not implemented' % docfield_class)
    
    def from_stringfield(self, field, **kwargs):
        if hasattr(field, 'regex') and field.regex:
            defaults = { 'regex' : field.regex,
                    'min_length' : getattr(field, 'min_length', None),
                    'max_length' : getattr(field, 'max_length', None), }
            kwargs.update(defaults)
            return forms.RegexField(**kwargs)
        elif hasattr(field, 'choices'):
            defaults = { 'choices' : zip(field.choices, field.choices) }
            kwargs.update(defaults)
            return forms.ChoiceField(**kwargs)
        else:
            defaults = { 'min_length' : getattr(field, 'min_length', None),
                    'max_length' : getattr(field, 'max_length', None), }
            kwargs.update(defaults)
            return forms.CharField(**kwargs)

    def from_emailfield(self, field, **kwargs):
        defaults = { 'min_length' : getattr(field, 'min_length', None),
                'max_length' : getattr(field, 'max_length', None), }
        kwargs.update(defaults)
        return forms.EmailField(**kwargs)

    def from_urlfield(self, field, **kwargs):
        defaults = { 'min_length' : getattr(field, 'min_length', None),
                'max_length' : getattr(field, 'max_length', None), }
        kwargs.update(defaults)
        return forms.URLField(**kwargs)

    def from_intfield(self, field, **kwargs):
        defaults = { 'min_value' : getattr(field, 'min_value', None),
                'max_value' : getattr(field, 'max_value', None), }
        kwargs.update(defaults)
        return forms.IntegerField(**kwargs)

    def from_floatfield(self, field, **kwargs):
        defaults = { 'min_value' : getattr(field, 'min_value', None),
                'max_value' : getattr(field, 'max_value', None), }
        kwargs.update(defaults)
        return forms.FloatField(**kwargs)

    def from_decimalfield(self, field, **kwargs):
        defaults = { 'min_value' : getattr(field, 'min_value', None),
                'max_value' : getattr(field, 'max_value', None), }
        kwargs.update(defaults)
        return forms.DecimalField(**kwargs)

    def from_booleanfield(self, field, **kwargs):
        return forms.BooleanField(**kwargs)

    def from_datetimefield(self, field, **kwargs):
        return forms.DateTimeField(**kwargs)

    def from_referencefield(self, field, **kwargs):
        return ReferenceField(field.document_type.objects, **kwargs)

    #TODO self._id? get it out?!
    def from_objectidfield(self, field, **kwargs):
        return forms.CharField(widget=forms.HiddenInput(attrs={'readonly':'readonly'}), **kwargs)
