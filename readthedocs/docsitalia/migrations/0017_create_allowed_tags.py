# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-11-18 09:21
from __future__ import unicode_literals

from django.core.management import call_command
from django.db import migrations


def sync_allowed_tags(apps, schema_editor):
    """Create missing allowed tags"""
    call_command('import_allowed_tags')


class Migration(migrations.Migration):

    dependencies = [
        ('docsitalia', '0016_force_python'),
    ]

    operations = [
        migrations.RunPython(sync_allowed_tags, migrations.RunPython.noop),
    ]
