# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import os
import subprocess

from django.http import Http404, HttpResponse, StreamingHttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.shortcuts import render_to_response
from django.forms.models import modelformset_factory, inlineformset_factory

from apps.console.models import Utility, Results, Parameter, Job
from apps.console.forms import ExecuteForm, UtilityDetailForm, ParameterDetailForm

from project.settings import PROJECT_ROOT

SCRIPT_DIR = os.path.join(PROJECT_ROOT,'apps', 'console', 'scripts')

def main(request):
    """ Provide list of installed scripts
    """
    utilities = Utility.objects.all().select_related()
    return render_to_response('main.html',
                              {'utilities': utilities},
                              context_instance=RequestContext(request))


def refresh(request):
    """ Re-populate Utility store based on contents of scripts folder
    """
    ignores = [lambda x:x.endswith('.swp'),
               lambda x:x.endswith('~'),
               lambda x:x.endswith('.bak'),
               lambda x:x.startswith('.'),
               ]

    utilities = [u.name for u in Utility.objects.all()]
    files = os.listdir(SCRIPT_DIR)
    files = [x for x in files if not any(c(x) for c in ignores)]

    for f in files:
        if f not in utilities:
            Utility(name=f, path=SCRIPT_DIR).save()
    return HttpResponseRedirect('/console')


def detail(request, script_id):
    """ Return details about specific script
    """
    ParameterFormSet = inlineformset_factory(Utility,
                                             Parameter,
                                             form=ParameterDetailForm,
                                             extra=1)

    try:
        utility = Utility.objects.get(pk=script_id)
    except:
        raise Http404

    if request.method == 'POST':
        form = UtilityDetailForm(request.POST, instance=utility)
        formset = ParameterFormSet(request.POST, instance=utility)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return HttpResponseRedirect(request.META['HTTP_REFERER'])
        else:
            from IPython import embed; embed()


            #if form.is_valid():
            #    raise
            #if formset.is_valid():
            #    raise
    else:
        form = UtilityDetailForm(instance=utility)
        formset = ParameterFormSet(instance=utility)

    return render_to_response('detail.html',
                              {'utility': utility,
                               'form': form,
                               'formset': formset},
                              context_instance=RequestContext(request))


def run(request, script_id):
    """ Execute utility script
    """
    try:
        utility = Utility.objects.get(pk=script_id)
    except:
        raise Http404

    if request.method == 'POST':
        form = ExecuteForm(request.POST, instance=utility)
        if form.is_valid():
            return StreamingHttpResponse(execute(utility, form))
        else:
            return HttpResponse('Error Processing Form.')
    else:
        form = ExecuteForm(instance=utility)

    return render_to_response('run.html',
                              {'utility': utility,
                               'executeForm': form},
                              context_instance=RequestContext(request))


def execute(utility, form):
    """ Executes the given utility, streaming stdout in the response

        Any report on stderr will prompt an attempt to generate
        help data for further information.
    """
    res = []
    path = os.path.join(SCRIPT_DIR, utility.name)
    print path

    p = subprocess.Popen(path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    line = p.stdout.readline()
    while line:
        res.append(line)
        print line
        # force browser buffer to flush with spaces
        #yield '{} <br> {}'.format(line, ' '*1024)
        yield '{}'.format(line)
        line = p.stdout.readline()
    p.stdout.close()

    errflag = False
    err = p.stderr.readline()
    while err:
        res.append(err)
        yield '{} <br> {}'.format(err, ' ')
        errflag = True
        err = p.stderr.readline()
    p.stderr.close()

    Results(utility=utility, results=res).save()

    if errflag:
        # rerun with help command to show additional info
        p = subprocess.Popen([path, '--help'], stdout=subprocess.PIPE)
        line = p.stdout.readline()
        while line:
            res.append(line)
            print line
            # force browser buffer to flush with spaces
            #yield '{} <br> {}'.format(line, ' '*1024)
            yield '{}'.format(line)
            line = p.stdout.readline()
        p.stdout.close()


def status(request, script_id):
    """ Return status of installed script
    """
    pass

