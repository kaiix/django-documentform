# coding: utf-8
from types import NoneType

from django.forms import BaseForm
from django.forms import Field
from django.forms.util import flatatt, ErrorDict, ErrorList
from django.utils.datastructures import SortedDict

from mongoengine.base import BaseDocument

from fields import DocumentFormField
from fields import ReferenceField

__all__ = ('DocumentForm',)

# copy from django
def get_declared_fields(bases, attrs, with_base_fields=True):
    fields = [(field_name, attrs.pop(field_name)) for field_name, obj in attrs.items() if isinstance(obj, Field)]
    fields.sort(lambda x, y: cmp(x[1].creation_counter, y[1].creation_counter))

    if with_base_fields:
        for base in bases[::-1]:
            if hasattr(base, 'base_fields'):
                fields = base.base_fields.items() + fields
    else:
        for base in bases[::-1]:
            if hasattr(base, 'declared_fields'):
                fields = base.declared_fields.items() + fields

    return SortedDict(fields)

class DocumentFormMetaOptions(object):
    def __init__(self, options=None):
        self.document = getattr(options, 'document', None)
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', [])
        self.widgets = getattr(options, 'widgets', None)
        # define custom labels
        self.labels = getattr(options, 'labels', None)

def fields_for_document(document, fields=None, exclude=None, widgets=None, labels=None, formfield_callback=DocumentFormField()):
    field_list = []
    ignored = []

    #TODO editable
    for f in document._fields.values():
        if fields and not f.db_field in fields:
            continue
        if exclude and f.db_field in exclude:
            continue
        if widgets and f.db_field in widgets:
            kwargs = {'widget': widgets[f.db_field]}
        else:
            kwargs = {}
        # hack for labels
        if labels and f.db_field in labels:
            kwargs['label'] = labels[f.db_field]
        formfield = formfield_callback(f, **kwargs)
        if formfield:
            field_list.append((f.db_field, formfield))
        else:
            ignored.append(f.db_field)
    
    field_dict = SortedDict(field_list)
    #why do this
    if fields:
        field_dict = SortedDict(
            [(f, field_dict.get(f)) for f in fields
                if ((not exclude) or (exclude and f not in exclude)) and (f not in ignored)]
        )
    return field_dict

class DocumentFormMetaClass(type):
    def __new__(cls, name, bases, attrs):
        formfield_callback = attrs.pop('formfield_callback', DocumentFormField())
        try:
            parents = [b for b in bases if issubclass(b, DocumentForm)]
        except NameError:
            parents = None

        declared_fields = get_declared_fields(bases, attrs, False)
        new_class = super(DocumentFormMetaClass, cls).__new__(cls, name, bases, attrs)
        
        if not parents:
            return new_class

        opts = new_class._meta = DocumentFormMetaOptions(getattr(new_class, 'Meta', None))

        if opts.document:
            fields = fields_for_document(opts.document, opts.fields, opts.exclude, 
                    opts.widgets, opts.labels, formfield_callback)
            # overwrite document field from self-defined field
            fields.update(declared_fields)
        else:
            fields = declared_fields
        
        new_class.declared_fields = declared_fields
        new_class.base_fields = fields
        return new_class

class DocumentForm(BaseForm):
    __metaclass__ = DocumentFormMetaClass

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, instance=None):

        assert isinstance(instance, (NoneType, BaseDocument)) 
        assert hasattr(self, 'Meta')
        
        opts = self._meta
        
        if instance is None:
            if opts.document is None:
                raise ValueError('DocumentForm has no document class specified.')
            self.instance = opts.document()
            object_data = {}
            self.instance._adding = True
        else:
            self.instance = instance
            self.instance._adding = False
            # use instance to initial the form
            object_data = document_to_dict(instance, opts.fields, opts.exclude)

        if initial is not None:
            object_data.update(initial)

        #...
        self._validate_unique = False
        super(DocumentForm, self).__init__(data, None, auto_id, prefix,
                object_data, error_class, label_suffix, empty_permitted)

    def save(self, commit=True):
        opts = self._meta

        for f in opts.document._fields.values():
            if opts.fields and f.db_field not in opt.fields:
                continue
            if opts.exclude and f.db_field in opt.exclude:
                continue
            if f.db_field in self.cleaned_data:
                setattr(self.instance, f.db_field, self.cleaned_data[f.db_field])

        if commit:
            self.instance.save()

        return self.instance

def document_to_dict(instance, fields, exclude):
    data = {}
    for f in instance._fields.values():
        if fields and not f.db_field in fields:
            continue
        if exclude and f.db_field in exclude:
            continue
        if isinstance(f, ReferenceField):
            data[f.db_field] = str(getattr(f, 'id', None))
        else:
            data[f.db_field] = getattr(instance, f.db_field, None)

    return data
