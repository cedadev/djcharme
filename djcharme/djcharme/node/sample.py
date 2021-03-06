'''
Created on 18 Nov 2013

@author: mnagni
'''
import csv
import logging

from django.contrib.auth.models import User
from djcharme import get_resource
from djcharme.exception import ParseError
from djcharme.node.actions import insert_rdf
from djcharme.node.constants import SUBMITTED
from provider.oauth2.models import Client
from rdflib.plugins.parsers.notation3 import BadSyntax


LOGGING = logging.getLogger(__name__)

CITATION_TEMPLATE = '''

@prefix oa: <http://www.w3.org/ns/oa#> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix cito: <http://purl.org/spar/cito/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix chnode: <http://localhost/> .

<chnode:annoID> a oa:Annotation ;
oa:hasBody <chnode:bodyID> ;
oa:hasTarget <load_target> ;
oa:motivatedBy oa:linking ;
#oa:annotatedAt load_annotated_at;
#oa:serializedAt load_serialized_at;
oa:annotatedBy <chnode:kp_xs02300> .

<chnode:kp_xs02300> a foaf:Person ;
    foaf:name "Maurizio Nagni"  ;
    foaf:mbox <mailto:maurizio.nagni@example.org> .

<chnode:bodyID> a cito:CitationAct ;
cito:hasCitingEntity <load_body> ;
cito:hasCitationEvent cito:citesAsDataSource ;
cito:hasCitedEntity <load_target> .

<load_body> a fabio:load_classes .
<load_target> a fabio:MetadataDocument .
'''


def __load_datasets():
    """
    Load sample data sets.

    """
    datasets_file = open(get_resource('dataset_to_ceda_mappings.csv'))
    # datasets_file = open('resources/dataset_to_ceda_mappings.csv')
    dataset_reader = csv.reader(datasets_file, dialect='excel-tab')
    datasets = {}
    for row in dataset_reader:
        if type(row) != list \
            or len(row[0]) == 0 \
            or (len(row[1]) + len(row[2])) == 0 \
            or row[0] == 'Dataset':
            continue
        try:
            datasets[row[0]] = row[1:3]
        except Exception:
            pass
    return datasets


def __load_citations():
    """
    Load sample citations.

    """
    citations_file = open(get_resource
                          ('ceda_citations_to_metadata_url_mappings.csv'))
    citations_reader = csv.reader(citations_file, dialect='excel-tab')
    citations = {}
    dataset_name = None
    for row in citations_reader:
        if type(row) != list \
            or len(row[0]) == 0 \
            or (len(row[1]) + len(row[2])) == 0 \
            or row[0] == 'Dataset':
            continue
        try:
            if dataset_name == row[0]:
                citations[row[0]].append(row[1:])
            else:
                citations[row[0]] = [row[1:]]
            dataset_name = row[0]
        except Exception:
            pass
    return citations


def load_sample():
    """
    Load sample data.

    """
    datasets = __load_datasets()
    citations = __load_citations()
    user = User()
    user.first_name = 'Sam'
    user.last_name = 'Ple'
    user.username = 'sample'
    user.email = 'sam.ple@example.org'
    client = Client()
    client.name = 'Sample Organization'
    client.url = 'https://localhost/samlpeOrganization/'
    for ds_key in datasets.keys():
        data_set = datasets.get(ds_key)
        cts = citations.get(ds_key, None)
        for cit in cts:
            annotation = CITATION_TEMPLATE.replace("load_target",
                                                   data_set[1].strip())
            if cit[8]:
                annotation = annotation.replace("load_body", cit[8].strip())
            else:
                continue
            if cit[0] == 'article':
                annotation = annotation.replace("load_classes", "Article")
            elif cit[0] == 'inbook':
                annotation = annotation.replace("load_classes", "BookChapter")
            elif cit[0] == 'proceedings':
                annotation = annotation.replace("load_classes",
                                                "AcademicProceedings")
            elif cit[0] == 'techreport':
                annotation = annotation.replace("load_classes",
                                                "TechnicalReport")
            elif cit[0] == 'misc':
                continue
            else:
                print "other"
                continue

            try:
                insert_rdf(annotation, 'turtle', user, client,
                                   graph=SUBMITTED)
            except BadSyntax as ex:
                LOGGING.warn(ex)
                continue
            except ParseError as ex:
                LOGGING.warn(ex)
                continue
