import functools
import http.server
import threading
from contextlib import contextmanager
import pytest
from lib import _docsite as site


@contextmanager
def server(handler):
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{srv.server_port}/pkg/'
    finally:srv.shutdown();srv.server_close();thread.join()


@pytest.mark.parametrize('url,normalized',[
 ('https://EXAMPLE.org:443/pkg','https://example.org/pkg/'),
 ('http://example.org:80/pkg/','http://example.org/pkg/'),
 ('https://example.org/Pkg%2fslice/','https://example.org/Pkg%2Fslice/'),
])
def test_base_url_validation_normalization(url,normalized):
    assert site.base_url(url)==normalized


@pytest.mark.parametrize('hops,accepted',[(1,True),(3,True),(4,False)])
def test_same_origin_redirect_policy(hops,accepted):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            index=int(self.path.rsplit('/',1)[-1]) if self.path.rsplit('/',1)[-1].isdigit() else 0
            if index<hops:
                self.send_response(302);self.send_header('Location',f'/pkg/{index+1}');self.end_headers()
            else:
                self.send_response(200);self.end_headers();self.wfile.write(b'<urlset/>')
        def log_message(self,*args):pass
    with server(Handler) as base:
        if accepted:assert site.sitemap(base)==(set(),0)
        else:
            with pytest.raises(ValueError,match='fresh invocation'):site.sitemap(base)


@pytest.mark.parametrize('target',['https://example.org/pkg/','http://www.example.org/pkg/','https://www.example.org/pkg/'])
def test_cross_origin_redirect_never_followed(target):
    redirects=site.Redirects('http://example.org/pkg/')
    import urllib.request
    with pytest.raises(ValueError,match=target):
        redirects.redirect_request(urllib.request.Request('http://example.org/pkg/sitemap.xml'),None,302,'',{},target)


def test_sitemap_shape_and_bounds():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers()
            try:self.wfile.write(b'x'*(site.MAX_BYTES+1))
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    with server(Handler) as base:
        with pytest.raises(ValueError,match='5 MiB'):site.sitemap(base)


def test_foreign_and_zero_inbase_entries():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            base=f'http://127.0.0.1:{self.server.server_port}'
            xml=f'<urlset><url><loc>{base}/pkg/reference/Case%2froute.html#fragment</loc></url><url><loc>{base}/pkg-extra/reference/a.html</loc></url><url><loc>{base}/pkg/reference/case/route.html</loc></url></urlset>'
            self.send_response(200);self.end_headers();self.wfile.write(xml.encode())
        def log_message(self,*args):pass
    with server(Handler) as base:
        paths,foreign=site.sitemap(base)
    assert paths=={'reference/Case%2Froute.html','reference/case/route.html'} and foreign==1


def test_slow_sitemap_total_deadline():
    import time
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers()
            try:
                for _ in range(200):
                    self.wfile.write(b' ');self.wfile.flush();time.sleep(.1)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    assert site.TIMEOUT==10
    with server(Handler) as base:
        start=time.monotonic()
        with pytest.raises((ValueError,TimeoutError),match='budget|timed out'):site.sitemap(base)
        elapsed=time.monotonic()-start
    assert 9<=elapsed<13
