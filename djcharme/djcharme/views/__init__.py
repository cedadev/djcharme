from djcharme.node.constants import FORMAT_MAP


FORMAT = 'format'
DEPTH = 'depth'


def isGET(request):
    return request.method == 'GET'


def isPUT(request):
    return request.method == 'PUT'


def isDELETE(request):
    return request.method == 'DELETE'


def isPOST(request):
    return request.method == 'POST'


def isOPTIONS(request):
    return request.method == 'OPTIONS'


def isHEAD(request):
    return request.method == 'HEAD'


def isPATCH(request):
    return request.method == 'PATCH'


def content_type(request):
    content_type = request.environ.get('CONTENT_TYPE', None)
    if content_type is None:
        return None
    else:
        return content_type.split(';')[0]


def get_format(request):
    try:
        return request.GET[FORMAT]
    except KeyError:
        return None


def get_depth(request):
    depth = request.GET.get(DEPTH)
    if depth is not None:
        try:
            return int(depth)
        except ValueError:
            return None
    return None


def http_accept(request):
    accept = request.META.get('HTTP_ACCEPT', None)
    if accept is None:
        return None
    return accept.split(';')[0].split(',')


def check_mime_format(mimeformat):
    '''Map input MIME format to one of the accepted formats available
    '''

    # Set a default MIME format if none was set
    if mimeformat is None:
        mimeformat = 'application/ld+json'

    if '/' in mimeformat:
        for k, value in FORMAT_MAP.iteritems():
            if value in mimeformat:
                return k
    else:
        for k, value in FORMAT_MAP.iteritems():
            if k in mimeformat:
                return k

def validate_mime_format(request):
    req_format = [get_format(request)]
    if req_format[0] is None:
        req_format = http_accept(request)

    for mimeformat in req_format:
        ret = check_mime_format(mimeformat)
        if ret is not None:
            return ret
    return None

'''
        SELECT Distinct ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o . }}
'''
