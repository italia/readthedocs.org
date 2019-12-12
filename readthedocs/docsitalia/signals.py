# -*- coding: utf-8 -*-
"""Signals for the docsitalia app."""

import logging

from django.dispatch import receiver
from django.db.models.signals import pre_delete, post_save
from django_elasticsearch_dsl.apps import DEDConfig

from readthedocs.projects.models import Project, HTMLFile
from readthedocs.core.signals import webhook_github
from readthedocs.doc_builder.signals import finalize_sphinx_context_data
from readthedocs.search.tasks import index_objects_to_es

from .github import get_metadata_for_document
from .models import PublisherProject, update_project_from_metadata


log = logging.getLogger(__name__) # noqa


@receiver(webhook_github)
def on_webhook_github(sender, project, data, event, **kwargs): # noqa
    # no push no party
    if event != 'push':
        return

    try:
        branch = data['ref'].replace('refs/heads/', '')
    except KeyError:
        log.error(
            'metadata github hook: Parameter "ref" is required')
        return

    if branch != 'master':
        log.info('Skipping metadata update for project: project=%s branch=%s',
                 project, branch)
        return

    try:
        metadata = get_metadata_for_document(project)
    except Exception as e: # noqa
        log.error(
            'Failed to import document metadata: %s', e)
    else:
        update_project_from_metadata(project, metadata)


@receiver(finalize_sphinx_context_data)
def add_sphinx_context_data(sender, data, build_env, **kwargs):  # pylint: disable=unused-argument
    """
    Provides additional data to the sphinx context.

    Data are injected in the provided context

    :param sender: sender class
    :param data: sphinx context
    :param build_env: BuildEnvironment instance
    :return: None
    """
    from readthedocs.docsitalia.utils import get_subprojects

    subprojects = get_subprojects(build_env.project.pk)
    data['subprojects'] = subprojects
    publisher_project = build_env.project.publisherproject_set.first()
    data['publisher_project'] = publisher_project
    if publisher_project:
        publisher = publisher_project.publisher
        data['publisher'] = publisher
        metadata = publisher.metadata.get('publisher', {})
        data['publisher_logo'] = metadata.get('logo_url')
    else:
        data['publisher'] = None
        data['publisher_logo'] = None
    if build_env.project.tags:
        data['tags'] = list(build_env.project.tags.names())


@receiver(pre_delete, sender=PublisherProject)
def on_publisher_project_delete(sender, instance, **kwargs):  # noqa
    """Remove all the projects associated at PublisherProject removal from db and ES indexes."""
    from readthedocs.docsitalia.tasks import clear_es_index
    reused_projects_pks = set(PublisherProject.objects.exclude(
        pk=instance.pk
    ).values_list(
        'projects', flat=True
    ))
    projects_pks = list(instance.projects.values_list('pk', flat=True))
    projects_pks = [p for p in projects_pks if p not in reused_projects_pks]
    if projects_pks:
        instance.projects.filter(pk__in=projects_pks).delete()
        clear_es_index.delay(projects=projects_pks)


@receiver(post_save, sender=Project)
def index_documents_project_save(instance, *args, **kwargs):
    from readthedocs.search.documents import PageDocument

    html_obj_ids = HTMLFile.objects.filter(project=instance).values_list('id', flat=True)

    if html_obj_ids and DEDConfig.autosync_enabled():
        kwargs = {
            'app_label': HTMLFile._meta.app_label,
            'model_name': HTMLFile.__name__,
            'document_class': str(PageDocument),
            'objects_id': list(html_obj_ids),
        }

        index_objects_to_es.delay(**kwargs)
