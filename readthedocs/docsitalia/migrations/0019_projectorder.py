# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-11-25 11:18
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0044_auto_20190703_1300'),
        ('docsitalia', '0018_create_allowed_tags'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectOrder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.PositiveIntegerField(default=0, help_text='Greater number goes first in Project list')),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='projects.Project', verbose_name='Projects')),
            ],
            options={
                'verbose_name': 'project order',
                'verbose_name_plural': 'projects order',
                'ordering': ('-priority',),
            },
        ),
    ]
