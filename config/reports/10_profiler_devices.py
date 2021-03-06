# -*- coding: utf-8 -*-
# Copyright (c) 2013 Riverbed Technology, Inc.
#
# This software is licensed under the terms and conditions of the
# MIT License set forth at:
#   https://github.com/riverbed/flyscript-portal/blob/master/LICENSE ("License").
# This software is distributed "AS IS" as set forth in the License.

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

from apps.datasource.models import Column
from apps.devices.models import Device
from apps.report.models import Report
import apps.report.modules.yui3 as yui3
from apps.datasource.modules.profiler_devices import DevicesTable

PROFILER = Device.objects.get(name="profiler")

report = Report(title="Profiler Device List", position=10)
report.save()

#
# Device Table

devtable = DevicesTable.create('devtable', PROFILER)
Column.create(devtable, 'ipaddr', 'Device IP', iskey=True, isnumeric=False)
Column.create(devtable, 'name', 'Device Name', isnumeric=False)
Column.create(devtable, 'type', 'Flow Type', isnumeric=False)
Column.create(devtable, 'version', 'Flow Version', isnumeric=False)

yui3.TableWidget.create(report, devtable, "Device List", height=300, width=12)

