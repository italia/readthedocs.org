# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import mock
import requests_mock
from requests.exceptions import ConnectionError

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings
from readthedocs.builds.models import Version
from readthedocs.docsitalia.github import InvalidMetadata
from readthedocs.docsitalia.models import Publisher, PublisherProject
from readthedocs.docsitalia.views.core_views import (
    DocsItaliaHomePage, PublisherIndex, PublisherProjectIndex)
from readthedocs.oauth.models import RemoteRepository
from readthedocs.projects.models import Project


DOCUMENT_METADATA = """document:
  name: Documento Documentato Pubblicamente
  description: |
    Lorem ipsum dolor sit amet, consectetur
  tags:
    - amazing document"""


class DocsItaliaViewsTest(TestCase):
    fixtures = ['eric']

    def setUp(self):
        eric = User.objects.get(username='eric')
        remote = RemoteRepository.objects.create(
            full_name='remote repo name',
            html_url='https://github.com/testorg/myrepourl',
            ssh_url='https://github.com/org-docs-italia/altro-progetto.git',
        )
        remote.users.add(eric)

        self.import_project_data = {
            'repo_type': 'git',
            'description': 'description',
            'remote_repository': str(remote.pk),
            'repo': 'https://github.com/org-docs-italia/altro-progetto.git',
            'project_url': 'https://github.com/org-docs-italia/altro-progetto',
            'name': 'altro-progetto'
        }
        self.document_settings_url = (
            'https://raw.githubusercontent.com/org-docs-italia/'
            'altro-progetto/master/document_settings.yml'
        )

    def test_docsitalia_homepage_get_queryset_filter_projects(self):
        hp = DocsItaliaHomePage()

        project = Project.objects.create(
            name='my project',
            slug='projectslug',
            repo='https://github.com/testorg/myrepourl.git'
        )

        qs = hp.get_queryset()
        self.assertFalse(qs.exists())

        publisher = Publisher.objects.create(
            name='Test Org',
            slug='testorg',
            metadata={},
            projects_metadata={},
            active=False
        )
        pub_project = PublisherProject.objects.create(
            name='Test Project',
            slug='testproject',
            metadata={
                'documents': [
                    'https://github.com/testorg/myrepourl',
                    'https://github.com/testorg/anotherrepourl',
                ]
            },
            publisher=publisher,
            active=False
        )
        pub_project.projects.add(project)

        qs = hp.get_queryset()
        self.assertFalse(qs.exists())

        # active publisher project, not active publisher
        pub_project.active = True
        pub_project.save()
        qs = hp.get_queryset()
        self.assertFalse(qs.exists())

        # active publisher, not active publisher project
        pub_project.active = False
        pub_project.save()
        publisher.active = True
        publisher.save()
        qs = hp.get_queryset()
        self.assertFalse(qs.exists())

        # active publisher, active publisher project, no public version
        pub_project.active = True
        pub_project.save()
        # a version for the project is already available
        version = Version.objects.first()
        version.privacy_level = 'private'
        version.save()

        qs = hp.get_queryset()
        self.assertFalse(qs.exists())

        # at last it should return our project
        version.privacy_level = 'public'
        version.save()
        qs = hp.get_queryset().values_list('pk')
        self.assertTrue(list(qs), [project.pk])

    def test_docsitalia_publisher_index_get_queryset_filter_active(self):
        index = PublisherIndex()

        publisher = Publisher.objects.create(
            name='Test Org',
            slug='testorg',
            metadata={},
            projects_metadata={},
            active=False
        )

        qs = index.get_queryset()
        self.assertFalse(qs.exists())

        publisher.active = True
        publisher.save()

        qs = index.get_queryset()
        self.assertTrue(qs.exists())

    def test_docsitalia_publisher_project_index_get_queryset_filter_active(self):
        index = PublisherProjectIndex()

        publisher = Publisher.objects.create(
            name='Test Org',
            slug='testorg',
            metadata={},
            projects_metadata={},
            active=False
        )
        pub_project = PublisherProject.objects.create(
            name='Test Project',
            slug='testproject',
            metadata={
                'documents': [
                    'https://github.com/testorg/myrepourl',
                    'https://github.com/testorg/anotherrepourl',
                ]
            },
            publisher=publisher,
            active=False
        )

        qs = index.get_queryset()
        self.assertFalse(qs.exists())

        publisher.active = True
        publisher.save()
        qs = index.get_queryset()
        self.assertFalse(qs.exists())

        pub_project.active = True
        pub_project.save()
        publisher.active = False
        publisher.save()
        qs = index.get_queryset()
        self.assertFalse(qs.exists())

        publisher.active = True
        publisher.save()
        qs = index.get_queryset()
        self.assertTrue(qs.exists())

    def test_docsitalia_import_render_error_without_metadata(self):
        self.client.login(username='eric', password='test')
        with requests_mock.Mocker() as rm:
            rm.get(self.document_settings_url, exc=ConnectionError)
            response = self.client.post(
                '/docsitalia/dashboard/import/', data=self.import_project_data)
        self.assertTemplateUsed(response, 'docsitalia/import_error.html')

    def test_docsitalia_import_render_error_with_invalid_metadata(self):
        self.client.login(username='eric', password='test')
        with requests_mock.Mocker() as rm:
            rm.get(self.document_settings_url, exc=InvalidMetadata)
            response = self.client.post(
                '/docsitalia/dashboard/import/', data=self.import_project_data)
        self.assertTemplateUsed(response, 'docsitalia/import_error.html')

    @mock.patch('readthedocs.docsitalia.views.core_views.trigger_build')
    def test_docsitalia_redirect_to_project_detail_with_valid_metadata(self, trigger_build):
        self.client.login(username='eric', password='test')
        with requests_mock.Mocker() as rm:
            rm.get(self.document_settings_url, text=DOCUMENT_METADATA)
            response = self.client.post(
                '/docsitalia/dashboard/import/', data=self.import_project_data)
        project = Project.objects.get(repo=self.import_project_data['repo'])
        repo = RemoteRepository.objects.get(ssh_url=project.repo)
        self.assertEqual(repo.project, project)
        redirect_url = reverse('projects_detail', kwargs={'project_slug': 'altro-progetto'})
        self.assertRedirects(response, redirect_url)