'''
BSD Licence
Copyright (c) 2014, Science & Technology Facilities Council (STFC)
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

Created on 25 May 2013

@author: Maurizio Nagni
'''
import datetime
import logging

from ceda_markup.atom.atom import createID, createUpdated, createPublished, \
    createEntry
from ceda_markup.atom.info import createContent, createTitle, TEXT_TYPE
from ceda_markup.opensearch import filter_results
from ceda_markup.opensearch.os_param import OSParam
from ceda_markup.opensearch.os_request import OS_NAMESPACE
from ceda_markup.opensearch.osquery import OSQuery
from ceda_markup.opensearch.template.atom import OSAtomResponse
from ceda_markup.opensearch.template.osresponse import OSEngineResponse, Result

from djcharme.node.actions import CH_NODE, ANNO_STABLE
from djcharme.node.search import search_title, search_annotations_by_target, \
    search_targets_by_data_type, search_annotations_by_status, \
    search_by_motivation, search_by_organization, \
    search_by_domain, annotation_resource, search_terms
from djcharme.views import check_mime_format


LOGGING = logging.getLogger(__name__)

COUNT_DEFAULT = 10
START_INDEX_DEFAULT = 1
START_PAGE_DEFAULT = 1

ANNOTATIONS = "annotations"
SEARCH_TERMS = "searchTerms"


def _generate_url_id(url, iid=None):
    if iid is None:
        return "%s/search" % (url)

    return "%s/search/%s" % (url, iid)


def _import_count_and_page(context):
    ret = []

    try:
        ret.append(int(context.get('count')))
    except (ValueError, TypeError):
        ret.append(COUNT_DEFAULT)

    try:
        ret.append(int(context.get('startIndex')))
    except (ValueError, TypeError):
        ret.append(START_INDEX_DEFAULT)

    try:
        ret.append(int(context.get('startPage')))
    except (ValueError, TypeError):
        ret.append(START_PAGE_DEFAULT)

    return tuple(ret)


class COSAtomResponse(OSAtomResponse):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        super(COSAtomResponse, self).__init__()

    def generate_entries(self, atomroot, subresults, path, \
                         params_model, context):
        LOGGING.debug("COSAtomResponse:generate_entries(atomroot, subresults, "\
                      "path, params_model, context)")
        if subresults is None:
            return

        entries = []
        for subresult in subresults:
            # Here could loop over results
            atom_id = createID(subresult['subject'], root=atomroot)
            ititle = createTitle(root=atomroot,
                                 body=subresult['subject'],
                                 itype=TEXT_TYPE)
            atom_content = createContent(root=atomroot,
                                         body=subresult['triple'],
                                         itype=TEXT_TYPE)
            time_doc = datetime.datetime.now().isoformat()
            atom_updated = createUpdated(time_doc,
                                         root=atomroot)
            atom_published = createPublished(time_doc,
                                             root=atomroot)
            entry = createEntry(atom_id, ititle, atom_updated,
                                published=atom_published,
                                content=atom_content, root=atomroot)

            entries.append(entry)

        for entry in entries:
            atomroot.append(entry)

    def generate_url(self, osHostURL, context):
        """
        Returns the proper URL to assemble the OSResponse links.

        """
        LOGGING.debug("COSAtomResponse:generate_url(%s, context)",
                      str(osHostURL))
        return _generate_url_id(osHostURL, context.get('target', None))

    def digest_search_results(self, results, context):
        LOGGING.debug("COSAtomResponse:digest_search_results(results, context)")
        title = "CHARMe results"
        count, start_index, start_page = _import_count_and_page(context)

        # set_subresults = set(results.subjects())
        # subjects = [subj for subj in set_subresults]
        # annotation_subresults = filter_results(results,
        #                                    count, start_index, start_page)

        iformat = context.get('format', 'json-ld')
        if iformat == None:
            iformat = 'json-ld'
        iformat = check_mime_format(iformat)
        if results['type'] == ANNOTATIONS:
            subresults = self._get_annotations(results['results'], iformat)
        elif results['type'] == SEARCH_TERMS:
            subresults = self._get_search_term_results(results['results'],
                                                       iformat)
        return Result(count, start_index, start_page, results['count'],
                      subresult=subresults, title=title)

    def _get_annotations(self, results, iformat):
        """

        """

        subresults = []
        for annotation_graph in results:
            try:
                subject = ([subj for subj in
                            annotation_graph.triples(annotation_resource())]
                           [0][0])
                subresults.append(
                    {'subject': str(subject),
                     'triple': annotation_graph.serialize(format=iformat)})
            except IndexError:
                LOGGING.warn("No Annotation resource for graph %s",
                             str(annotation_graph.serialize()))
                continue
        return subresults

    def _get_search_term_results(self, results, iformat):
        subresults = []
        for result in results:
            if iformat == 'json-ld':
                out = self._get_search_term_results_json_ld(result)
            else:
                out = ""
            subresults.append(
                    {'subject': result['searchTerm'], 'triple': out})
        return subresults

    def _get_search_term_results_json_ld(self, results):
        out = '"{@' + results['searchTerm'] + ':['
        first = True
        for result in results['results']:
            if first:
                first = False
            else:
                out = out + ', '
            out = out + '"' + str(result[0]) + '"'
        out = out + ']}'
        return out
    

'''
    def generate_response(self, results, query, \
                          ospath, params_model, context):
        return results
'''


class COSRDFResponse(OSEngineResponse):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        super(COSRDFResponse, self).__init__('rdf')

    def digest_search_results(self, results, context):
        LOGGING.debug("COSRDFResponse:digest_search_results(results, context)")
        title = "CHARMe results"
        count, start_index, start_page = _import_count_and_page(context)
        subresults = filter_results(results, count, start_index, start_page)
        return Result(count, start_index, start_page, len(results), \
                      subresult=subresults, title=title)
        # return results.serialize(format='xml')

    def generate_response(self, results, query, ospath, params_model, context):
        LOGGING.debug("COSRDFResponse:generate_response(results, query, " \
                      "ospath, params_model, context)")
        return results


class COSJsonLDResponse(OSEngineResponse):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        super(COSJsonLDResponse, self).__init__('json-ld')

    def digest_search_results(self, results, context):
        LOGGING.debug("COSJsonLDResponse:digest_search_results(results, " \
                      "context)")
        return results.serialize(format='json-ld')

    def generate_response(self, results, query, ospath, params_model, context):
        LOGGING.debug("COSJsonLDResponse:generate_response(results, query, " \
                      "ospath, params_model, context)")
        return results


class COSTurtleResponse(OSEngineResponse):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        super(COSTurtleResponse, self).__init__('ttl')

    def digest_search_results(self, results, context):
        LOGGING.debug("COSTurtleResponse:digest_search_results(results, " \
                      "context)")
        return results.serialize(format='turtle')

    def generate_response(self, results, query, ospath, params_model, context):
        LOGGING.debug("COSTurtleResponse:generate_response(results, query, " \
                      "ospath, params_model, context)")
        return results


class COSHTMLResponse(OSAtomResponse):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        super(COSHTMLResponse, self).__init__()

    def generateResponse(self, result, queries, ospath, **kwargs):
        LOGGING.debug("COSHTMLResponse:generateResponse(result, queries, " \
                      "ospath, **kwargs)")
        return result + " HTML!"


class COSQuery(OSQuery):
    """
    Class docs.

    """

    def __init__(self):
        """
        Constructor.

        """
        params = []
        params.append(OSParam("count", "count",
                              namespace=OS_NAMESPACE,
                              default=str(COUNT_DEFAULT)))
        params.append(OSParam("startPage", "startPage",
                              namespace=OS_NAMESPACE,
                              default=str(START_PAGE_DEFAULT)))
        params.append(OSParam("startIndex", "startIndex",
                              namespace=OS_NAMESPACE,
                              default=str(START_INDEX_DEFAULT)))
        params.append(OSParam("q", "searchTerms",
                              namespace=OS_NAMESPACE, default=''))
        params.append(OSParam("title", "title",
                              namespace="http://purl.org/dc/terms/",
                              default=''))
        params.append(OSParam("dataType", "dataType",
                              namespace=CH_NODE, default=''))
        params.append(OSParam("target", "target",
                              namespace=CH_NODE, default=''))
        params.append(OSParam("domainOfInterest", "domainOfInterest",
                              namespace=CH_NODE, default=''))
        params.append(OSParam("motivation", "motivation",
                              namespace=CH_NODE, default=''))
        params.append(OSParam("organization", "organization",
                              namespace=CH_NODE, default=''))
        params.append(OSParam("status", "status",
                              namespace=CH_NODE, default=ANNO_STABLE))
        params.append(OSParam("depth", "depth",
                              namespace=CH_NODE, default='1'))
        params.append(OSParam("format", "format",
                              namespace=CH_NODE, default='json-ld'))
        '''
        params.append(OSParam(BBOX, 'box',
                namespace = "http://a9.com/-/opensearch/extensions/geo/1.0/"))
        params.append(OSParam("start", "start",
                namespace = "http://a9.com/-/opensearch/extensions/time/1.0/"))
        params.append(OSParam("stop", "end",
                namespace = "http://a9.com/-/opensearch/extensions/time/1.0/"))
        '''
        self._query_signature = self._querySignature(params)
        super(COSQuery, self).__init__(params)

    def do_search(self, query, context):
        LOGGING.debug("do_search(query, context)")
        results = None
        total_results = 0
        search_type = ANNOTATIONS

        if query.attrib.get('q', None) != None \
                and len(query.attrib.get('q')) > 0:
            results, total_results = search_terms(query.attrib['q'],
                                                  query.attrib)
            search_type = SEARCH_TERMS

        elif query.attrib.get('title', None) != None \
                and len(query.attrib.get('title')) > 0:
            results, total_results = search_title(query.attrib['title'],
                                                  query.attrib)

        elif query.attrib.get('target', None) \
                and len(query.attrib.get('target')) > 0:

            results, total_results = (
                search_annotations_by_target(query.attrib['target'],
                                             query.attrib))

        elif query.attrib.get('domainOfInterest', None) \
                and len(query.attrib.get('domainOfInterest')) > 0:
            results, total_results = (
                search_by_domain(query.attrib['domainOfInterest'],
                                 query.attrib))

        elif query.attrib.get('dataType', None) \
                and len(query.attrib.get('dataType')) > 0:
            results, total_results = (
                search_targets_by_data_type(query.attrib['dataType'],
                                            query.attrib))

        elif query.attrib.get('motivation', None) \
                and len(query.attrib.get('motivation')) > 0:
            results, total_results = (
                search_by_motivation(query.attrib['motivation'], query.attrib))

        elif query.attrib.get('organization', None) \
                and len(query.attrib.get('organization')) > 0:
            results, total_results = (
                search_by_organization(query.attrib['organization'],
                                       query.attrib))

        elif query.attrib.get('status', None) \
                and len(query.attrib.get('status')) > 0:
            results, total_results = search_annotations_by_status(query.attrib)

        return {'results': results, 'count': total_results, 'type' : search_type}

    def _querySignature(self, params_model):
        _params = []
        for params in params_model:
            if params.par_name not in ['count', 'startPage', 'startIndex']:
                _params.append(params.par_name)
        return _params

