# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import shutil
import tempfile

from django import forms
from django.utils.datastructures import SortedDict
from django.core.files.uploadedfile import UploadedFile

from rvbd.common import datetime_to_seconds

from apps.report.models import Report, Widget
from apps.datasource.models import Criteria

import logging
logger = logging.getLogger(__name__)

DURATIONS = ('Default', '15 min', '1 hour', 
             '2 hours', '4 hours', '12 hours', '1 day',
             '1 week', '4 weeks')


class ReportDetailForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ReportDetailForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Report


class WidgetDetailForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(WidgetDetailForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Widget
        exclude = ['tables', 'module', 'uiwidget', 'uioptions']


class ReportDateWidget(forms.DateInput):
    """ Custom DateWidget for Reports
    """

    def __init__(self, attrs=None, format=None):
        final_attrs = {'class': 'date'}
        if attrs is not None:
            final_attrs.update(attrs)
        super(ReportDateWidget, self).__init__(attrs=final_attrs, format=format)

    def render(self, *args, **kwargs):
        msg = '{0} <span id="datenow" class="icon-calendar" title="Set date to today"> </span> '
        return msg.format(super(ReportDateWidget, self).render(*args, **kwargs))


class ReportTimeWidget(forms.TimeInput):
    """ Custom TimeWidget for Reports
    """

    def __init__(self, attrs=None, format=None):
        final_attrs = {'class': 'time'}
        if attrs is not None:
            final_attrs.update(attrs)
        super(ReportTimeWidget, self).__init__(attrs=final_attrs, format=format)

    def render(self, *args, **kwargs):
        msg = '{0} <span id="timenow" class="icon-time" title="Set time/date to now"> </span> '
        return msg.format(super(ReportTimeWidget, self).render(*args, **kwargs))


class ReportSplitDateTimeWidget(forms.SplitDateTimeWidget):
    """ A SplitDateTime Widget that uses overridden Report widgets
    """
    def __init__(self, attrs=None):
        split_widgets = [ReportDateWidget, ReportTimeWidget]
        # Note that we're calling MultiWidget, not SplitDateTimeWidget, because
        # we want to define widgets.
        forms.MultiWidget.__init__(self, split_widgets, attrs)


class ReportCriteriaForm(forms.Form):
    """ Base Form for Report Criteria
    """
    # css definitions
    error_css_class = 'text-error'

    # field definitions
    endtime = forms.DateTimeField(label='Report End Time',
                                  input_formats=['%m/%d/%Y %I:%M %p'], 
                                  widget=ReportSplitDateTimeWidget)
    duration = forms.ChoiceField(choices=zip(DURATIONS, DURATIONS),
                                 widget=forms.Select(attrs={'class': 'duration'}))
    filterexpr = forms.CharField(label='Filter Expression',
                                 required=False, max_length=100,
                                 widget=forms.TextInput(attrs={'class': 'filterexpr'}))
    ignore_cache = forms.BooleanField(required=False, widget=forms.HiddenInput)
    debug = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, extra=None, **kwargs):
        """ Handle arbitrary number of additional fields in `extra` keyword

            Keyword argument options:

            `extra` optional, a list of TableCriteria objects to append to
                    form listings

            Standard Form criteria options `data` and `files` should be used
            as kwargs instead of args.
            
        """
        super(ReportCriteriaForm, self).__init__(**kwargs)

        if extra:
            logging.debug('creating ReportCriteriaForm, with extra fields: %s' % extra)
            for field in extra:
                field_id = 'criteria_%s' % field.id
                field_cls = eval(field.field_type)
                if field.field_kwargs is not None:
                    fkwargs = field.field_kwargs
                else:
                    fkwargs = {}

                self.fields[field_id] = field_cls(label=field.label,
                                                  required=field.required,
                                                  initial=field.initial,
                                                  **fkwargs)

                self.initial[field_id] = field.initial
                
    def criteria(self):
        """ Return certain field values as a dict for simple json parsing
        """
        result = {}
        for k, v in self.cleaned_data.iteritems():
            if k == 'endtime':
                result[k] = datetime_to_seconds(v)
            elif isinstance(v, UploadedFile):
                # look for uploaded files, save them off to another
                # temporary file and return the path for use in JSON
                # consumers of this file will need to clean them up
                # TODO this will be replaced by the File Storage App
                newtemp = tempfile.NamedTemporaryFile(delete=False)
                v.seek(0)
                shutil.copyfileobj(v, newtemp)
                v.close()
                newtemp.close()
                result[k] = newtemp.name
            elif k != 'debug':
                result[k] = v
        return result


class ReportCriteriaJSONForm(ReportCriteriaForm):
    """ Subclass to handle validation of JSON submission of equivalent form

        Since some fields will be returned via JSON in a different manner
        than the initial form submission, this class modifies the field types
    """
    def __init__(self, **kwargs):
        super(ReportCriteriaJSONForm, self).__init__(**kwargs)
        
        for k, v in self.fields.iteritems():
            if isinstance(v, forms.FileField):
                # FileFields instead have a pathname to the stored tempfile
                new_field = forms.CharField(label=v.label, initial=v.initial)
                self.fields[k] = new_field

        # toggle endtime formfield to handle timestamps via IntegerField
        self.fields['endtime'] = forms.IntegerField()


def create_report_criteria_form(report, jsonform=False, **kwargs):
    """ Create a form for this report.

        Any TableCriteria objects linked to this report or it's
        widgets are passed to the initialization method for a
        ReportCriteriaForm.
        
        If the report has no associated TableCriteria, nothing
        special will occur, and a nominal form will be returned.
        
        Only criteria objects which have no 'parent' will be included,
        'parent' objects will later provide the form values
        to all children criteria during processing.

    """
    # use SortedDict to limit to unique criteria objects only
    extra = SortedDict()

    # Collect all criteria objects tied to this report
    for c in report.criteria.all():
        if not c.parent:
            extra[c.id] = c

    # Collect all criteria objects tied to any widgets associated with report
    for widget in Widget.objects.filter(report=report):
        for table in widget.tables.all():
            for tc in table.criteria.all():
                if not tc.parent:
                    extra[tc.id] = tc

    kwargs['extra'] = extra.values()
    if jsonform:
        return ReportCriteriaJSONForm(**kwargs)
    else:
        return ReportCriteriaForm(**kwargs)
