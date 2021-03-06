'''
BSD Licence
Copyright (c) 2015, Science & Technology Facilities Council (STFC)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
        this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.
    * Neither the name of the Science & Technology Facilities Council (STFC)
        nor the names of its contributors may be used to endorse or promote
        products derived from this software without specific prior written
        permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Created on 14 May 2013

@author: mnagni
'''
import json
import logging

from django.contrib import messages
from django.http.response import (HttpResponseRedirectBase, HttpResponse,
                                  HttpResponseNotFound)
from django.views.decorators.csrf import csrf_exempt
from djcharme import mm_render_to_response_error, \
    __version__
from djcharme.exception import NotFoundError
from djcharme.exception import ParseError
from djcharme.exception import SecurityError
from djcharme.exception import StoreConnectionError
from djcharme.exception import UserError
from djcharme.node.actions import collect_annotations, find_resource_by_id, \
    format_resource_uri_ref, change_annotation_state, get_vocab, \
    report_to_moderator, validate_graph_name
from djcharme.node.actions import insert_rdf, modify_rdf
from djcharme.node.constants import OA, FOAF, PROV, RDF, FORMAT_MAP, \
    CONTENT_JSON, CONTENT_RDF, CONTENT_TEXT, DATA, PAGE, SUBMITTED, RETIRED
from djcharme.views import isDELETE, isPOST, isPUT, isOPTIONS, \
    validate_mime_format, http_accept, get_depth, content_type, \
    check_mime_format, get_format

from djcharme.views.resource import agent, annotation, annotation_index, \
    activity, composite, person, resource


LOGGING = logging.getLogger(__name__)


class HttpResponseSeeOther(HttpResponseRedirectBase):
    '''
        Implements a simple HTTP 303 response
    '''
    status_code = 303


def __serialize(graph, req_format=CONTENT_RDF):
    '''
        Serializes a graph according to the required format
        - rdflib:Graph **graph** the graph to serialize
        - string **req_format** the serialization format
        - **return** the serialized graph
    '''
    if req_format == FORMAT_MAP['json-ld']:
        req_format = 'json-ld'

    return graph.serialize(format=req_format)


def index(request, graph='submitted'):
    '''
        Returns a tabular view of the stored annotations.
        - HTTPRequest **request** the client request
        - string **graph**  the required named graph
        TODO: In a future implementation this actions should be supported by an
        OpenSearch implementation
    '''
    try:
        validate_graph_name(graph)
    except UserError as ex:
        messages.add_message(request, messages.ERROR, ex)
        return mm_render_to_response_error(request, '400.html', 400)
    tmp_g = None
    try:
        tmp_g = collect_annotations(graph)
    except StoreConnectionError as ex:
        LOGGING.error("Internal error. " + str(ex))
        messages.add_message(request, messages.ERROR, ex)
        return mm_render_to_response_error(request, '500.html', 500)

    req_format = validate_mime_format(request)

    if req_format is not None:
        return HttpResponse(__serialize(tmp_g, req_format=req_format))
    elif 'text/html' in http_accept(request):
        return annotation_index(request, tmp_g, graph)

    messages.add_message(request, messages.ERROR, "Format not accepted")
    return mm_render_to_response_error(request, '400.html', 400)


def _get_return_format(request, request_format):
    '''
        Extracts the return format otherwise return the request_format
    '''
    return_format = http_accept(request)
    if type(return_format) == list:
        return_format = return_format[0]

    if return_format is None:
        return_format = request_format
    else:
        return_format = check_mime_format(return_format)

    if return_format is None:
        return_format = request_format
    return FORMAT_MAP.get(return_format)


# Temporary solution as long identify a solution for csrf
# @csrf_protect
@csrf_exempt
def insert(request):
    '''
        Inserts in the triplestore a new annotation under the "SUBMITTED"
        graph
    '''
    try:
        return _insert(request)
    except UserError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '400.html', 400)
    except Exception as ex:
        LOGGING.error("insert - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _insert(request):
    '''
        Inserts in the triplestore a new annotation under the "SUBMITTED"
        graph
    '''
    request_format = check_mime_format(content_type(request))
    return_format = _get_return_format(request, request_format)

    if request_format is None:
        messages.add_message(request, messages.ERROR,
                             "Cannot ingest the posted format")
        return mm_render_to_response_error(request, '400.html', 400)

    if isPOST(request) or isOPTIONS(request):
        triples = request.body
        try:
            anno_uri = insert_rdf(triples, request_format, request.user,
                                  request.client, graph=SUBMITTED)
        except ParseError as ex:
            LOGGING.debug("insert parsing error: %s", str(ex))
            messages.add_message(request, messages.ERROR, str(ex))
            return mm_render_to_response_error(request, '400.html', 400)
        except StoreConnectionError as ex:
            LOGGING.error("Internal error. " + str(ex))
            messages.add_message(request, messages.ERROR, ex)
            return mm_render_to_response_error(request, '500.html', 500)
        return HttpResponse(anno_uri, content_type=return_format)


# Temporary solution as long identify a solution for csrf
# @csrf_protect
@csrf_exempt
def modify(request):
    """
    Modify the annotation contained in the request.

    Args:
        request (WSGIRequest): The request from the user

    """
    try:
        return _modify(request)
    except NotFoundError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '404.html', 404)
    except SecurityError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '403.html', 403)
    except UserError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '400.html', 400)
    except Exception as ex:
        LOGGING.error("modify - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _modify(request):
    """
    Modify the annotation contained in the request.

    Args:
        request (WSGIRequest): The request from the user

    """
    request_format = check_mime_format(content_type(request))
    return_format = _get_return_format(request, request_format)

    if request_format is None:
        messages.add_message(request, messages.ERROR,
                             "Cannot ingest the posted format")
        return mm_render_to_response_error(request, '400.html', 400)

    if isPOST(request) or isOPTIONS(request):
        try:
            anno_uri = modify_rdf(request, request_format)
        except ParseError as ex:
            LOGGING.debug("modify parsing error: %s", str(ex))
            messages.add_message(request, messages.ERROR, str(ex))
            return mm_render_to_response_error(request, '400.html', 400)
        except StoreConnectionError as ex:
            LOGGING.error("Internal error. " + str(ex))
            messages.add_message(request, messages.ERROR, ex)
            return mm_render_to_response_error(request, '500.html', 500)
        return HttpResponse(anno_uri, content_type=return_format)


# Temporary solution as long identify a solution for csrf
# @csrf_protect
@csrf_exempt
def advance_status(request):
    '''
        Advance the status of an annotation
    '''
    try:
        return _advance_status(request)
    except NotFoundError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '404.html', 404)
    except SecurityError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '403.html', 403)
    except UserError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '400.html', 400)
    except Exception as ex:
        LOGGING.error("advance_status - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _advance_status(request):
    '''
        Advance the status of an annotation
    '''
    if isPOST(request) and (CONTENT_JSON in content_type(request) or
                            'application/json' in content_type(request)):
        params = json.loads(request.body)
        if not params.has_key('annotation') or not params.has_key('toState'):
            messages.add_message(request, messages.ERROR,
                                 "Missing annotation/state parameters")
            return mm_render_to_response_error(request, '400.html', 400)
        LOGGING.info("advancing %s to state:%s", str(params.get('annotation')),
                     str(params.get('toState')))
        change_annotation_state(params.get('annotation'),
                                params.get('toState'), request)
        return HttpResponse(status=204)
    elif not isPOST(request):
        messages.add_message(request, messages.ERROR,
                             "Message must be a POST")
        return mm_render_to_response_error(request, '405.html', 405)
    else:
        messages.add_message(request, messages.ERROR,
                             "Message must contain " + CONTENT_JSON)
        return mm_render_to_response_error(request, '400.html', 400)


@csrf_exempt
def process_resource(request, resource_id):
    """
        Process the resource dependent on the mime format.
    """
    try:
        if isDELETE(request):
            return _delete(request, resource_id)
        if _is_report_to_moderator(request):
            return _report_to_moderator(request, resource_id)
        return _process_resource(request, resource_id)
    except Exception as ex:
        LOGGING.error("process_resource - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _is_report_to_moderator(request):
    """
        Is this a report to moderator request?
    """
    path_bits = request.path.split('/')
    if len(path_bits) < 4:
        return False
    if path_bits[3] == 'reporttomoderator':
        return True
    return False


def _delete(request, resource_id):
    """
        Delete the resource, move it to the 'retired' graph.
    """
    LOGGING.info("advancing %s to state:%s", str(resource_id), RETIRED)
    try:
        change_annotation_state(resource_id, RETIRED, request)
    except NotFoundError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '404.html', 404)
    except SecurityError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '403.html', 403)
    return HttpResponse(status=204)


def _report_to_moderator(request, resource_id):
    """
        Report the resource to the moderator.
    """
    LOGGING.info("reporting %s to moderator", str(resource_id))
    if not isPUT(request):
        messages.add_message(request, messages.ERROR,
                             "Message must be a PUT")
        return mm_render_to_response_error(request, '405.html', 405)
    try:
        report_to_moderator(request, resource_id)
    except NotFoundError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '404.html', 404)
    except SecurityError as ex:
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '403.html', 403)
    return HttpResponse(status=204)


def _process_resource(request, resource_id):
    """
        Process the resource dependent on the mime format.
    """
    if validate_mime_format(request) is not None:
        path = "/%s/%s" % (DATA, resource_id)
        path = _process_resource_parameters(request, path)
        LOGGING.info("Redirecting to %s", str(path))
        return HttpResponseSeeOther(path)

    if 'text/html' in http_accept(request):
        path = '/%s/%s' % (PAGE, resource_id)
        path = _process_resource_parameters(request, path)
        LOGGING.info("Redirecting to /%s/%s", str(PAGE), str(resource_id))
        return HttpResponseSeeOther(path)
    return HttpResponseNotFound()


def _process_resource_parameters(request, path):
    """
        Add depth and format parameters onto the path
    """
    depth = get_depth(request)
    format_ = get_format(request)
    if format_ is not None:
        path = "%s/?format=%s" % (path, format_)
        if depth is not None:
            path = "%s&depth=%s" % (path, depth)
    elif depth is not None:
        path = "%s/?depth=%s" % (path, depth)
    return path


def process_data(request, resource_id):
    """
        Process the data dependent on the mime format.
    """
    try:
        return _process_data(request, resource_id)
    except Exception as ex:
        LOGGING.error("process_data - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _process_data(request, resource_id):
    """
        Process the data dependent on the mime format.
    """
    if get_format(request) is None and 'text/html' in http_accept(request):
        return process_resource(request, resource_id=resource_id)

    req_format = validate_mime_format(request)
    if req_format is None:
        return process_resource(request, resource_id)
    depth = get_depth(request)
    if depth == None:
        depth = 1
    tmp_g = find_resource_by_id(resource_id, depth)
    return HttpResponse(tmp_g.serialize(format=req_format),
                        mimetype=FORMAT_MAP.get(req_format))


def process_page(request, resource_id=None):
    """
        Process the page dependent on the mime format.
    """
    try:
        return _process_page(request, resource_id)
    except Exception as ex:
        LOGGING.error("process_page - unexpected error: %s", str(ex))
        messages.add_message(request, messages.ERROR, str(ex))
        return mm_render_to_response_error(request, '500.html', 500)


def _process_page(request, resource_id=None):
    """
        Process the page dependent on the mime format.
    """
    if 'text/html' not in http_accept(request):
        return process_resource(request, resource_id)

    tmp_g = find_resource_by_id(resource_id, 1)

    resource_uri = format_resource_uri_ref(resource_id)

    # Check if the resource is an annotation
    triples = tmp_g.triples((resource_uri, RDF['type'], OA['Annotation']))
    for triple in triples:
        return annotation(request, resource_uri, tmp_g)

    # Check if the resource is a SoftwareAgent
    triples = tmp_g.triples((resource_uri, RDF['type'], PROV['SoftwareAgent']))
    for triple in triples:
        return agent(request, resource_uri, tmp_g)

    # Check if the resource is an activity
    triples = tmp_g.triples((resource_uri, RDF['type'], PROV['Activity']))
    for triple in triples:
        return activity(request, resource_uri, tmp_g)

    # Check if the resource is a person
    triples = tmp_g.triples((resource_uri, RDF['type'], FOAF['Person']))
    for triple in triples:
        return person(request, resource_uri, tmp_g)

    # Check if the resource is a composite
    triples = tmp_g.triples((resource_uri, RDF['type'], OA['Composite']))
    for triple in triples:
        return composite(request, resource_uri, tmp_g)

    return resource(request, resource_uri, tmp_g)


def version(request):
    """
    Get the version number of the server.

    Args:
        request (WSGIRequest): The request from the user

    """
    return HttpResponse(__version__, content_type=CONTENT_TEXT)


def vocab(request):
    """
    Get the chame vocab.

    Args:
        request (WSGIRequest): The request from the user

    """
    tmp_g = None
    try:
        tmp_g = get_vocab()
    except StoreConnectionError as ex:
        LOGGING.error("Internal error. " + str(ex))
        messages.add_message(request, messages.ERROR, ex)
        return mm_render_to_response_error(request, '500.html', 500)

    req_format = validate_mime_format(request)
    if req_format is None or 'text/html' in http_accept(request):
        req_format = CONTENT_JSON
    if req_format is not None:
        return HttpResponse(__serialize(tmp_g, req_format=req_format))

    messages.add_message(request, messages.ERROR, "Format not accepted")
    return mm_render_to_response_error(request, '400.html', 400)

