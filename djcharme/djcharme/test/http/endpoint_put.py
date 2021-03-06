'''
Created on 25 Jul 2013

@author: mnagni
'''

import logging
import unittest

from django.test.client import RequestFactory
from rdflib.graph import Graph

from djcharme import settings
from djcharme.charme_middleware import CharmeMiddleware
from djcharme.node.actions import format_graph_iri
from djcharme.test import turtle_usecase1
from djcharme.views.endpoint import endpoint


LOGGING = logging.getLogger(__name__)

class Test(unittest.TestCase):

    def setUp(self):
        self.store = CharmeMiddleware.get_store(debug=True)

        self.graph = 'submitted'
        self.identifier = '%s/%s' % (getattr(settings, 'SPARQL_DATA'),
                                     self.graph)
        self.g = Graph(store=self.store, identifier=self.identifier)
        self.factory = RequestFactory()

    def tearDown(self):
        for res in self.g:
            self.g.remove(res)

    def test_PUT(self):
        # self.test_insert_anotation()

        graph = format_graph_iri('submitted')
        request = self.factory.put('/endpoint?graph=%s' % graph,
                                   data=turtle_usecase1,
                                   content_type='text/turtle')
        response = endpoint(request)
        self.assert_(response.status_code in [200, 204],
                     "HTTPResponse has status_code: %s" % response.status_code)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.test_get_index']
    unittest.main()
